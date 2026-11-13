"""Server-side Pro clear-sky + bright-target backyard alert matching and dispatch."""

from __future__ import annotations

import logging
from collections.abc import Callable, Sequence
from typing import Any

from skyalerts_functions.notifications import NotificationPayload, SendFn, _default_send

log = logging.getLogger("skyalerts_functions.pro_alerts")

SCOPE_LIMITING_MAG: dict[str, float] = {
    "binoculars_10x50": 9.5,
    "visual_8": 14.0,
    "seestar_s30": 15.5,
    "dwarf_3": 15.8,
    "seestar_s50": 16.5,
    "unistellar": 17.5,
    "astrograph_8": 19.0,
}

DEFAULT_SCOPE_LIMITING_MAG = 16.5


def max_transit_altitude_deg(latitude_deg: float, dec_deg: float) -> float:
    """Upper culmination altitude above the horizon in degrees."""
    return 90.0 - abs(latitude_deg - dec_deg)


def _target_magnitude(target: dict[str, Any]) -> float | None:
    raw = target.get("latest_mag")
    if raw is None:
        raw = target.get("peak_mag")
    if raw is None:
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def _target_dec(target: dict[str, Any]) -> float | None:
    raw = target.get("mean_dec")
    if raw is None:
        raw = target.get("dec")
    if raw is None:
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def evaluate_backyard_alert_match(
    user_doc: dict[str, Any],
    target: dict[str, Any],
    *,
    cloud_cover_pct: float = 0.0,
    min_altitude_deg: float = 25.0,
    max_cloud_cover_pct: float = 40.0,
) -> bool:
    """Returns True when a target is bright enough and clears horizon & clouds for the user."""
    rounded_lat = user_doc.get("rounded_lat")
    rounded_lon = user_doc.get("rounded_lon")
    if rounded_lat is None or rounded_lon is None:
        return False

    if float(cloud_cover_pct) > float(max_cloud_cover_pct):
        return False

    mag = _target_magnitude(target)
    if mag is None:
        return False

    max_peak_mag = user_doc.get("max_peak_mag")
    scope_preset = str(user_doc.get("scope_preset") or "")
    if max_peak_mag is not None and mag > float(max_peak_mag):
        return False
    scope_limit = SCOPE_LIMITING_MAG.get(scope_preset, DEFAULT_SCOPE_LIMITING_MAG)
    if mag > scope_limit:
        return False

    dec = _target_dec(target)
    if dec is None:
        return False

    return max_transit_altitude_deg(float(rounded_lat), dec) >= float(min_altitude_deg)


def dispatch_pro_backyard_alerts(
    db: Any,
    targets: Sequence[dict[str, Any]],
    *,
    send_fn: SendFn | None = None,
    cloud_cover_fn: Callable[[float, float], float] | None = None,
) -> list[NotificationPayload]:
    """Matches synced backyard profiles against bright targets; sends at most 1 push/user."""
    sender = send_fn or _default_send
    sent: list[NotificationPayload] = []

    eligible_targets = [t for t in targets if not t.get("is_artifact")]
    if not eligible_targets:
        return sent

    for snap in db.collection("users").stream():
        user_doc = snap.to_dict() or {}
        tokens = tuple(str(t) for t in (user_doc.get("fcm_tokens") or []) if t)
        lat = user_doc.get("rounded_lat")
        lon = user_doc.get("rounded_lon")
        if not tokens or lat is None or lon is None:
            continue

        cloud_pct = float(cloud_cover_fn(float(lat), float(lon))) if cloud_cover_fn else 0.0
        matches = [
            t
            for t in eligible_targets
            if evaluate_backyard_alert_match(user_doc, t, cloud_cover_pct=cloud_pct)
        ]
        if not matches:
            continue

        matches.sort(key=lambda t: _target_magnitude(t) or 99.0)
        top = matches[0]
        oid = str(top.get("oid") or "Backyard Target")
        top_mag = _target_magnitude(top)
        mag_note = f"mag {top_mag:.1f}" if top_mag is not None else "observable"
        extra_note = f" (+{len(matches) - 1} more)" if len(matches) > 1 else ""

        payload = NotificationPayload(
            title=f"Clear-sky backyard alert: {oid}{extra_note}",
            body=f"{oid} ({mag_note}) clears your horizon tonight ({cloud_pct:.0f}% clouds).",
            tokens=tokens,
            data={
                "type": "pro_backyard",
                "oid": oid,
                "survey": str(top.get("survey") or "ztf"),
                "route": "/tonight",
            },
        )
        try:
            sender(payload)
            sent.append(payload)
        except Exception as exc:
            log.warning("fcm_pro_backyard_failed uid=%s err=%s", getattr(snap, "id", "?"), exc)

    return sent
