"""CLI entrypoint for rendering the weekly Sky Alerts digest.

DATABASE_URL=... python -m skyalerts_digest --week-end 2026-11-01 [--html]
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import UTC, datetime

import psycopg

from .render import render_html, render_markdown
from .select import select_digest


def parse_week_end(raw: str | None) -> datetime:
    if not raw:
        return datetime.now(UTC)
    dt = datetime.fromisoformat(raw)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="skyalerts_digest",
        description="Render the weekly Sky Alerts digest from Postgres (read-only).",
    )
    parser.add_argument(
        "--week-end",
        default=None,
        help="End of the 7-day window (ISO-8601 date or datetime in UTC, e.g. 2026-11-01).",
    )
    parser.add_argument(
        "--html",
        action="store_true",
        help="Render HTML instead of Markdown.",
    )
    args = parser.parse_args(argv)

    try:
        week_end = parse_week_end(args.week_end)
    except ValueError as exc:
        print(f"invalid --week-end {args.week_end!r}: {exc}", file=sys.stderr)
        return 2

    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        print("DATABASE_URL is not set", file=sys.stderr)
        return 2

    with psycopg.connect(
        dsn,
        autocommit=True,
        connect_timeout=15,
        application_name="skyalerts-digest",
    ) as conn:
        digest = select_digest(conn, week_end)

    output = render_html(digest) if args.html else render_markdown(digest)
    sys.stdout.write(output)
    if not output.endswith("\n"):
        sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
