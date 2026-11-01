"""Daily ingest: pull recently-updated ALeRCE objects, upsert them, and enrich top candidates.

    DATABASE_URL=... python -m skyalerts_ingest.ingest [--surveys lsst,ztf] [--trigger cli]

Strategy (fits Vercel Hobby: one run/day, 300 s max; see docs/decisions.md #13, #18):
- Page each source newest-first (order_by=lastmjd DESC) and stop once a page
  reaches objects older than the catch-up window, or the page cap / time budget.
- LSST list rows already carry the top classification.
- ZTF list rows only carry a class when filtered by classifier, so ZTF is
  paged once per classifier; stamp first, then lc (lc wins as top_class).
- Bounded enrichment: for up to enrich_max_objects priority candidates touched
  in this run (excluding bogus/asteroid, skipping already-current objects),
  fetch per-object detections (capped at 200 newest) and probabilities
  (top 3 per classifier version) within the shared time budget.
- Upserts are idempotent; a lease row in ingest_runs (claimed under a
  transaction-scoped advisory lock, so it is PgBouncer-safe) serialises runs.
- Run outcome: success | partial (budget/page cap hit, a source failed, rows
  rejected in list paging) | failed. Only success advances the catch-up window;
  enrichment errors or budget exhaustion are logged without demoting status.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from typing import Any

import psycopg

from . import logutil
from .alerce_client import AlerceClient, AlerceError
from .normalize import (
    ClassificationRow,
    DetectionRow,
    ObjectRow,
    normalize_detection,
    normalize_object,
    normalize_probability,
)
from .store import Store
from .summary import datetime_to_mjd

log = logging.getLogger("skyalerts.ingest")

# (survey, classifier filter or None). Order matters for ZTF top_class precedence.
SOURCES: list[tuple[str, str | None]] = [
    ("lsst", None),
    ("ztf", "stamp_classifier"),
    ("ztf", "lc_classifier"),
]

MAX_DETECTIONS = 200
MAX_PROB_RANK = 3


@dataclass
class Config:
    page_size: int = 100
    max_pages_per_source: int = 20
    default_lookback_days: float = 2.0
    max_lookback_days: float = 7.0
    time_budget_s: float = 240.0  # leave headroom under Vercel's 300 s
    enrich_max_objects: int = 40

    @classmethod
    def from_env(cls) -> Config:
        c = cls()
        c.page_size = int(os.getenv("INGEST_PAGE_SIZE", c.page_size))
        c.max_pages_per_source = int(os.getenv("INGEST_MAX_PAGES", c.max_pages_per_source))
        c.time_budget_s = float(os.getenv("INGEST_TIME_BUDGET_S", c.time_budget_s))
        c.enrich_max_objects = int(os.getenv("INGEST_ENRICH_MAX", c.enrich_max_objects))
        return c


@dataclass
class RunResult:
    run_id: int | None
    status: str
    objects_seen: int = 0
    objects_upserted: int = 0
    classifications_upserted: int = 0
    objects_enriched: int = 0
    detections_upserted: int = 0
    rejected: int = 0
    requests: int = 0
    errors: list[dict[str, Any]] = field(default_factory=list)
    duration_ms: int = 0

    def as_dict(self) -> dict[str, Any]:
        return {k: v for k, v in self.__dict__.items() if k != "errors"} | {
            "error_count": len(self.errors)
        }


def catchup_floor_mjd(store: Store, now_mjd: float, cfg: Config) -> float:
    """Oldest lastmjd worth fetching: since the last good run (minus a day of slack),
    bounded to [default, max] lookback."""
    last = store.last_success_mjd_floor()
    floor = now_mjd - cfg.default_lookback_days
    if last is not None:
        floor = min(floor, last - 1.0)
    return max(floor, now_mjd - cfg.max_lookback_days)


def _select_detections(
    survey: str, oid: str, raw_rows: list[dict[str, Any]], limit: int = MAX_DETECTIONS
) -> list[DetectionRow]:
    dets = [d for r in raw_rows if (d := normalize_detection(survey, oid, r)) is not None]
    dets.sort(key=lambda d: d.mjd, reverse=True)
    seen: set[str] = set()
    out: list[DetectionRow] = []
    for d in dets:
        if d.measurement_id not in seen:
            seen.add(d.measurement_id)
            out.append(d)
            if len(out) >= limit:
                break
    return out


def _select_probabilities(
    survey: str, oid: str, raw_rows: list[dict[str, Any]], max_rank: int = MAX_PROB_RANK
) -> list[ClassificationRow]:
    groups: dict[tuple[str, str], list[ClassificationRow]] = {}
    for r in raw_rows:
        c = normalize_probability(survey, oid, r)
        if c is not None:
            groups.setdefault((c.classifier_name, c.classifier_version), []).append(c)

    out: list[ClassificationRow] = []
    for group in groups.values():
        group.sort(key=lambda c: c.probability, reverse=True)
        seen_classes: set[str] = set()
        for idx, c in enumerate(group, start=1):
            rank = c.ranking if c.ranking is not None else idx
            if rank <= max_rank and c.class_name not in seen_classes:
                seen_classes.add(c.class_name)
                out.append(c if c.ranking is not None else replace(c, ranking=rank))
    return out


def run(
    store: Store,
    client: AlerceClient,
    *,
    trigger: str = "cli",
    surveys: tuple[str, ...] = ("lsst", "ztf"),
    cfg: Config | None = None,
    now: datetime | None = None,
    monotonic: Callable[[], float] = time.monotonic,
) -> RunResult:
    cfg = cfg or Config()
    started = monotonic()
    run_id = store.start_run(trigger, surveys)
    if run_id is None:
        log.warning("another ingest run holds the lease; skipping")
        return RunResult(run_id=None, status="skipped")

    res = RunResult(run_id=run_id, status="running")
    requests_before = client.request_count
    budget_hit = False
    truncated: set[str] = set()  # sources that hit the page cap before reaching the floor
    try:
        now_mjd = datetime_to_mjd(now or datetime.now(UTC))
        floor = catchup_floor_mjd(store, now_mjd, cfg)
        log.info("ingest start", extra={"run_id": run_id, "floor_mjd": round(floor, 4)})

        for survey, classifier in SOURCES:
            if survey not in surveys:
                continue
            source = f"{survey}:{classifier or 'default'}"
            reached_end = False
            for page in range(1, cfg.max_pages_per_source + 1):
                if monotonic() - started > cfg.time_budget_s:
                    budget_hit = True
                    log.warning("time budget reached", extra={"source": source, "page": page})
                    break
                try:
                    rows = client.list_objects(
                        survey,  # type: ignore[arg-type]
                        page=page,
                        page_size=cfg.page_size,
                        classifier=classifier,
                    )
                except AlerceError as exc:
                    res.errors.append({"source": source, "page": page, "error": str(exc)[:500]})
                    log.error("source failed", extra={"source": source, "error": str(exc)})
                    reached_end = True  # counted as a failed source, not a truncation
                    break

                objs: list[ObjectRow] = []
                clss: list[ClassificationRow] = []
                oldest = None
                for raw in rows:
                    norm = normalize_object(survey, raw)
                    if norm is None:
                        res.rejected += 1
                        continue
                    o, c = norm
                    objs.append(o)
                    if c is not None:
                        clss.append(c)
                    if o.lastmjd is not None:
                        oldest = o.lastmjd if oldest is None else min(oldest, o.lastmjd)
                res.objects_seen += len(rows)
                try:
                    n_o, n_c = store.upsert_batch(run_id, objs, clss)
                except psycopg.Error as exc:
                    # One bad page must not sink the run; record it and move on.
                    res.errors.append({"source": source, "page": page, "error": f"db: {exc}"[:500]})
                    log.error("page upsert failed", extra={"source": source, "page": page})
                    reached_end = True
                    break
                res.objects_upserted += n_o
                res.classifications_upserted += n_c
                log.info(
                    "page ingested",
                    extra={"source": source, "page": page, "rows": len(rows), "upserted": n_o},
                )
                if len(rows) < cfg.page_size or (oldest is not None and oldest < floor):
                    reached_end = True
                    break
            if not reached_end and not budget_hit:
                truncated.add(source)
                log.warning("page cap reached before catch-up floor", extra={"source": source})
            if budget_hit:
                break

        attempted = sum(1 for s, _ in SOURCES if s in surveys)
        failed_sources = len({e["source"] for e in res.errors if e["source"] != "enrich"})
        if truncated:
            res.errors.append({"source": "paging", "error": f"page cap hit: {sorted(truncated)}"})
        if res.rejected:
            res.errors.append({"source": "normalize", "error": f"{res.rejected} rows rejected"})
        if failed_sources and failed_sources >= attempted:
            res.status = "failed"
        elif failed_sources or budget_hit or truncated or res.rejected:
            res.status = "partial"
        else:
            res.status = "success"

        if not budget_hit and cfg.enrich_max_objects > 0:
            candidates = store.enrichment_candidates(run_id, cfg.enrich_max_objects)
            for survey, oid in candidates:
                if monotonic() - started > cfg.time_budget_s:
                    log.warning("time budget reached during enrichment", extra={"oid": oid})
                    break
                try:
                    raw_dets = client.detections(survey, oid)  # type: ignore[arg-type]
                    raw_probs = client.probabilities(survey, oid)  # type: ignore[arg-type]
                    dets = _select_detections(survey, oid, raw_dets)
                    probs = _select_probabilities(survey, oid, raw_probs)
                    n_d, n_c = store.enrich_object(survey, oid, dets, probs)
                except Exception as exc:
                    # Any per-object failure (upstream, DB, or a bad payload we didn't
                    # anticipate) is recorded and skipped: the list phase already set
                    # the run status, and enrichment must never demote it.
                    res.errors.append(
                        {
                            "source": "enrich",
                            "oid": oid,
                            "error": f"{type(exc).__name__}: {exc}"[:500],
                        }
                    )
                    log.exception("enrichment failed", extra={"survey": survey, "oid": oid})
                    continue
                res.objects_enriched += 1
                res.detections_upserted += n_d
                res.classifications_upserted += n_c
                log.info(
                    "object enriched",
                    extra={"survey": survey, "oid": oid, "detections": n_d, "probabilities": n_c},
                )
    except Exception as exc:  # record, then re-raise: no silent failures
        res.status = "failed"
        res.errors.append({"source": "ingest", "error": f"{type(exc).__name__}: {exc}"[:500]})
        log.exception("ingest crashed", extra={"run_id": run_id})
        raise
    finally:
        res.requests = client.request_count - requests_before
        res.duration_ms = round((monotonic() - started) * 1000)
        try:
            store.finish_run(
                run_id,
                status=res.status,
                objects_seen=res.objects_seen,
                objects_upserted=res.objects_upserted,
                classifications_upserted=res.classifications_upserted,
                objects_enriched=res.objects_enriched,
                detections_upserted=res.detections_upserted,
                requests=res.requests,
                errors=res.errors,
                duration_ms=res.duration_ms,
            )
        except Exception:
            # Don't mask the original error; the lease expires on its own.
            log.exception("could not record run outcome", extra={"run_id": run_id})
        log.info("ingest finished", extra=res.as_dict())
    return res


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--surveys", default="lsst,ztf")
    ap.add_argument("--trigger", default="cli", choices=["cli", "manual", "cron"])
    args = ap.parse_args(argv)
    logutil.configure(os.getenv("LOG_LEVEL", "INFO"))
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        print("DATABASE_URL is not set", file=sys.stderr)
        return 2
    surveys = tuple(s for s in args.surveys.split(",") if s in ("lsst", "ztf"))
    store = Store.connect(dsn)
    try:
        with AlerceClient() as client:
            res = run(store, client, trigger=args.trigger, surveys=surveys, cfg=Config.from_env())
    finally:
        store.close()
    return 0 if res.status in ("success", "partial", "skipped") else 1


if __name__ == "__main__":
    sys.exit(main())
