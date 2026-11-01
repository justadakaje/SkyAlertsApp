"""Phase 0 exploration: pull a handful of recent ALeRCE objects per survey and
summarise fields, classes, and freshness.

    python -m skyalerts_ingest.explore --survey both --limit 25 --out out/explore

Writes raw JSON samples (future real-data fixtures) and a Markdown summary.
Exit code: 0 if at least one survey succeeded, 1 if all failed, 2 on bad args.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from . import logutil
from .alerce_client import MAX_PAGE_SIZE, AlerceClient, AlerceError, Survey
from .summary import SurveySummary, render_markdown, summarize_objects

log = logging.getLogger("skyalerts.explore")


def _write_json(out: Path | None, name: str, data: Any) -> None:
    if out is None:
        return
    out.mkdir(parents=True, exist_ok=True)
    (out / name).write_text(json.dumps(data, indent=2, sort_keys=True, default=str) + "\n")


def explore_survey(
    client: AlerceClient,
    survey: Survey,
    limit: int,
    n_probabilities: int,
    out: Path | None,
    now: datetime,
) -> SurveySummary:
    try:
        objects = client.list_objects(survey, page_size=limit)
    except AlerceError as exc:
        log.error("list_objects failed", extra={"survey": survey, "error": str(exc)})
        return SurveySummary.failed(survey, str(exc))
    _write_json(out, f"{survey}_objects.json", {"items": objects})

    probs: list[dict[str, Any]] = []
    samples: dict[str, Any] = {}
    for obj in objects[:n_probabilities]:
        oid = obj.get("oid")
        if oid is None:
            continue
        try:
            p = client.probabilities(survey, oid)
        except AlerceError as exc:
            log.warning(
                "probabilities failed", extra={"survey": survey, "oid": oid, "error": str(exc)}
            )
            continue
        samples[str(oid)] = p
        probs.extend(p)
    _write_json(out, f"{survey}_probabilities.json", samples)

    summary = summarize_objects(survey, objects, now, probs)
    log.info(
        "survey explored",
        extra={
            "survey": survey,
            "objects": summary.n_objects,
            "newest_age_h": summary.newest_age_hours,
            "classes": len(summary.classes),
        },
    )
    return summary


def main(argv: list[str] | None = None, *, client: AlerceClient | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--survey", choices=["both", "ztf", "lsst"], default="both")
    ap.add_argument(
        "--limit", type=int, default=25, help=f"objects per survey (1..{MAX_PAGE_SIZE})"
    )
    ap.add_argument("--probabilities", type=int, default=5, help="fetch probabilities for first N")
    ap.add_argument("--out", type=Path, default=None, help="directory for raw JSON samples")
    ap.add_argument("--markdown", type=Path, default=None, help="write Markdown summary here")
    ap.add_argument("--log-level", default="INFO")
    args = ap.parse_args(argv)

    if not 1 <= args.limit <= MAX_PAGE_SIZE:
        ap.error(f"--limit must be 1..{MAX_PAGE_SIZE}")
    if args.probabilities < 0:
        ap.error("--probabilities must be >= 0")

    logutil.configure(args.log_level)
    now = datetime.now(UTC)
    surveys: list[Survey] = ["ztf", "lsst"] if args.survey == "both" else [args.survey]

    owns_client = client is None
    client = client or AlerceClient()
    try:
        summaries = [
            explore_survey(client, s, args.limit, args.probabilities, args.out, now)
            for s in surveys
        ]
        if "ztf" in surveys:
            try:
                _write_json(args.out, "ztf_classifiers.json", client.ztf_classifiers())
            except AlerceError as exc:
                log.warning("classifier listing failed", extra={"error": str(exc)})
    finally:
        if owns_client:
            client.close()

    md = render_markdown(summaries, now)
    if args.markdown:
        args.markdown.parent.mkdir(parents=True, exist_ok=True)
        args.markdown.write_text(md + "\n")
    print(md)
    log.info("explore finished", extra={"requests": client.request_count})
    return 0 if any(s.error is None for s in summaries) else 1


if __name__ == "__main__":
    sys.exit(main())
