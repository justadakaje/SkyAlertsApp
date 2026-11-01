"""Daily ingest: pull recently-updated ALeRCE objects and upsert them.

    DATABASE_URL=... python -m skyalerts_ingest.ingest [--surveys lsst,ztf] [--trigger cli]

Strategy (fits Vercel Hobby: one run/day, 300 s max; see docs/decisions.md #13):
- Page each source newest-first (order_by=lastmjd DESC) and stop once a page
  reaches objects older than the catch-up window, or the page cap / time budget.
- LSST list rows already carry the top classification.
- ZTF list rows only carry a class when filtered by classifier, so ZTF is
  paged once per classifier; stamp first, then lc (lc wins as top_class).
- Upserts are idempotent; an advisory lock serialises overlapping runs.
- Run outcome: success | partial (budget hit or some sources failed) | failed.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from . import logutil
from .alerce_client import AlerceClient, AlerceError
from .normalize import ClassificationRow, ObjectRow, normalize_object
from .store import Store
from .summary import datetime_to_mjd

log = logging.getLogger("skyalerts.ingest")

# (survey, classifier filter or None). Order matters for ZTF top_class precedence.
SOURCES: list[tuple[str, str | None]] = [
    ("lsst", None),
    ("ztf", "stamp_classifier"),
    ("ztf", "lc_classifier"),
]


@dataclass
class Config:
    page_size: int = 100
    max_pages_per_source: int = 10
    default_lookback_days: float = 2.0
    max_lookback_days: float = 7.0
    time_budget_s: float = 240.0  # leave headroom under Vercel's 300 s

    @classmethod
    def from_env(cls) -> Config:
        c = cls()
        c.page_size = int(os.getenv("INGEST_PAGE_SIZE", c.page_size))
        c.max_pages_per_source = int(os.getenv("INGEST_MAX_PAGES", c.max_pages_per_source))
        c.time_budget_s = float(os.getenv("INGEST_TIME_BUDGET_S", c.time_budget_s))
        return c


@dataclass
class RunResult:
    run_id: int | None
    status: str
    objects_seen: int = 0
    objects_upserted: int = 0
    classifications_upserted: int = 0
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
    if not store.try_lock():
        log.warning("another ingest run holds the lock; skipping")
        return RunResult(run_id=None, status="skipped")

    run_id = store.start_run(trigger, surveys)
    res = RunResult(run_id=run_id, status="running")
    requests_before = client.request_count
    budget_hit = False
    try:
        now_mjd = datetime_to_mjd(now or datetime.now(UTC))
        floor = catchup_floor_mjd(store, now_mjd, cfg)
        log.info("ingest start", extra={"run_id": run_id, "floor_mjd": round(floor, 4)})

        for survey, classifier in SOURCES:
            if survey not in surveys:
                continue
            source = f"{survey}:{classifier or 'default'}"
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
                n_o, n_c = store.upsert_batch(run_id, objs, clss)
                res.objects_upserted += n_o
                res.classifications_upserted += n_c
                log.info(
                    "page ingested",
                    extra={"source": source, "page": page, "rows": len(rows), "upserted": n_o},
                )
                if len(rows) < cfg.page_size or (oldest is not None and oldest < floor):
                    break
            if budget_hit:
                break

        attempted = sum(1 for s, _ in SOURCES if s in surveys)
        failed_sources = len({e["source"] for e in res.errors})
        if failed_sources and failed_sources >= attempted:
            res.status = "failed"
        elif failed_sources or budget_hit or res.rejected:
            res.status = "partial"
        else:
            res.status = "success"
        if res.rejected:
            res.errors.append({"source": "normalize", "error": f"{res.rejected} rows rejected"})
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
                requests=res.requests,
                errors=res.errors,
                duration_ms=res.duration_ms,
            )
        finally:
            store.unlock()
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
