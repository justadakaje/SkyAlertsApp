"""Apply db/migrations/*.sql in order, exactly once each.

    DATABASE_URL=postgres://skyalerts_admin:...@.../skyalerts uv run python migrate.py [--dry-run]

- Each migration runs in its own transaction together with its bookkeeping row,
  so a failure leaves the database at the previous version.
- A session-level advisory lock prevents two runners racing.
- Applied migrations are checksummed; editing one after it ran is an error
  (write a new migration instead).
"""

from __future__ import annotations

import argparse
import hashlib
import os
import re
import sys
from pathlib import Path

import psycopg

MIGRATIONS_DIR = Path(__file__).parent / "migrations"
NAME_RE = re.compile(r"^(\d{4})_[a-z0-9_]+\.sql$")
LOCK_KEY = 0x5C7A1E27  # arbitrary, stable

BOOTSTRAP = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version    text        PRIMARY KEY,
    checksum   text        NOT NULL,
    applied_at timestamptz NOT NULL DEFAULT now()
)
"""


class MigrationError(Exception):
    pass


def discover(directory: Path = MIGRATIONS_DIR) -> list[tuple[str, Path, str]]:
    found = []
    for path in sorted(directory.glob("*.sql")):
        m = NAME_RE.match(path.name)
        if not m:
            raise MigrationError(f"Bad migration filename: {path.name} (want NNNN_snake_case.sql)")
        sql = path.read_text()
        found.append((path.stem, path, hashlib.sha256(sql.encode()).hexdigest()))
    versions = [v[:4] for v, _, _ in found]
    if len(set(versions)) != len(versions):
        raise MigrationError(f"Duplicate migration numbers: {versions}")
    return found


def migrate(dsn: str, *, dry_run: bool = False, directory: Path = MIGRATIONS_DIR) -> list[str]:
    migrations = discover(directory)
    applied_now: list[str] = []
    with psycopg.connect(dsn, autocommit=True) as conn:
        conn.execute("SELECT pg_advisory_lock(%s)", (LOCK_KEY,))
        try:
            conn.execute(BOOTSTRAP)
            done = dict(conn.execute("SELECT version, checksum FROM schema_migrations").fetchall())
            for version, path, checksum in migrations:
                if version in done:
                    if done[version] != checksum:
                        raise MigrationError(
                            f"{version} was modified after being applied (checksum mismatch)"
                        )
                    continue
                if dry_run:
                    applied_now.append(version)
                    continue
                with conn.transaction():
                    conn.execute(path.read_text())
                    conn.execute(
                        "INSERT INTO schema_migrations (version, checksum) VALUES (%s, %s)",
                        (version, checksum),
                    )
                applied_now.append(version)
        finally:
            conn.execute("SELECT pg_advisory_unlock(%s)", (LOCK_KEY,))
    return applied_now


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--dry-run", action="store_true", help="list pending migrations only")
    args = ap.parse_args(argv)
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        print("DATABASE_URL is not set", file=sys.stderr)
        return 2
    try:
        applied = migrate(dsn, dry_run=args.dry_run)
    except (MigrationError, psycopg.Error) as exc:
        print(f"migration failed: {exc}", file=sys.stderr)
        return 1
    verb = "pending" if args.dry_run else "applied"
    print(f"{verb}: {', '.join(applied) if applied else 'none'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
