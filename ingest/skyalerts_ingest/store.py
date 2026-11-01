"""Postgres persistence for the ingest job (runs as skyalerts_ingest).

All statements are parameterized. Upserts are idempotent: re-running the same
batch changes only last_ingested_at / last_ingest_run_id.
"""

from __future__ import annotations

import json
import math
from collections.abc import Sequence
from typing import Any

import psycopg
from psycopg.types.json import Jsonb

from .normalize import ClassificationRow, ObjectRow

LOCK_KEY = 0x5C7A1E28  # one ingest at a time across overlapping/duplicate cron calls

UPSERT_OBJECT = """
INSERT INTO objects (survey, oid, meanra, meandec, firstmjd, lastmjd, ndet, n_forced, stellar,
                     top_class, top_classifier, top_classifier_version, top_probability,
                     raw, last_ingest_run_id)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
ON CONFLICT (survey, oid) DO UPDATE SET
    meanra                 = COALESCE(EXCLUDED.meanra, objects.meanra),
    meandec                = COALESCE(EXCLUDED.meandec, objects.meandec),
    firstmjd               = LEAST(objects.firstmjd, EXCLUDED.firstmjd),
    lastmjd                = GREATEST(objects.lastmjd, EXCLUDED.lastmjd),
    ndet                   = COALESCE(EXCLUDED.ndet, objects.ndet),
    n_forced               = COALESCE(EXCLUDED.n_forced, objects.n_forced),
    stellar                = COALESCE(EXCLUDED.stellar, objects.stellar),
    top_class              = COALESCE(EXCLUDED.top_class, objects.top_class),
    top_classifier         = CASE WHEN EXCLUDED.top_class IS NULL THEN objects.top_classifier
                                  ELSE EXCLUDED.top_classifier END,
    top_classifier_version = CASE WHEN EXCLUDED.top_class IS NULL
                                  THEN objects.top_classifier_version
                                  ELSE EXCLUDED.top_classifier_version END,
    top_probability        = CASE WHEN EXCLUDED.top_class IS NULL THEN objects.top_probability
                                  ELSE EXCLUDED.top_probability END,
    raw                    = EXCLUDED.raw,
    last_ingested_at       = now(),
    last_ingest_run_id     = EXCLUDED.last_ingest_run_id
"""

UPSERT_CLASSIFICATION = """
INSERT INTO classifications (survey, oid, classifier_name, classifier_version, class_name,
                             probability, ranking)
VALUES (%s, %s, %s, %s, %s, %s, %s)
ON CONFLICT (survey, oid, classifier_name, classifier_version, class_name) DO UPDATE SET
    probability = EXCLUDED.probability,
    ranking     = EXCLUDED.ranking,
    ingested_at = now()
"""


class Store:
    def __init__(self, conn: psycopg.Connection) -> None:
        self.conn = conn

    @classmethod
    def connect(cls, dsn: str) -> Store:
        conn = psycopg.connect(
            dsn, autocommit=True, connect_timeout=15, application_name="skyalerts-ingest"
        )
        return cls(conn)

    def close(self) -> None:
        self.conn.close()

    # -- locking ----------------------------------------------------------
    def try_lock(self) -> bool:
        return bool(self.conn.execute("SELECT pg_try_advisory_lock(%s)", (LOCK_KEY,)).fetchone()[0])

    def unlock(self) -> None:
        self.conn.execute("SELECT pg_advisory_unlock(%s)", (LOCK_KEY,))

    # -- runs -------------------------------------------------------------
    def start_run(self, trigger: str, surveys: Sequence[str]) -> int:
        row = self.conn.execute(
            "INSERT INTO ingest_runs (trigger, surveys) VALUES (%s, %s) RETURNING id",
            (trigger, list(surveys)),
        ).fetchone()
        return int(row[0])

    def finish_run(
        self,
        run_id: int,
        *,
        status: str,
        objects_seen: int,
        objects_upserted: int,
        classifications_upserted: int,
        requests: int,
        errors: list[dict[str, Any]],
        duration_ms: int,
    ) -> None:
        self.conn.execute(
            """UPDATE ingest_runs SET finished_at = now(), status = %s, objects_seen = %s,
                   objects_upserted = %s, classifications_upserted = %s, requests = %s,
                   error_count = %s, errors = %s, duration_ms = %s
               WHERE id = %s""",
            (
                status,
                objects_seen,
                objects_upserted,
                classifications_upserted,
                requests,
                len(errors),
                Jsonb(errors[:50]),  # cap stored detail
                duration_ms,
                run_id,
            ),
        )

    def last_success_mjd_floor(self) -> float | None:
        """Max lastmjd seen as of the last successful/partial run (for catch-up windows)."""
        row = self.conn.execute(
            """SELECT extract(epoch FROM max(started_at)) FROM ingest_runs
               WHERE status IN ('success', 'partial')"""
        ).fetchone()
        if row is None or row[0] is None:
            return None
        return float(row[0]) / 86400.0 + 40587.0

    # -- data -------------------------------------------------------------
    def upsert_batch(
        self,
        run_id: int,
        objects: Sequence[ObjectRow],
        classifications: Sequence[ClassificationRow],
    ) -> tuple[int, int]:
        if not objects:
            return 0, 0
        with self.conn.transaction(), self.conn.cursor() as cur:
            cur.executemany(
                UPSERT_OBJECT,
                [
                    (
                        o.survey,
                        o.oid,
                        o.meanra,
                        o.meandec,
                        o.firstmjd,
                        o.lastmjd,
                        o.ndet,
                        o.n_forced,
                        o.stellar,
                        o.top_class,
                        o.top_classifier,
                        o.top_classifier_version,
                        o.top_probability,
                        Jsonb(o.raw, dumps=_dumps),
                        run_id,
                    )
                    for o in objects
                ],
            )
            if classifications:
                cur.executemany(
                    UPSERT_CLASSIFICATION,
                    [
                        (
                            c.survey,
                            c.oid,
                            c.classifier_name,
                            c.classifier_version,
                            c.class_name,
                            c.probability,
                            c.ranking,
                        )
                        for c in classifications
                    ],
                )
        return len(objects), len(classifications)


def _clean(v: Any) -> Any:
    """Make upstream JSON safe for jsonb: NaN/Inf -> null, strip NUL bytes."""
    if isinstance(v, float):
        return v if math.isfinite(v) else None
    if isinstance(v, str):
        return v.replace("\x00", "")
    if isinstance(v, dict):
        return {str(k).replace("\x00", ""): _clean(x) for k, x in v.items()}
    if isinstance(v, list):
        return [_clean(x) for x in v]
    return v


def _dumps(obj: Any) -> str:
    return json.dumps(_clean(obj), default=str, allow_nan=False)
