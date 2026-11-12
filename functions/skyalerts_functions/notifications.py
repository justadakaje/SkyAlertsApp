"""FCM push notification triggers for SkyAlerts.

Implements the four push triggers:
1. New cosmic explosions & outbursts (`SNIa`, `TDE`, `KN`, `SLSN`) — topic `transients`
   plus per-user custom thresholds (`min_confidence`, `max_peak_mag`) on `users/{uid}`.
2. Named Solar System catches — topic `solar_matched` when IMCCE SkyBoT matches a known
   minor planet.
3. Bookmarked object updates — per-user FCM tokens when a bookmarked object receives
   new detections or a classification change.
4. Weekly Sky Dispatch ready — topic `weekly_dispatch` when the Sunday digest is sent.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any

from skyalerts_digest.classes import TRANSIENT_CLASSES

log = logging.getLogger("skyalerts_functions.notifications")


@dataclass(frozen=True, slots=True)
class NotificationPayload:
    title: str
    body: str
    topic: str | None = None
    tokens: tuple[str, ...] = ()
    data: dict[str, str] = field(default_factory=dict)


SendFn = Callable[[NotificationPayload], None]


def _default_send(payload: NotificationPayload) -> None:
    """Dispatches via `firebase_admin.messaging` in production."""
    from firebase_admin import messaging

    notification = messaging.Notification(title=payload.title, body=payload.body)
    if payload.topic:
        msg = messaging.Message(
            notification=notification,
            topic=payload.topic,
            data=payload.data,
        )
        messaging.send(msg)
    elif payload.tokens:
        multicast = messaging.MulticastMessage(
            notification=notification,
            tokens=list(payload.tokens),
            data=payload.data,
        )
        messaging.send_each_for_multicast(multicast)


def notify_new_transients(
    db: Any,
    touched_objects: Sequence[dict[str, Any]],
    *,
    min_default_prob: float = 0.80,
    send_fn: SendFn | None = None,
) -> list[NotificationPayload]:
    """Trigger 1: Notify topic `transients` and matching user thresholds on new explosions."""
    sender = send_fn or _default_send
    sent: list[NotificationPayload] = []

    candidates = [
        obj
        for obj in touched_objects
        if obj.get("is_new")
        and not obj.get("is_artifact")
        and obj.get("top_class") in TRANSIENT_CLASSES
    ]
    if not candidates:
        return sent

    # Pre-fetch signed-in user threshold preferences if any exist
    user_docs: list[dict[str, Any]] = []
    for snap in db.collection("users").stream():
        d = snap.to_dict() or {}
        if d.get("fcm_tokens") and d.get("notify_transients", True):
            user_docs.append(d)

    for obj in candidates:
        prob = float(obj.get("top_probability") or 0.0)
        peak_mag = obj.get("peak_mag")
        survey = str(obj.get("survey") or "ztf")
        oid = str(obj.get("oid") or "")
        top_class = str(obj.get("top_class") or "Transient")
        prob_pct = round(prob * 100)

        mag_clause = f" at mag {float(peak_mag):.1f}" if peak_mag is not None else ""
        title = f"New cosmic explosion: {oid}"
        body = f"Classified as {top_class} ({prob_pct}% confidence){mag_clause}."
        data = {
            "type": "transient",
            "survey": survey,
            "oid": oid,
            "top_class": top_class,
            "route": f"/objects/{survey}/{oid}",
        }

        if prob >= min_default_prob:
            payload = NotificationPayload(
                title=title,
                body=body,
                topic="transients",
                data=data,
            )
            try:
                sender(payload)
                sent.append(payload)
            except Exception as exc:
                log.warning("fcm_transient_topic_failed oid=%s err=%s", oid, exc)

        # Evaluate per-user custom thresholds (e.g. lower min_confidence or max_peak_mag filter)
        matching_tokens: list[str] = []
        for u in user_docs:
            min_conf = float(u.get("min_confidence", min_default_prob))
            max_mag = u.get("max_peak_mag")
            if prob < min_conf:
                continue
            if max_mag is not None and (peak_mag is None or float(peak_mag) > float(max_mag)):
                continue
            # Only send direct user token push if user has custom threshold below topic default
            # or a specific magnitude filter so they don't get double-notified on topic.
            if min_conf != min_default_prob or max_mag is not None:
                for tok in u.get("fcm_tokens") or []:
                    if isinstance(tok, str) and tok not in matching_tokens:
                        matching_tokens.append(tok)

        if matching_tokens:
            user_payload = NotificationPayload(
                title=title,
                body=body,
                tokens=tuple(matching_tokens),
                data=data,
            )
            try:
                sender(user_payload)
                sent.append(user_payload)
            except Exception as exc:
                log.warning("fcm_transient_user_failed oid=%s err=%s", oid, exc)

    return sent


def notify_matched_asteroids(
    matched_objects: Sequence[dict[str, Any]],
    *,
    send_fn: SendFn | None = None,
) -> list[NotificationPayload]:
    """Trigger 2: Notify topic `solar_matched` when IMCCE SkyBoT identifies a known asteroid."""
    sender = send_fn or _default_send
    sent: list[NotificationPayload] = []

    for item in matched_objects:
        survey = str(item.get("survey") or "ztf")
        oid = str(item.get("oid") or "")
        name = item.get("sso_name") or item.get("object_name") or "Known minor planet"
        number = item.get("sso_number") or item.get("object_number")
        sep = item.get("sep_arcsec")
        label = f"({number}) {name}" if number else str(name)
        sep_str = f' ({float(sep):.2f}" match)' if sep is not None else ""

        payload = NotificationPayload(
            title=f"Solar System catch: {label}",
            body=f"Survey detection {oid} matched to known asteroid {label}{sep_str}.",
            topic="solar_matched",
            data={
                "type": "solar_matched",
                "survey": survey,
                "oid": oid,
                "object_name": str(name),
                "route": f"/objects/{survey}/{oid}",
            },
        )
        try:
            sender(payload)
            sent.append(payload)
        except Exception as exc:
            log.warning("fcm_solar_matched_failed oid=%s err=%s", oid, exc)

    return sent


def notify_bookmarked_updates(
    db: Any,
    updated_objects: Sequence[dict[str, Any]],
    *,
    send_fn: SendFn | None = None,
) -> list[NotificationPayload]:
    """Trigger 3: Notify users whose bookmarked objects received new detections or class changes."""
    sender = send_fn or _default_send
    sent: list[NotificationPayload] = []

    candidates = [
        obj
        for obj in updated_objects
        if not obj.get("is_new") and (obj.get("ndet_increased") or obj.get("class_changed"))
    ]
    if not candidates:
        return sent

    by_key = {str(obj["doc_id"]): obj for obj in candidates if obj.get("doc_id")}
    if not by_key:
        return sent

    # Scan bookmarks via collection_group("bookmarks") and map object_key -> user uids
    bookmarks_by_key: dict[str, list[str]] = {}
    for b_snap in db.collection_group("bookmarks").stream():
        b_data = b_snap.to_dict() or {}
        obj_key = str(b_data.get("object_key") or b_snap.id)
        uid = str(b_data.get("uid") or "")
        if obj_key in by_key and uid:
            bookmarks_by_key.setdefault(obj_key, []).append(uid)

    if not bookmarks_by_key:
        return sent

    # Resolve user tokens
    tokens_by_uid: dict[str, list[str]] = {}
    for uids in bookmarks_by_key.values():
        for uid in uids:
            if uid not in tokens_by_uid:
                u_snap = db.collection("users").document(uid).get()
                u_data = (u_snap.to_dict() or {}) if u_snap.exists else {}
                tokens_by_uid[uid] = [
                    str(t) for t in (u_data.get("fcm_tokens") or []) if isinstance(t, str)
                ]

    for obj_key, uids in bookmarks_by_key.items():
        obj = by_key[obj_key]
        tokens: list[str] = []
        for uid in uids:
            for t in tokens_by_uid.get(uid, []):
                if t not in tokens:
                    tokens.append(t)
        if not tokens:
            continue

        oid = str(obj.get("oid") or obj_key)
        survey = str(obj.get("survey") or "ztf")
        reasons: list[str] = []
        if obj.get("ndet_increased"):
            reasons.append(f"now {obj.get('n_detections')} detections")
        if obj.get("class_changed"):
            reasons.append(f"reclassified as {obj.get('top_class')}")

        payload = NotificationPayload(
            title=f"Saved object update: {oid}",
            body=f"{oid} updated ({', '.join(reasons)}).",
            tokens=tuple(tokens),
            data={
                "type": "bookmark_update",
                "survey": survey,
                "oid": oid,
                "route": f"/objects/{survey}/{oid}",
            },
        )
        try:
            sender(payload)
            sent.append(payload)
        except Exception as exc:
            log.warning("fcm_bookmark_update_failed oid=%s err=%s", oid, exc)

    return sent


def notify_weekly_digest(
    *,
    window_label: str,
    total_active: int,
    transients_count: int,
    send_fn: SendFn | None = None,
) -> NotificationPayload | None:
    """Trigger 4: Notify topic `weekly_dispatch` when the Sunday digest is ready."""
    sender = send_fn or _default_send
    payload = NotificationPayload(
        title=f"Weekly Sky Dispatch ({window_label})",
        body=(
            f"{total_active:,} active objects and {transients_count:,} cosmic explosions "
            "spotted this week. Tap to explore."
        ),
        topic="weekly_dispatch",
        data={
            "type": "weekly_dispatch",
            "route": "/trends",
        },
    )
    try:
        sender(payload)
        return payload
    except Exception as exc:
        log.warning("fcm_weekly_digest_failed err=%s", exc)
        return None
