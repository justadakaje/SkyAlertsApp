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

LOCK_KEY = 0x5C7A1E28
# A run is considered alive for this long. Vercel kills functions at 300 s, so a
# 'running' row older than this belongs to a dead invocation.
LEASE_SECONDS = 600

_TAKE_TOP = (
    "(EXCLUDED.top_class IS NOT NULL AND (objects.top_classifier IS DISTINCT FROM "
    "'lc_classifier' OR EXCLUDED.top_classifier = 'lc_classifier'))"
)

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
    -- Top class precedence: never let a non-lc classifier overwrite an lc result.
    top_class              = CASE WHEN {take} THEN EXCLUDED.top_class
                                  ELSE objects.top_class END,
    top_classifier         = CASE WHEN {take} THEN EXCLUDED.top_classifier
                                  ELSE objects.top_classifier END,
    top_classifier_version = CASE WHEN {take} THEN EXCLUDED.top_classifier_version
                                  ELSE objects.top_classifier_version END,
    top_probability        = CASE WHEN {take} THEN EXCLUDED.top_probability
                                  ELSE objects.top_probability END,
    raw                    = EXCLUDED.raw,
    last_ingested_at       = now(),
    last_ingest_run_id     = EXCLUDED.last_ingest_run_id
""".replace("{take}", _TAKE_TOP)

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

    # -- runs / lease ------------------------------------------------------
    def start_run(self, trigger: str, surveys: Sequence[str]) -> int | None:
        """Claim the ingest lease and open a run, or return None if a live run exists.

        Uses a *transaction-scoped* advisory lock (safe behind PgBouncer
        transaction pooling) to serialise the check-and-insert. Stale 'running'
        rows from killed invocations are closed as failed.
        """
        with self.conn.transaction():
            self.conn.execute("SELECT pg_advisory_xact_lock(%s)", (LOCK_KEY,))
            self.conn.execute(
                """UPDATE ingest_runs
                      SET status = 'failed', finished_at = now(), error_count = error_count + 1,
                          errors = errors || '[{"source": "lease", "error": "abandoned run"}]'
                    WHERE status = 'running'
                      AND started_at < now() - make_interval(secs => %s)""",
                (LEASE_SECONDS,),
            )
            live = self.conn.execute(
                "SELECT 1 FROM ingest_runs WHERE status = 'running' LIMIT 1"
            ).fetchone()
            if live:
                return None
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
        """Start time (as MJD) of the last fully successful run. Partial runs don't
        advance the catch-up window, so their gaps get re-fetched next time."""
        row = self.conn.execute(
            "SELECT extract(epoch FROM max(started_at)) FROM ingest_runs WHERE status = 'success'"
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


def _clean_str(s: str) -> str:
    # jsonb rejects NUL and unpaired UTF-16 surrogates.
    return s.replace("\x00", "").encode("utf-8", "replace").decode("utf-8").replace("\ufffd", "")


def _clean(v: Any) -> Any:
    """Make upstream JSON safe for jsonb: NaN/Inf -> null, strip NUL bytes."""
    if isinstance(v, float):
        return v if math.isfinite(v) else None
    if isinstance(v, str):
        return _clean_str(v)
    if isinstance(v, dict):
        return {_clean_str(str(k)): _clean(x) for k, x in v.items()}
    if isinstance(v, list):
        return [_clean(x) for x in v]
    return v


def _dumps(obj: Any) -> str:
    return json.dumps(_clean(obj), default=str, allow_nan=False)
