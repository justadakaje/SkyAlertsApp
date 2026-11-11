"""Integration tests against a real Postgres.

Requires TEST_DATABASE_URL pointing at a superuser connection on a throwaway
server (CI uses a postgres:17 service container). Each test gets a fresh
database; roles are cluster-wide and created idempotently by 0002.
"""

from __future__ import annotations

import os
import shutil
import sys
import uuid
from pathlib import Path

import psycopg
import pytest
from psycopg import conninfo, errors

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import migrate

ADMIN_URL = os.environ.get("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not ADMIN_URL, reason="TEST_DATABASE_URL not set")


@pytest.fixture
def db_url():
    name = f"t_{uuid.uuid4().hex[:12]}"
    with psycopg.connect(ADMIN_URL, autocommit=True) as c:
        c.execute(f'CREATE DATABASE "{name}"')
    url = conninfo.make_conninfo(ADMIN_URL, dbname=name)
    yield url
    with psycopg.connect(ADMIN_URL, autocommit=True) as c:
        c.execute(f'DROP DATABASE "{name}" WITH (FORCE)')


@pytest.fixture
def migrated(db_url):
    migrate.migrate(db_url)
    return db_url


def test_applies_all_then_is_idempotent(db_url):
    first = migrate.migrate(db_url)
    assert first == [
        "0001_init",
        "0002_roles_and_grants",
        "0003_enrichment",
        "0004_web_admin_role",
        "0005_ingest_coverage",
        "0006_sso_identifications",
        "0007_retention_policy",
    ]
    assert migrate.migrate(db_url) == []
    with psycopg.connect(db_url) as c:
        n = c.execute("SELECT count(*) FROM schema_migrations").fetchone()[0]
    assert n == 7


def test_dry_run_changes_nothing(db_url):
    assert migrate.migrate(db_url, dry_run=True) == [
        "0001_init",
        "0002_roles_and_grants",
        "0003_enrichment",
        "0004_web_admin_role",
        "0005_ingest_coverage",
        "0006_sso_identifications",
        "0007_retention_policy",
    ]
    with psycopg.connect(db_url) as c:
        assert c.execute("SELECT to_regclass('objects')").fetchone()[0] is None
        assert c.execute("SELECT to_regclass('schema_migrations')").fetchone()[0] is None


def test_checksum_mismatch_is_refused(db_url, tmp_path):
    d = tmp_path / "m"
    shutil.copytree(migrate.MIGRATIONS_DIR, d)
    migrate.migrate(db_url, directory=d)
    (d / "0001_init.sql").write_text((d / "0001_init.sql").read_text() + "\n-- edited\n")
    with pytest.raises(migrate.MigrationError, match="checksum"):
        migrate.migrate(db_url, directory=d)


def test_failed_migration_rolls_back(db_url, tmp_path):
    d = tmp_path / "m"
    shutil.copytree(migrate.MIGRATIONS_DIR, d)
    (d / "0008_broken.sql").write_text("CREATE TABLE ok_part (x int);\nSELECT * FROM nope;\n")
    with pytest.raises(psycopg.Error):
        migrate.migrate(db_url, directory=d)
    with psycopg.connect(db_url) as c:
        assert c.execute("SELECT to_regclass('ok_part')").fetchone()[0] is None
        versions = [r[0] for r in c.execute("SELECT version FROM schema_migrations")]
    assert "0008_broken" not in versions and "0007_retention_policy" in versions


def test_bad_filename_rejected(tmp_path):
    (tmp_path / "1_bad.sql").write_text("select 1;")
    with pytest.raises(migrate.MigrationError, match="filename"):
        migrate.discover(tmp_path)


def _as(url: str, role: str):
    c = psycopg.connect(url, autocommit=True)
    c.execute(f"SET ROLE {role}")
    c.execute(f"SET default_transaction_read_only = {'on' if role == 'skyalerts_ro' else 'off'}")
    return c


OBJ = (
    "INSERT INTO objects (survey, oid, meanra, meandec, raw) "
    "VALUES ('lsst', %s, 10.0, -20.0, '{}'::jsonb)"
)


def test_ingest_role_privileges(migrated):
    with _as(migrated, "skyalerts_ingest") as c:
        run_id = c.execute(
            "INSERT INTO ingest_runs (trigger, surveys) VALUES ('cli', '{lsst}') RETURNING id"
        ).fetchone()[0]
        c.execute(OBJ, ("1",))
        c.execute(
            "INSERT INTO classifications (survey, oid, classifier_name, class_name, probability)"
            " VALUES ('lsst', '1', 'stamp', 'VS', 0.9)"
        )
        c.execute(
            "UPDATE objects SET last_ingest_run_id = %s, enriched_at = now(),"
            " enriched_lastmjd = 61344.5 WHERE oid = '1'",
            (run_id,),
        )
        c.execute(
            "UPDATE ingest_runs SET status = 'success', objects_enriched = 1,"
            " detections_upserted = 5, coverage = '{\"lsst:default\": {}}' WHERE id = %s",
            (run_id,),
        )
        with pytest.raises(errors.InsufficientPrivilege):
            c.execute("UPDATE ingest_runs SET started_at = now() WHERE id = %s", (run_id,))
        with pytest.raises(errors.InsufficientPrivilege):
            c.execute("UPDATE ingest_runs SET trigger = 'cron' WHERE id = %s", (run_id,))
        with pytest.raises(errors.InsufficientPrivilege):
            c.execute("DELETE FROM objects")
        with pytest.raises(errors.InsufficientPrivilege):
            c.execute("SELECT * FROM audit_log")
        with pytest.raises(errors.InsufficientPrivilege):
            c.execute("CREATE TABLE sneaky (x int)")


def test_ro_role_is_read_only(migrated):
    with _as(migrated, "skyalerts_ingest") as c:
        run_id = c.execute(
            "INSERT INTO ingest_runs (trigger, surveys) VALUES ('cli', '{lsst}') RETURNING id"
        ).fetchone()[0]
        c.execute(OBJ, ("2",))
        c.execute(
            "UPDATE objects SET enriched_at = now(), enriched_lastmjd = 61000.0 WHERE oid = '2'"
        )
        c.execute(
            "UPDATE ingest_runs SET objects_enriched = 2, detections_upserted = 10 WHERE id = %s",
            (run_id,),
        )
    with _as(migrated, "skyalerts_ro") as c:
        row = c.execute(
            "SELECT enriched_at, enriched_lastmjd FROM objects WHERE oid = '2'"
        ).fetchone()
        assert row[0] is not None and row[1] == 61000.0
        r_row = c.execute(
            "SELECT objects_enriched, detections_upserted FROM ingest_runs WHERE id = %s",
            (run_id,),
        ).fetchone()
        assert r_row == (2, 10)
        with pytest.raises((errors.InsufficientPrivilege, errors.ReadOnlySqlTransaction)):
            c.execute(OBJ, ("3",))
        with pytest.raises(errors.InsufficientPrivilege):
            c.execute("SELECT * FROM audit_log")


def test_web_admin_role_privileges(migrated):
    with _as(migrated, "skyalerts_ingest") as c:
        run_id = c.execute(
            "INSERT INTO ingest_runs (trigger, surveys) VALUES ('cli', '{lsst}') RETURNING id"
        ).fetchone()[0]
        c.execute(OBJ, ("admin-1",))
    with _as(migrated, "skyalerts_web_admin") as c:
        c.execute("SELECT count(*) FROM objects").fetchone()
        c.execute("SELECT count(*) FROM classifications").fetchone()
        c.execute("SELECT count(*) FROM detections").fetchone()
        c.execute("SELECT count(*) FROM ingest_runs").fetchone()
        audit_id, audit_at = c.execute(
            "INSERT INTO audit_log (actor_github_id, action, target, details)"
            " VALUES (16056018, 'ingest.rerun', 'manual', '{\"ok\": true}'::jsonb)"
            " RETURNING id, at"
        ).fetchone()
        assert audit_id >= 1 and audit_at is not None
        row = c.execute(
            "SELECT actor_github_id, action, target, details FROM audit_log WHERE id = %s",
            (audit_id,),
        ).fetchone()
        assert row == (16056018, "ingest.rerun", "manual", {"ok": True})
        with pytest.raises(errors.InsufficientPrivilege):
            c.execute(
                "INSERT INTO audit_log (id, actor_github_id, action) OVERRIDING SYSTEM VALUE"
                " VALUES (999, 16056018, 'spoof')"
            )
        with pytest.raises(errors.InsufficientPrivilege):
            c.execute(
                "INSERT INTO audit_log (at, actor_github_id, action)"
                " VALUES ('2000-01-01T00:00:00Z', 16056018, 'backdate')"
            )
        with pytest.raises(errors.InsufficientPrivilege):
            c.execute("UPDATE audit_log SET action = 'tampered' WHERE id = %s", (audit_id,))
        with pytest.raises(errors.InsufficientPrivilege):
            c.execute("DELETE FROM audit_log WHERE id = %s", (audit_id,))
        with pytest.raises(errors.InsufficientPrivilege):
            c.execute(OBJ, ("admin-2",))
        with pytest.raises(errors.InsufficientPrivilege):
            c.execute("UPDATE objects SET top_class = 'SNIa' WHERE oid = 'admin-1'")
        with pytest.raises(errors.InsufficientPrivilege):
            c.execute("DELETE FROM objects WHERE oid = 'admin-1'")
        with pytest.raises(errors.InsufficientPrivilege):
            c.execute("INSERT INTO ingest_runs (trigger, surveys) VALUES ('manual', '{lsst}')")
        with pytest.raises(errors.InsufficientPrivilege):
            c.execute("UPDATE ingest_runs SET status = 'success' WHERE id = %s", (run_id,))
        with pytest.raises(errors.InsufficientPrivilege):
            c.execute("DELETE FROM ingest_runs WHERE id = %s", (run_id,))
        with pytest.raises(errors.InsufficientPrivilege):
            c.execute("CREATE TABLE sneaky_admin (x int)")


def test_roles_are_not_privileged(migrated):
    with psycopg.connect(migrated) as c:
        rows = c.execute(
            "SELECT rolname, rolsuper, rolcreaterole, rolcreatedb, rolbypassrls FROM pg_roles"
            " WHERE rolname IN ('skyalerts_ingest', 'skyalerts_ro', 'skyalerts_web_admin')"
        ).fetchall()
    assert len(rows) == 3
    assert all(not any(r[1:]) for r in rows)


@pytest.mark.parametrize(
    ("sql", "err"),
    [
        (
            "INSERT INTO objects (survey, oid, raw) VALUES ('ptf', 'x', '{}')",
            errors.CheckViolation,
        ),
        (
            "INSERT INTO objects (survey, oid, meandec, raw) VALUES ('ztf', 'x', 95, '{}')",
            errors.CheckViolation,
        ),
        (
            "INSERT INTO classifications (survey, oid, classifier_name, class_name, probability)"
            " VALUES ('ztf', 'missing', 'c', 'SN', 0.5)",
            errors.ForeignKeyViolation,
        ),
    ],
)
def test_constraints(migrated, sql, err):
    with psycopg.connect(migrated, autocommit=True) as c, pytest.raises(err):
        c.execute(sql)


def test_explicit_transaction_control_rejected(tmp_path):
    (tmp_path / "0001_x.sql").write_text(
        "CREATE TABLE a (x int);\nCOMMIT;\nCREATE TABLE b (x int);\n"
    )
    with pytest.raises(migrate.MigrationError, match="transaction control"):
        migrate.discover(tmp_path)


def test_do_block_begin_end_allowed(tmp_path):
    (tmp_path / "0001_x.sql").write_text("DO $$\nBEGIN\n  PERFORM 1;\nEND\n$$;\n")
    assert [v for v, _, _ in migrate.discover(tmp_path)] == ["0001_x"]


def test_pooled_endpoint_refused():
    dsn = "postgresql://u:p@ep-x-pooler.us-east-1.aws.neon.tech/skyalerts"
    with pytest.raises(migrate.MigrationError, match="pooler"):
        migrate.migrate(dsn)


def test_role_level_settings(migrated):
    with psycopg.connect(migrated) as c:
        rows = dict(
            c.execute(
                "SELECT r.rolname, s.setconfig FROM pg_db_role_setting s"
                " JOIN pg_roles r ON r.oid = s.setrole"
                " WHERE r.rolname IN ('skyalerts_ingest', 'skyalerts_ro', 'skyalerts_web_admin')"
                " AND s.setdatabase = 0"
            ).fetchall()
        )
    assert "statement_timeout=60s" in rows["skyalerts_ingest"]
    assert {"statement_timeout=10s", "default_transaction_read_only=on"} <= set(
        rows["skyalerts_ro"]
    )
    assert rows["skyalerts_web_admin"] == ["statement_timeout=10s"]


def test_ingest_cannot_choose_run_ids_or_temp_tables(migrated):
    with _as(migrated, "skyalerts_ingest") as c:
        with pytest.raises(errors.InsufficientPrivilege):
            c.execute(
                "INSERT INTO ingest_runs (id, trigger, surveys) OVERRIDING SYSTEM VALUE"
                " VALUES (999, 'cli', '{lsst}')"
            )
        with pytest.raises(errors.InsufficientPrivilege):
            c.execute("UPDATE ingest_runs SET started_at = now()")
        with pytest.raises(errors.InsufficientPrivilege):
            c.execute("CREATE TEMP TABLE t (x int)")


def test_dry_run_on_fresh_db_creates_nothing(db_url):
    migrate.migrate(db_url, dry_run=True)
    with psycopg.connect(db_url) as c:
        assert c.execute("SELECT to_regclass('schema_migrations')").fetchone()[0] is None


def test_retention_policy_prunes_only_old_bogus_artifacts(migrated):
    with _as(migrated, "skyalerts_ingest") as c:
        c.execute(
            """INSERT INTO objects (survey, oid, top_class, lastmjd, raw)
               VALUES ('ztf', 'old_bogus', 'bogus', 58000.0, '{}'::jsonb),
                      ('ztf', 'recent_bogus', 'bogus', 99000.0, '{}'::jsonb),
                      ('ztf', 'old_sn', 'SNIa', 58000.0, '{}'::jsonb)"""
        )
        pruned = c.execute("SELECT prune_old_artifacts(30.0)").fetchone()[0]
        assert pruned == 1
        remaining = [r[0] for r in c.execute("SELECT oid FROM objects ORDER BY oid").fetchall()]
        assert remaining == ["old_sn", "recent_bogus"]
        with pytest.raises(errors.RaiseException):
            c.execute("SELECT prune_old_artifacts(1.0)")
    with _as(migrated, "skyalerts_ro") as c, pytest.raises(errors.InsufficientPrivilege):
        c.execute("SELECT prune_old_artifacts(30.0)")
    with _as(migrated, "skyalerts_web_admin") as c, pytest.raises(errors.InsufficientPrivilege):
        c.execute("SELECT prune_old_artifacts(30.0)")
