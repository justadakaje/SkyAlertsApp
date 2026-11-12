"""Cloud Functions for Firebase (2nd Gen, Python 3.12) entrypoints for SkyAlerts."""

from __future__ import annotations

from typing import Any

from skyalerts_ingest.sso import SkyBotClient

from skyalerts_functions.firestore_store import FirestoreStore
from skyalerts_functions.notifications import notify_matched_asteroids
from skyalerts_functions.pipeline import (
    execute_daily_pipeline,
    execute_weekly_digest,
    require_admin_and_audit,
)


def _get_firestore_db() -> Any:
    import firebase_admin
    from firebase_admin import firestore

    if not firebase_admin._apps:
        firebase_admin.initialize_app()
    return firestore.client()


try:
    from firebase_functions import https_fn, scheduler_fn

    @scheduler_fn.on_schedule(
        schedule="17 6 * * *",
        timezone=scheduler_fn.Timezone("UTC"),
        memory=512,
        timeout_sec=540,
    )
    def daily_ingest_and_identify(event: scheduler_fn.ScheduledEvent) -> None:
        del event
        db = _get_firestore_db()
        execute_daily_pipeline(db)

    @scheduler_fn.on_schedule(
        schedule="23 14 * * 0",
        timezone=scheduler_fn.Timezone("UTC"),
        memory=256,
        timeout_sec=180,
    )
    def weekly_digest_and_broadcast(event: scheduler_fn.ScheduledEvent) -> None:
        del event
        db = _get_firestore_db()
        execute_weekly_digest(db, send_email=True, send_fcm=True)

    def _guard_admin(
        db: Any,
        req: https_fn.CallableRequest[Any],
        *,
        action: str,
        target: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        auth_ctx = {"uid": req.auth.uid, "token": req.auth.token} if req.auth is not None else None
        try:
            return require_admin_and_audit(
                db,
                auth_ctx,
                action=action,
                target=target,
                metadata=metadata,
            )
        except PermissionError as exc:
            code = (
                https_fn.FunctionsErrorCode.UNAUTHENTICATED
                if req.auth is None
                else https_fn.FunctionsErrorCode.PERMISSION_DENIED
            )
            raise https_fn.HttpsError(code=code, message=str(exc)) from exc

    @https_fn.on_call(memory=512, timeout_sec=300)
    def trigger_ingest(req: https_fn.CallableRequest[Any]) -> dict[str, Any]:
        db = _get_firestore_db()
        survey = (req.data or {}).get("survey") if isinstance(req.data, dict) else None
        _guard_admin(
            db,
            req,
            action="ingest.rerun",
            target=str(survey or "all"),
            metadata={"survey": survey},
        )
        surveys = (survey,) if survey in ("lsst", "ztf") else ("lsst", "ztf")
        return execute_daily_pipeline(db, surveys=surveys)

    @https_fn.on_call(memory=256, timeout_sec=180)
    def trigger_identify(req: https_fn.CallableRequest[Any]) -> dict[str, Any]:
        db = _get_firestore_db()
        _guard_admin(
            db,
            req,
            action="identify.rerun",
            target="skybot",
        )
        fs_store = FirestoreStore(db)
        with SkyBotClient() as s_client:
            counts = fs_store.identify_asteroids(s_client)
        fs_store.compute_and_save_rollups()
        notify_matched_asteroids(fs_store.last_matched_asteroids)
        return {"sso_counts": counts.as_dict()}

    @https_fn.on_call(memory=256, timeout_sec=120)
    def preview_digest(req: https_fn.CallableRequest[Any]) -> dict[str, Any]:
        db = _get_firestore_db()
        _guard_admin(
            db,
            req,
            action="digest.preview",
            target="weekly",
        )
        return execute_weekly_digest(db, send_email=False, send_fcm=False)

    @https_fn.on_call(memory=256, timeout_sec=180)
    def send_digest(req: https_fn.CallableRequest[Any]) -> dict[str, Any]:
        db = _get_firestore_db()
        _guard_admin(
            db,
            req,
            action="digest.send",
            target="weekly",
        )
        return execute_weekly_digest(db, send_email=True, send_fcm=True)

except ImportError:
    pass
