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
import contextlib
import hashlib
import os
import re
import sys
from pathlib import Path

import psycopg
import psycopg.conninfo

MIGRATIONS_DIR = Path(__file__).parent / "migrations"
NAME_RE = re.compile(r"^(\d{4})_[a-z0-9_]+\.sql$")
# Explicit transaction control would break the one-transaction-per-file guarantee.
TXN_RE = re.compile(
    r"^\s*(BEGIN|COMMIT|END|ROLLBACK|START\s+TRANSACTION|SAVEPOINT|RELEASE)\b",
    re.IGNORECASE | re.MULTILINE,
)
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


def discover(directory: Path = MIGRATIONS_DIR) -> list[tuple[str, str, str]]:
    """Return [(version, sql, sha256)]. The SQL that is hashed is the SQL that runs."""
    found = []
    for path in sorted(directory.glob("*.sql")):
        m = NAME_RE.match(path.name)
        if not m:
            raise MigrationError(f"Bad migration filename: {path.name} (want NNNN_snake_case.sql)")
        sql = path.read_text()
        if TXN_RE.search(_strip_dollar_quoted(sql)):
            raise MigrationError(
                f"{path.name} contains explicit transaction control; the runner wraps each file"
            )
        found.append((path.stem, sql, hashlib.sha256(sql.encode()).hexdigest()))
    versions = [v[:4] for v, _, _ in found]
    if len(set(versions)) != len(versions):
        raise MigrationError(f"Duplicate migration numbers: {versions}")
    return found


def _strip_dollar_quoted(sql: str) -> str:
    """Drop $$...$$ bodies (DO blocks/functions) so BEGIN/END inside them aren't flagged."""
    return re.sub(r"\$(\w*)\$.*?\$\1\$", "", sql, flags=re.DOTALL)


def _is_pooled(dsn: str) -> bool:
    return "-pooler" in (psycopg.conninfo.conninfo_to_dict(dsn).get("host") or "")


def migrate(dsn: str, *, dry_run: bool = False, directory: Path = MIGRATIONS_DIR) -> list[str]:
    migrations = discover(directory)
    if _is_pooled(dsn):
        # Session advisory locks don't survive PgBouncer transaction pooling.
        raise MigrationError("Use the direct (non -pooler) Neon endpoint for migrations")
    applied_now: list[str] = []
    with psycopg.connect(dsn, autocommit=True) as conn:
        conn.execute("SELECT pg_advisory_lock(%s)", (LOCK_KEY,))
        try:
            exists = conn.execute("SELECT to_regclass('schema_migrations')").fetchone()[0]
            if exists is None and not dry_run:
                conn.execute(BOOTSTRAP)
            done = (
                dict(conn.execute("SELECT version, checksum FROM schema_migrations").fetchall())
                if exists is not None or not dry_run
                else {}
            )
            for version, sql, checksum in migrations:
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
                    conn.execute(sql)
                    conn.execute(
                        "INSERT INTO schema_migrations (version, checksum) VALUES (%s, %s)",
                        (version, checksum),
                    )
                applied_now.append(version)
        finally:
            # If the connection is gone the lock died with the session; keep the original error.
            with contextlib.suppress(psycopg.Error):
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
