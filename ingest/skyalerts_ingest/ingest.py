"""Daily ingest: pull recently-updated ALeRCE objects, upsert them, and enrich top candidates.

    DATABASE_URL=... python -m skyalerts_ingest.ingest [--surveys lsst,ztf] [--trigger cli]

Strategy (fits Vercel Hobby: one run/day, 300 s max; see docs/decisions.md #13, #18, #24):
- Page each source newest-first (order_by=lastmjd DESC) and stop once a page
  reaches objects older than the source's catch-up floor, or the page cap / time budget.
- The floor is in data time: the newest lastmjd the source saw when its window last
  advanced, minus a day of overlap for late arrivals. A "complete" source that hits
  its page cap first records the possible gap (exact lastmjd range) and is partial.
- Neither full stream can be paged in one run (LSST ~500 pages/night), so each is a
  newest-first "sample" (truncation expected, not a gap); the tier-1 transient classes
  (LSST SN; ZTF stamp SN, lc SNIa/SNIbc/SNII/SLSN/CV/Nova) are paged completely.
- LSST list rows already carry the top classification.
- ZTF list rows only carry a class when filtered by classifier, so ZTF is
  paged once per classifier; stamp first, then lc (lc wins as top_class).
- Bounded enrichment: for up to enrich_max_objects priority candidates touched
  in this run (excluding bogus/asteroid, skipping already-current objects),
  fetch per-object detections (capped at 200 newest) and probabilities
  (top 3 per classifier version) within the shared time budget.
- Upserts are idempotent; a lease row in ingest_runs (claimed under a
  transaction-scoped advisory lock, so it is PgBouncer-safe) serialises runs.
- Run outcome: success | partial (possible gap, budget hit, a source failed, rows
  rejected in list paging) | failed. Each source's window advances only when its
  own coverage reached the floor or its gap was recorded; enrichment errors or
  budget exhaustion are logged without demoting status.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
import time
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass, field, replace
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

MAX_DETECTIONS = 200
MAX_PROB_RANK = 3
# Rows dated further than this past the wall clock don't move a watermark: one bad
# upstream lastmjd would otherwise lift the floor above all real data (a silent gap).
FUTURE_TOLERANCE_DAYS = 1 / 24
LSST_STAMP_CLASSIFIER = "stamp_classifier_rubin_beta_20260421"


@dataclass(frozen=True)
class Source:
    survey: str
    classifier: str | None = None
    class_name: str | None = None
    # complete: must page back to its floor, else a gap is possible (run is partial).
    # sample: a newest-first slice by design; stopping at the page cap is expected.
    complete: bool = True
    max_pages: int | None = None  # None -> Config.max_pages_per_source
    # Flag the source if its newest row trails the survey's newest by this much
    # (catches a renamed classifier silently returning an ever-older list).
    stale_after_days: float | None = None

    @property
    def key(self) -> str:
        parts = [self.survey, self.classifier or "default"]
        if self.class_name:
            parts.append(self.class_name)
        return ":".join(parts)


# Neither unfiltered stream can be paged in a run (LSST ~500 pages/night, ZTF 100 rows
# per ~2 min of data), so each classifier's tier-1 transient classes (store.TIER1_CLASSES)
# are paged completely and the rest is a newest-first sample. Volumes measured
# 2026-11-01, see decisions.md #24. Order matters for top_class: later LSST rows win
# (SN over the sample); for ZTF, lc always wins over stamp (store._TAKE_TOP).
ZTF_LC_TIER1 = ("SNIa", "SNIbc", "SNII", "SLSN", "CV/Nova")
SOURCES: tuple[Source, ...] = (
    Source("lsst", complete=False),
    Source("lsst", LSST_STAMP_CLASSIFIER, "SN", max_pages=40, stale_after_days=2.0),
    Source("ztf", "stamp_classifier", complete=False, max_pages=1),
    Source("ztf", "stamp_classifier", "SN", max_pages=10),
    Source("ztf", "lc_classifier", complete=False, max_pages=1),
    *(Source("ztf", "lc_classifier", c, max_pages=10) for c in ZTF_LC_TIER1),
)


@dataclass
class Coverage:
    """What one source's paging covered, stored per run in ingest_runs.coverage."""

    floor_mjd: float | None = None
    newest_mjd: float | None = None
    oldest_mjd: float | None = None
    pages: int = 0
    outcome: str = "running"  # complete | capped | sample | budget | error

    @property
    def advances(self) -> bool:
        # A capped source advances too: its gap is recorded, and holding the window
        # back would make every later run need even more pages (never catching up).
        return self.newest_mjd is not None and self.outcome in ("complete", "capped")

    def as_dict(self) -> dict[str, Any]:
        return asdict(self) | {"advances": self.advances}


@dataclass
class Config:
    page_size: int = 100
    max_pages_per_source: int = 20
    overlap_days: float = 1.0  # re-cover below the last watermark for late arrivals
    default_lookback_days: float = 1.2  # source with no watermark yet: about one night
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
    coverage: dict[str, Coverage] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {k: v for k, v in self.__dict__.items() if k not in ("errors", "coverage")} | {
            "error_count": len(self.errors),
            "coverage": {k: c.as_dict() for k, c in self.coverage.items()},
        }


def catchup_floor_mjd(
    watermark: float | None, newest: float, cfg: Config
) -> tuple[float, float | None]:
    """Oldest lastmjd a complete source must reach, in data time rather than wall clock.

    With a watermark, re-cover overlap_days below it; without one, look back
    default_lookback_days from this run's newest row. Bounded to max_lookback_days:
    returns (floor, gap_start), where gap_start is set when that bound cut the window
    and [gap_start, floor) will not be fetched.
    """
    want = newest - cfg.default_lookback_days if watermark is None else watermark - cfg.overlap_days
    limit = newest - cfg.max_lookback_days
    return (limit, want) if want < limit else (want, None)


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
    sources: Sequence[Source] = SOURCES,
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
    gaps = False  # a complete source may have missed rows (recorded in errors)
    try:
        newest_ok = datetime_to_mjd(now or datetime.now(UTC)) + FUTURE_TOLERANCE_DAYS
        log.info("ingest start", extra={"run_id": run_id})

        for src in sources:
            if src.survey not in surveys:
                continue
            source = src.key
            cov = res.coverage[source] = Coverage()
            watermark = store.source_watermark(source) if src.complete else None
            for page in range(1, (src.max_pages or cfg.max_pages_per_source) + 1):
                if monotonic() - started > cfg.time_budget_s:
                    budget_hit = True
                    cov.outcome = "budget"
                    log.warning("time budget reached", extra={"source": source, "page": page})
                    break
                try:
                    rows = client.list_objects(
                        src.survey,  # type: ignore[arg-type]
                        page=page,
                        page_size=cfg.page_size,
                        classifier=src.classifier,
                        class_name=src.class_name,
                    )
                except AlerceError as exc:
                    res.errors.append({"source": source, "page": page, "error": str(exc)[:500]})
                    log.error("source failed", extra={"source": source, "error": str(exc)})
                    cov.outcome = "error"
                    break

                objs: list[ObjectRow] = []
                clss: list[ClassificationRow] = []
                oldest = None
                for raw in rows:
                    norm = normalize_object(src.survey, raw)
                    if norm is None:
                        res.rejected += 1
                        continue
                    o, c = norm
                    objs.append(o)
                    if c is not None:
                        clss.append(c)
                    if o.lastmjd is not None:
                        oldest = o.lastmjd if oldest is None else min(oldest, o.lastmjd)
                        if o.lastmjd <= newest_ok and (
                            cov.newest_mjd is None or o.lastmjd > cov.newest_mjd
                        ):
                            cov.newest_mjd = o.lastmjd
                res.objects_seen += len(rows)
                try:
                    n_o, n_c = store.upsert_batch(run_id, objs, clss)
                except psycopg.Error as exc:
                    # One bad page must not sink the run; record it and move on.
                    res.errors.append({"source": source, "page": page, "error": f"db: {exc}"[:500]})
                    log.error("page upsert failed", extra={"source": source, "page": page})
                    cov.outcome = "error"
                    break
                res.objects_upserted += n_o
                res.classifications_upserted += n_c
                cov.pages = page
                if oldest is not None:
                    cov.oldest_mjd = (
                        oldest if cov.oldest_mjd is None else min(cov.oldest_mjd, oldest)
                    )
                log.info(
                    "page ingested",
                    extra={"source": source, "page": page, "rows": len(rows), "upserted": n_o},
                )
                if src.complete and cov.floor_mjd is None and cov.newest_mjd is not None:
                    cov.floor_mjd, gap_start = catchup_floor_mjd(watermark, cov.newest_mjd, cfg)
                    if gap_start is not None:
                        gaps = True
                        res.errors.append(
                            {
                                "source": source,
                                "error": "gap: window older than max lookback",
                                "gap_mjd": [gap_start, cov.floor_mjd],
                            }
                        )
                if len(rows) < cfg.page_size or (
                    oldest is not None and cov.floor_mjd is not None and oldest < cov.floor_mjd
                ):
                    cov.outcome = "complete" if src.complete else "sample"
                    break
            if cov.outcome == "running":  # used every page without reaching the floor
                if src.complete:
                    gaps = True
                    cov.outcome = "capped"
                    res.errors.append(
                        {
                            "source": source,
                            "error": "possible gap: page cap hit before catch-up floor",
                            "gap_mjd": [cov.floor_mjd, cov.oldest_mjd],
                        }
                    )
                    log.warning("page cap reached before catch-up floor", extra={"source": source})
                else:
                    cov.outcome = "sample"
            log.info("source paged", extra={"source": source, **cov.as_dict()})
            if budget_hit:
                break

        # Compare against every source of the survey, so a stale filtered list shows up
        # next to the unfiltered sample.
        survey_newest: dict[str, float] = {}
        for src in sources:
            cov = res.coverage.get(src.key)
            if cov is not None and cov.newest_mjd is not None:
                survey_newest[src.survey] = max(cov.newest_mjd, survey_newest.get(src.survey, 0.0))
        for src in sources:
            cov = res.coverage.get(src.key)
            ref = survey_newest.get(src.survey)
            if src.stale_after_days is None or cov is None or ref is None:
                continue
            if cov.outcome in ("complete", "capped") and (
                cov.newest_mjd is None or ref - cov.newest_mjd > src.stale_after_days
            ):
                gaps = True
                behind = "no rows" if cov.newest_mjd is None else f"{ref - cov.newest_mjd:.1f} d"
                res.errors.append(
                    {
                        "source": src.key,
                        "error": f"stale: {behind} behind newest {src.survey} row"
                        " (classifier renamed?)",
                    }
                )

        attempted = sum(1 for s in sources if s.survey in surveys)
        failed_sources = sum(1 for c in res.coverage.values() if c.outcome == "error")
        if res.rejected:
            res.errors.append({"source": "normalize", "error": f"{res.rejected} rows rejected"})
        if failed_sources and failed_sources >= attempted:
            res.status = "failed"
        elif failed_sources or budget_hit or gaps or res.rejected:
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
                coverage={k: c.as_dict() for k, c in res.coverage.items()},
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
