"""Idempotent Neon Postgres -> Cloud Firestore backfill utility.

Copies all existing rows from Neon (`objects`, `detections`, `classifications`,
`sso_identifications`, `ingest_runs`, `audit_log`) into Cloud Firestore using the
two-tier document layout and immediately computes `rollups/overview` and
`rollups/trends_90d`.
"""

from __future__ import annotations

import argparse
import logging
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from skyalerts_digest.classes import ARTIFACT_CLASS, TRANSIENT_CLASSES

from skyalerts_functions.firestore_store import FirestoreStore, object_doc_id

log = logging.getLogger("skyalerts_functions.backfill")


@dataclass(frozen=True, slots=True)
class BackfillSummary:
    objects_migrated: int
    details_migrated: int
    sso_migrated: int
    runs_migrated: int
    audit_logs_migrated: int


def _compute_notability_score(
    *,
    top_class: str | None,
    top_probability: float | None,
    is_artifact: bool,
    n_detections: int | None,
) -> float:
    if is_artifact or top_class == ARTIFACT_CLASS:
        return -1.0
    tier_rank = 2 if top_class in TRANSIENT_CLASSES else (1 if top_class is not None else 0)
    prob = float(top_probability or 0.0)
    ndet = min(int(n_detections or 0), 999999)
    return round(tier_rank * 100.0 + prob * 10.0 + ndet / 1_000_000.0, 6)


def backfill_neon_to_firestore(
    pg_conn: Any,
    fs_store: FirestoreStore,
    *,
    now: datetime | None = None,
    solar_ephemerides: dict[str, dict[str, Any] | None] | None = None,
) -> BackfillSummary:
    """Migrates all Postgres tables into Firestore idempotently and rebuilds rollups."""
    db = fs_store.db

    # 1. Fetch SSO identifications keyed by (survey, oid)
    sso_by_key: dict[tuple[str, str], dict[str, Any]] = {}
    with pg_conn.cursor() as cur:
        cur.execute(
            """
            SELECT survey, oid, status, object_name, object_number, object_class,
                   sep_arcsec, v_mag, epoch_mjd, checked_at, error
            FROM sso_identifications
            """
        )
        for row in cur.fetchall():
            (
                survey,
                oid,
                status,
                object_name,
                object_number,
                object_class,
                sep_arcsec,
                v_mag,
                epoch_mjd,
                checked_at,
                error,
            ) = row
            sso_by_key[(str(survey), str(oid))] = {
                "status": str(status),
                "sso_name": object_name,
                "object_name": object_name,
                "sso_number": int(object_number) if object_number is not None else None,
                "object_number": int(object_number) if object_number is not None else None,
                "sso_class": object_class,
                "object_class": object_class,
                "sep_arcsec": float(sep_arcsec) if sep_arcsec is not None else None,
                "predicted_mag": float(v_mag) if v_mag is not None else None,
                "v_mag": float(v_mag) if v_mag is not None else None,
                "obs_mjd": float(epoch_mjd) if epoch_mjd is not None else None,
                "epoch_mjd": float(epoch_mjd) if epoch_mjd is not None else None,
                "queried_at": (
                    checked_at.isoformat() if hasattr(checked_at, "isoformat") else str(checked_at)
                ),
                "error": error,
            }

    # 2. Fetch detections grouped by (survey, oid)
    dets_by_key: dict[tuple[str, str], list[dict[str, Any]]] = {}
    with pg_conn.cursor() as cur:
        cur.execute(
            """
            SELECT survey, oid, measurement_id, mjd, band, mag, mag_err, flux_njy, flux_err_njy
            FROM detections
            ORDER BY survey, oid, mjd ASC
            """
        )
        for row in cur.fetchall():
            survey, oid, mid, mjd, band, mag, mag_err, flux_njy, flux_err_njy = row
            dets_by_key.setdefault((str(survey), str(oid)), []).append(
                {
                    "measurement_id": str(mid),
                    "mjd": float(mjd),
                    "band": str(band),
                    "mag": float(mag) if mag is not None else None,
                    "mag_err": float(mag_err) if mag_err is not None else None,
                    "flux_njy": float(flux_njy) if flux_njy is not None else None,
                    "flux_err_njy": float(flux_err_njy) if flux_err_njy is not None else None,
                }
            )

    # 3. Fetch classifications grouped by (survey, oid)
    cls_by_key: dict[tuple[str, str], list[dict[str, Any]]] = {}
    with pg_conn.cursor() as cur:
        cur.execute(
            """
            SELECT survey, oid, classifier_name, classifier_version,
                   class_name, probability, ranking
            FROM classifications
            ORDER BY survey, oid, classifier_name, ranking ASC
            """
        )
        for row in cur.fetchall():
            survey, oid, cname, cver, class_name, prob, ranking = row
            cls_by_key.setdefault((str(survey), str(oid)), []).append(
                {
                    "classifier_name": str(cname),
                    "classifier_version": str(cver),
                    "class_name": str(class_name),
                    "probability": float(prob),
                    "ranking": int(ranking),
                }
            )

    # 4. Migrate objects + detail/enrichment subdocuments
    objects_migrated = 0
    details_migrated = 0
    with pg_conn.cursor() as cur:
        cur.execute(
            """
            SELECT survey, oid, ra_deg, dec_deg, first_mjd, last_mjd, n_detections,
                   top_class, top_probability, classifier_name, classifier_version,
                   is_artifact, enriched_at, updated_at
            FROM objects
            """
        )
        obj_rows = cur.fetchall()

    for row in obj_rows:
        (
            survey,
            oid,
            ra_deg,
            dec_deg,
            first_mjd,
            last_mjd,
            n_detections,
            top_class,
            top_probability,
            classifier_name,
            classifier_version,
            is_artifact,
            enriched_at,
            updated_at,
        ) = row
        key = (str(survey), str(oid))
        doc_id = object_doc_id(str(survey), str(oid))
        dets = dets_by_key.get(key, [])
        clss = cls_by_key.get(key, [])
        sso = sso_by_key.get(key)

        peak_mag: float | None = None
        for d in dets:
            m = d.get("mag")
            if m is not None and (peak_mag is None or float(m) < peak_mag):
                peak_mag = float(m)

        is_art = bool(is_artifact) or top_class == ARTIFACT_CLASS
        tier = (
            2
            if is_art
            else (0 if top_class in TRANSIENT_CLASSES else (1 if top_class is not None else 1))
        )
        payload: dict[str, Any] = {
            "survey": str(survey),
            "oid": str(oid),
            "meanra": float(ra_deg),
            "meandec": float(dec_deg),
            "ra_deg": float(ra_deg),
            "dec_deg": float(dec_deg),
            "firstmjd": float(first_mjd),
            "lastmjd": float(last_mjd),
            "first_mjd": float(first_mjd),
            "last_mjd": float(last_mjd),
            "ndet": int(n_detections) if n_detections is not None else 0,
            "n_detections": int(n_detections) if n_detections is not None else 0,
            "top_class": top_class,
            "top_probability": float(top_probability) if top_probability is not None else None,
            "top_classifier": classifier_name,
            "top_classifier_version": classifier_version,
            "classifier_name": classifier_name,
            "classifier_version": classifier_version,
            "is_artifact": is_art,
            "tier": tier,
            "notability_score": _compute_notability_score(
                top_class=top_class,
                top_probability=float(top_probability) if top_probability is not None else None,
                is_artifact=is_art,
                n_detections=int(n_detections) if n_detections is not None else 0,
            ),
            "peak_mag": peak_mag,
            "enriched_at": (
                enriched_at.isoformat()
                if enriched_at is not None and hasattr(enriched_at, "isoformat")
                else (str(enriched_at) if enriched_at is not None else None)
            ),
            "updated_at": (
                updated_at.isoformat()
                if updated_at is not None and hasattr(updated_at, "isoformat")
                else datetime.now(UTC).isoformat()
            ),
        }
        if sso is not None:
            payload["sso"] = sso

        obj_ref = db.collection("objects").document(doc_id)
        obj_ref.set(payload, merge=True)
        objects_migrated += 1

        if dets or clss or enriched_at is not None:
            obj_ref.collection("detail").document("enrichment").set(
                {
                    "detections": dets,
                    "classifications": clss,
                    "enriched_at": payload["enriched_at"],
                }
            )
            details_migrated += 1

    # 5. Migrate ingest_runs -> admin_runs
    runs_migrated = 0
    with pg_conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, source, started_at, finished_at, status,
                   objects_fetched, objects_upserted, detections_upserted,
                   classifications_upserted, error_count, error_sample
            FROM ingest_runs
            ORDER BY id ASC
            """
        )
        run_rows = cur.fetchall()

    for r in run_rows:
        (
            run_id,
            source,
            started_at,
            finished_at,
            status,
            objects_fetched,
            objects_upserted,
            detections_upserted,
            classifications_upserted,
            error_count,
            error_sample,
        ) = r
        db.collection("admin_runs").document(str(run_id)).set(
            {
                "id": int(run_id),
                "source": str(source),
                "started_at": (
                    started_at.isoformat() if hasattr(started_at, "isoformat") else str(started_at)
                ),
                "finished_at": (
                    finished_at.isoformat()
                    if finished_at is not None and hasattr(finished_at, "isoformat")
                    else (str(finished_at) if finished_at is not None else None)
                ),
                "status": str(status),
                "objects_fetched": int(objects_fetched or 0),
                "objects_upserted": int(objects_upserted or 0),
                "detections_upserted": int(detections_upserted or 0),
                "classifications_upserted": int(classifications_upserted or 0),
                "error_count": int(error_count or 0),
                "error_sample": error_sample,
            }
        )
        runs_migrated += 1

    # 6. Migrate audit_log -> audit_log
    audit_logs_migrated = 0
    with pg_conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, occurred_at, actor, action, target, ip, user_agent, metadata
            FROM audit_log
            ORDER BY id ASC
            """
        )
        audit_rows = cur.fetchall()

    for a in audit_rows:
        aid, occurred_at, actor, action, target, ip, user_agent, metadata = a
        db.collection("audit_log").document(str(aid)).set(
            {
                "id": int(aid),
                "occurred_at": (
                    occurred_at.isoformat()
                    if hasattr(occurred_at, "isoformat")
                    else str(occurred_at)
                ),
                "actor": str(actor),
                "action": str(action),
                "target": target,
                "ip": str(ip) if ip is not None else None,
                "user_agent": user_agent,
                "metadata": metadata if isinstance(metadata, dict) else {},
            }
        )
        audit_logs_migrated += 1

    # 7. Compute initial rollups/overview and rollups/trends_90d
    fs_store.compute_and_save_rollups(now=now, solar_ephemerides=solar_ephemerides)

    return BackfillSummary(
        objects_migrated=objects_migrated,
        details_migrated=details_migrated,
        sso_migrated=len(sso_by_key),
        runs_migrated=runs_migrated,
        audit_logs_migrated=audit_logs_migrated,
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Idempotent backfill from Neon Postgres into Cloud Firestore."
    )
    parser.add_argument(
        "--database-url",
        default=os.environ.get("DATABASE_URL"),
        help="Neon Postgres connection string (defaults to DATABASE_URL env var).",
    )
    parser.add_argument(
        "--project",
        default=os.environ.get("GCLOUD_PROJECT", "skyalerts-app"),
        help="Firebase / GCP project ID.",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    if not args.database_url:
        log.error("DATABASE_URL is required for backfill.")
        return 2

    import firebase_admin
    import psycopg
    from firebase_admin import firestore

    if not firebase_admin._apps:
        firebase_admin.initialize_app(options={"projectId": args.project})
    db = firestore.client()
    fs_store = FirestoreStore(db)

    with psycopg.connect(args.database_url) as pg_conn:
        summary = backfill_neon_to_firestore(pg_conn, fs_store)
    log.info("backfill_complete summary=%s", summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
