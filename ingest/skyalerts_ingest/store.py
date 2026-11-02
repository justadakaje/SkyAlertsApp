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

from .normalize import ClassificationRow, DetectionRow, ObjectRow

LOCK_KEY = 0x5C7A1E28
# A run is considered alive for this long. Vercel kills functions at 300 s, so a
# 'running' row older than this belongs to a dead invocation.
LEASE_SECONDS = 600

SKIP_CLASSES: list[str] = ["bogus", "asteroid"]
TIER1_CLASSES: list[str] = ["SN", "SNIa", "SNIbc", "SNII", "SLSN", "TDE", "KN", "CV/Nova"]
TIER3_CLASSES: list[str] = ["AGN", "QSO", "Blazar"]

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

UPSERT_DETECTION = """
INSERT INTO detections (survey, oid, measurement_id, mjd, band, mag, mag_err,
                        flux_njy, flux_err_njy, raw)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
ON CONFLICT (survey, oid, measurement_id) DO UPDATE SET
    mjd          = EXCLUDED.mjd,
    band         = EXCLUDED.band,
    mag          = EXCLUDED.mag,
    mag_err      = EXCLUDED.mag_err,
    flux_njy     = EXCLUDED.flux_njy,
    flux_err_njy = EXCLUDED.flux_err_njy,
    raw          = EXCLUDED.raw,
    ingested_at  = now()
"""

ENRICHMENT_CANDIDATES = """
SELECT survey, oid
  FROM objects
 WHERE last_ingest_run_id = %s
   AND (top_class IS NULL OR NOT (top_class = ANY(%s)))
   AND (enriched_lastmjd IS NULL OR lastmjd > enriched_lastmjd)
 ORDER BY CASE
              WHEN top_class = ANY(%s) THEN 1
              WHEN top_class = ANY(%s) THEN 3
              ELSE 2
          END ASC,
          top_probability DESC NULLS LAST,
          lastmjd DESC NULLS LAST
 LIMIT %s
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
        objects_enriched: int = 0,
        detections_upserted: int = 0,
        requests: int,
        errors: list[dict[str, Any]],
        duration_ms: int,
        coverage: dict[str, Any] | None = None,
    ) -> None:
        self.conn.execute(
            """UPDATE ingest_runs SET finished_at = now(), status = %s, objects_seen = %s,
                   objects_upserted = %s, classifications_upserted = %s,
                   objects_enriched = %s, detections_upserted = %s, requests = %s,
                   error_count = %s, errors = %s, duration_ms = %s, coverage = %s
               WHERE id = %s""",
            (
                status,
                objects_seen,
                objects_upserted,
                classifications_upserted,
                objects_enriched,
                detections_upserted,
                requests,
                len(errors),
                Jsonb(errors[:50]),  # cap stored detail
                duration_ms,
                Jsonb(coverage or {}),
                run_id,
            ),
        )

    def source_watermark(self, source: str) -> float | None:
        """Newest lastmjd the source saw in the last finished run that advanced its window.

        Data time, not wall clock: if ALeRCE stalls, the window waits for it. Runs that
        failed, were abandoned, or didn't advance this source (budget hit, source error)
        are skipped, so their unfetched range is re-covered next time."""
        row = self.conn.execute(
            """SELECT (coverage -> %s ->> 'newest_mjd')::float8 FROM ingest_runs
                WHERE status IN ('success', 'partial')
                  AND (coverage -> %s ->> 'advances')::boolean
                ORDER BY id DESC LIMIT 1""",
            (source, source),
        ).fetchone()
        if row is None or row[0] is None:
            return None
        return float(row[0])

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

    def upsert_detections(self, detections: Sequence[DetectionRow]) -> int:
        if not detections:
            return 0
        with self.conn.transaction(), self.conn.cursor() as cur:
            cur.executemany(UPSERT_DETECTION, _detection_params(detections))
        return len(detections)

    def enrichment_candidates(self, run_id: int, limit: int) -> list[tuple[str, str]]:
        if limit <= 0:
            return []
        rows = self.conn.execute(
            ENRICHMENT_CANDIDATES,
            (run_id, SKIP_CLASSES, TIER1_CLASSES, TIER3_CLASSES, limit),
        ).fetchall()
        return [(str(r[0]), str(r[1])) for r in rows]

    def enrich_object(
        self,
        survey: str,
        oid: str,
        detections: Sequence[DetectionRow],
        classifications: Sequence[ClassificationRow],
    ) -> tuple[int, int]:
        with self.conn.transaction(), self.conn.cursor() as cur:
            if detections:
                cur.executemany(UPSERT_DETECTION, _detection_params(detections))
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
            cur.execute(
                "UPDATE objects SET enriched_at = now(), enriched_lastmjd = lastmjd"
                " WHERE survey = %s AND oid = %s",
                (survey, oid),
            )
        return len(detections), len(classifications)


def _detection_params(detections: Sequence[DetectionRow]) -> list[tuple[Any, ...]]:
    return [
        (
            d.survey,
            d.oid,
            d.measurement_id,
            d.mjd,
            d.band,
            d.mag,
            d.mag_err,
            d.flux_njy,
            d.flux_err_njy,
            Jsonb(d.raw, dumps=_dumps),
        )
        for d in detections
    ]


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
