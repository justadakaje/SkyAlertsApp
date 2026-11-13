"""Core orchestration functions for daily ingest, weekly digest, and admin audit checks."""

from __future__ import annotations

import logging
import os
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from typing import Any

from skyalerts_digest.config import DigestConfig
from skyalerts_digest.podcast import render_podcast
from skyalerts_digest.render import render_html, render_markdown
from skyalerts_digest.send import format_subject
from skyalerts_digest.send import send_digest as send_resend_digest
from skyalerts_ingest.alerce_client import AlerceClient
from skyalerts_ingest.ingest import SOURCES, Config, Source
from skyalerts_ingest.ingest import run as run_ingest
from skyalerts_ingest.sso import SkyBotClient

from skyalerts_functions.bright_targets import collect_bright_targets
from skyalerts_functions.firestore_store import FirestoreStore
from skyalerts_functions.horizons import fetch_all_ephemerides
from skyalerts_functions.notifications import (
    SendFn,
    notify_bookmarked_updates,
    notify_matched_asteroids,
    notify_new_transients,
    notify_weekly_digest,
)

log = logging.getLogger("skyalerts_functions.pipeline")


def execute_daily_pipeline(
    db: Any,
    *,
    config: Config | None = None,
    surveys: tuple[str, ...] = ("lsst", "ztf"),
    sources: Sequence[Source] = SOURCES,
    alerce_client: AlerceClient | None = None,
    skybot_client: SkyBotClient | None = None,
    send_fn: SendFn | None = None,
    ephemerides_fn: Callable[[], dict[str, dict[str, Any] | None]] | None = None,
    bright_targets_fn: Callable[[], list[dict[str, Any]]] | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Runs daily ingest + SkyBoT + bright targets + Horizons + rollups + FCM."""
    cfg = config or Config.from_env()
    fs_store = FirestoreStore(db, now_fn=(lambda: now) if now is not None else None)

    own_alerce = alerce_client is None
    a_client = alerce_client or AlerceClient(min_interval=0.2)
    own_skybot = skybot_client is None
    s_client = skybot_client or SkyBotClient()

    try:
        run_res = run_ingest(
            fs_store,  # type: ignore[arg-type]
            a_client,
            trigger="cron",
            surveys=surveys,
            sources=sources,
            cfg=cfg,
            now=now,
        )
        sso_res = fs_store.identify_asteroids(s_client)
        bright_items = (
            bright_targets_fn()
            if bright_targets_fn is not None
            else collect_bright_targets(now=now)
        )
        bright_upserted = fs_store.upsert_bright_targets(bright_items)
        ephemerides = (
            ephemerides_fn() if ephemerides_fn is not None else fetch_all_ephemerides(now=now)
        )
        rollups = fs_store.compute_and_save_rollups(now=now, solar_ephemerides=ephemerides)

        transient_pushes = notify_new_transients(db, fs_store.last_touched_objects, send_fn=send_fn)
        bookmark_pushes = notify_bookmarked_updates(
            db, fs_store.last_touched_objects, send_fn=send_fn
        )
        asteroid_pushes = notify_matched_asteroids(fs_store.last_matched_asteroids, send_fn=send_fn)

        return {
            "ingest_run": run_res.as_dict(),
            "sso_counts": sso_res.as_dict(),
            "bright_targets_upserted": bright_upserted,
            "notifications_sent": {
                "transients": len(transient_pushes),
                "bookmarks": len(bookmark_pushes),
                "solar_matched": len(asteroid_pushes),
            },
            "total_objects": rollups["overview"]["total_objects"],
        }
    finally:
        if own_alerce:
            a_client.close()
        if own_skybot:
            s_client.close()


def execute_weekly_digest(
    db: Any,
    *,
    send_email: bool = True,
    send_fcm: bool = True,
    send_fn: SendFn | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Selects and renders the weekly Sky Dispatch; optionally emails and pushes FCM."""
    ref_now = now or datetime.now(UTC)
    fs_store = FirestoreStore(db, now_fn=lambda: ref_now)
    digest = fs_store.select_digest(ref_now)
    subject = format_subject(digest)
    markdown = render_markdown(digest)
    html = render_html(digest)
    podcast = render_podcast(digest)

    email_id: str | None = None
    resend_key = os.environ.get("RESEND_API_KEY", "").strip()
    digest_from = os.environ.get("DIGEST_FROM", "").strip()
    digest_to = tuple(
        addr.strip() for addr in os.environ.get("DIGEST_TO", "").split(",") if addr.strip()
    )
    if send_email and resend_key and digest_from and digest_to:
        cfg = DigestConfig(
            database_url="",
            resend_api_key=resend_key,
            digest_from=digest_from,
            digest_to=digest_to,
        )
        res = send_resend_digest(digest, cfg)
        email_id = res.id

    fcm_sent = False
    if send_fcm:
        transients_cnt = digest.stats.count_for("transients")
        window_label = (
            f"{digest.week_start.strftime('%b %d')}–{digest.week_end.strftime('%b %d, %Y')}"
        )
        payload = notify_weekly_digest(
            window_label=window_label,
            total_active=digest.stats.new_objects,
            transients_count=transients_cnt,
            send_fn=send_fn,
        )
        fcm_sent = payload is not None

    return {
        "subject": subject,
        "markdown": markdown,
        "html": html,
        "podcast": podcast,
        "email_id": email_id,
        "fcm_sent": fcm_sent,
        "total_active": digest.stats.new_objects,
    }


OWNER_ADMIN_EMAILS = frozenset({"kjhenseler@gmail.com", "kenneth@henseler.email"})


def require_admin_and_audit(
    db: Any,
    auth_context: dict[str, Any] | None,
    *,
    action: str,
    target: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> str:
    """Verifies `admin == true` claim (or owner email) and writes an audit_log entry."""
    if not auth_context:
        raise PermissionError("Authentication required for admin action.")
    token = auth_context.get("token") or {}
    uid = str(auth_context.get("uid") or "")
    email = str(token.get("email") or "").strip().lower()
    is_owner_email = email in OWNER_ADMIN_EMAILS
    is_admin = bool(token.get("admin") is True) or is_owner_email
    if not is_admin or not uid:
        raise PermissionError("Admin claim required for this operation.")
    if is_owner_email and token.get("admin") is not True:
        try:
            from firebase_admin import auth as fb_auth

            fb_auth.update_user(uid, email_verified=True)
            fb_auth.set_custom_user_claims(uid, {"admin": True})
        except Exception:
            pass

    now_iso = datetime.now(UTC).isoformat()
    audit_id = f"{int(datetime.now(UTC).timestamp() * 1000)}_{action}"
    db.collection("audit_log").document(audit_id).set(
        {
            "occurred_at": now_iso,
            "actor": str(token.get("email") or token.get("name") or uid),
            "uid": uid,
            "action": action,
            "target": target,
            "metadata": metadata or {},
        }
    )
    return uid
