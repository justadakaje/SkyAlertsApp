"""End-to-end ingest against real Postgres + mocked ALeRCE.

Needs TEST_DATABASE_URL (superuser on a throwaway server). Applies the real
db/migrations, then runs ingest as skyalerts_ingest to prove the grants suffice.
"""

from __future__ import annotations

import importlib.util
import os
import uuid
from datetime import UTC, datetime
from pathlib import Path

import httpx
import psycopg
import pytest
from psycopg import conninfo

from skyalerts_ingest.ingest import Config, run
from skyalerts_ingest.store import Store
from tests.conftest import load_fixture

ADMIN_URL = os.environ.get("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not ADMIN_URL, reason="TEST_DATABASE_URL not set")
NOW = datetime(2026, 11, 1, tzinfo=UTC)  # fixtures are anchored at MJD 61345.0

_spec = importlib.util.spec_from_file_location(
    "migrate", Path(__file__).resolve().parents[2] / "db" / "migrate.py"
)
migrate = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(migrate)


@pytest.fixture
def ingest_dsn():
    name = f"t_{uuid.uuid4().hex[:12]}"
    with psycopg.connect(ADMIN_URL, autocommit=True) as c:
        c.execute(f'CREATE DATABASE "{name}"')
    admin = conninfo.make_conninfo(ADMIN_URL, dbname=name)
    migrate.migrate(admin)
    with psycopg.connect(ADMIN_URL, autocommit=True) as c:
        c.execute("ALTER ROLE skyalerts_ingest PASSWORD 'test-only-password'")
    yield conninfo.make_conninfo(admin, user="skyalerts_ingest", password="test-only-password")
    with psycopg.connect(ADMIN_URL, autocommit=True) as c:
        c.execute(f'DROP DATABASE "{name}" WITH (FORCE)')


def alerce(lsst_status=200, ztf_status=200):
    def handler(req: httpx.Request) -> httpx.Response:
        page = int(req.url.params.get("page", "1"))
        if req.url.host == "lsst.test":
            if lsst_status != 200:
                return httpx.Response(lsst_status)
            items = load_fixture("lsst_objects.json")["items"] if page == 1 else []
            return httpx.Response(200, json={"items": items})
        if req.url.host == "ztf.test":
            if ztf_status != 200:
                return httpx.Response(ztf_status)
            if page > 1:
                return httpx.Response(200, json={"items": []})
            items = load_fixture("ztf_objects.json")["items"]
            clf = req.url.params.get("classifier")
            for it in items:  # ZTF only reports class for the filtered classifier
                if clf and it.get("class"):
                    it["classifier"] = clf
            return httpx.Response(200, json={"items": items})
        return httpx.Response(404)

    return handler


def _count(dsn, sql):
    with psycopg.connect(dsn) as c:
        return c.execute(sql).fetchone()[0]


def test_ingest_end_to_end_and_idempotent(ingest_dsn, make_client):
    client, _seen = make_client(alerce())
    store = Store.connect(ingest_dsn)
    try:
        res = run(store, client, trigger="cli", cfg=Config(page_size=100), now=NOW)
        assert res.status == "success", res.errors
        n_lsst = len(load_fixture("lsst_objects.json")["items"])
        n_ztf = len(load_fixture("ztf_objects.json")["items"])
        assert _count(ingest_dsn, "SELECT count(*) FROM objects") == n_lsst + n_ztf
        first_cls = _count(ingest_dsn, "SELECT count(*) FROM classifications")
        assert first_cls > 0

        res2 = run(store, client, trigger="cli", cfg=Config(page_size=100), now=NOW)
        assert res2.status == "success"
        assert _count(ingest_dsn, "SELECT count(*) FROM objects") == n_lsst + n_ztf
        assert _count(ingest_dsn, "SELECT count(*) FROM classifications") == first_cls
        runs = _count(ingest_dsn, "SELECT count(*) FROM ingest_runs WHERE status='success'")
        assert runs == 2
        # lc_classifier ran after stamp, so it owns top_classifier for ZTF rows that have a class
        top = _count(
            ingest_dsn,
            "SELECT count(*) FROM objects WHERE survey='ztf' AND top_classifier='lc_classifier'",
        )
        assert top > 0
    finally:
        store.close()


def test_one_source_down_is_partial_and_logged(ingest_dsn, make_client):
    client, _ = make_client(alerce(lsst_status=404))
    store = Store.connect(ingest_dsn)
    try:
        res = run(store, client, cfg=Config(), now=NOW)
    finally:
        store.close()
    assert res.status == "partial"
    with psycopg.connect(ingest_dsn) as c:
        status, n_err, errs = c.execute(
            "SELECT status, error_count, errors FROM ingest_runs ORDER BY id DESC LIMIT 1"
        ).fetchone()
    assert status == "partial" and n_err == 1 and errs[0]["source"] == "lsst:default"


def test_all_sources_down_is_failed(ingest_dsn, make_client):
    client, _ = make_client(alerce(lsst_status=404, ztf_status=404))
    store = Store.connect(ingest_dsn)
    try:
        res = run(store, client, cfg=Config(), now=NOW)
    finally:
        store.close()
    assert res.status == "failed"


def test_lease_prevents_concurrent_runs(ingest_dsn, make_client):
    client, seen = make_client(alerce())
    holder = Store.connect(ingest_dsn)
    store = Store.connect(ingest_dsn)
    try:
        assert holder.start_run("cli", ["lsst"]) is not None  # live 'running' row
        res = run(store, client, cfg=Config(), now=NOW)
        assert res.status == "skipped" and res.run_id is None and seen == []
    finally:
        holder.close()
        store.close()


def test_abandoned_lease_is_reclaimed(ingest_dsn, make_client):
    admin = conninfo.make_conninfo(
        ADMIN_URL, dbname=conninfo.conninfo_to_dict(ingest_dsn)["dbname"]
    )
    with psycopg.connect(admin, autocommit=True) as c:
        c.execute(
            "INSERT INTO ingest_runs (trigger, surveys, started_at)"
            " VALUES ('cron', '{lsst}', now() - interval '1 hour')"
        )
    client, _ = make_client(alerce())
    store = Store.connect(ingest_dsn)
    try:
        res = run(store, client, cfg=Config(), now=NOW)
    finally:
        store.close()
    assert res.status == "success"
    with psycopg.connect(ingest_dsn) as c:
        statuses = [r[0] for r in c.execute("SELECT status FROM ingest_runs ORDER BY id")]
    assert statuses == ["failed", "success"]


def test_page_cap_before_floor_is_partial(ingest_dsn, make_client):
    full = load_fixture("lsst_objects.json")["items"]

    def handler(req):
        page = int(req.url.params["page"])
        items = [dict(it, oid=int(f"{page}{i:03d}"), lastmjd=61344.9) for i, it in enumerate(full)]
        return httpx.Response(200, json={"items": items})

    client, _ = make_client(handler)
    store = Store.connect(ingest_dsn)
    try:
        res = run(
            store,
            client,
            surveys=("lsst",),
            cfg=Config(page_size=len(full), max_pages_per_source=2),
            now=NOW,
        )
    finally:
        store.close()
    assert res.status == "partial"
    assert any(e["source"] == "paging" for e in res.errors)


def test_bad_row_does_not_sink_run(ingest_dsn, make_client):
    items = load_fixture("lsst_objects.json")["items"]
    bad = dict(items[0], oid=42, ranking=40000, n_det="3000000000", class_name="VS\ud800x")

    def handler(req):
        if req.url.host == "lsst.test" and req.url.params.get("page") == "1":
            return httpx.Response(
                200,
                content=__import__("json").dumps({"items": [bad, *items[1:]]}).encode(),
                headers={"content-type": "application/json"},
            )
        return httpx.Response(200, json={"items": []})

    client, _ = make_client(handler)
    store = Store.connect(ingest_dsn)
    try:
        res = run(store, client, surveys=("lsst",), cfg=Config(), now=NOW)
    finally:
        store.close()
    assert res.status == "success", res.errors
    with psycopg.connect(ingest_dsn) as c:
        (ndet,) = c.execute("SELECT ndet FROM objects WHERE oid = '42'").fetchone()
    assert ndet is None


def test_stamp_never_overwrites_lc_top_class(ingest_dsn):
    from skyalerts_ingest.normalize import normalize_object

    store = Store.connect(ingest_dsn)
    try:
        run_id = store.start_run("cli", ["ztf"])
        base = {"oid": "ZTF26x", "meanra": 1.0, "meandec": 1.0, "lastmjd": 61344.0}
        lc = normalize_object(
            "ztf", base | {"class": "SNIa", "classifier": "lc_classifier", "probability": 0.8}
        )
        st = normalize_object(
            "ztf", base | {"class": "SN", "classifier": "stamp_classifier", "probability": 0.9}
        )
        store.upsert_batch(run_id, [lc[0]], [lc[1]])
        store.upsert_batch(run_id, [st[0]], [st[1]])
    finally:
        store.close()
    with psycopg.connect(ingest_dsn) as c:
        row = c.execute(
            "SELECT top_class, top_classifier FROM objects WHERE oid='ZTF26x'"
        ).fetchone()
        n = c.execute("SELECT count(*) FROM classifications WHERE oid='ZTF26x'").fetchone()[0]
    assert row == ("SNIa", "lc_classifier") and n == 2


def test_time_budget_marks_partial(ingest_dsn, make_client):
    client, _ = make_client(alerce())
    ticks = iter([0.0] + [1000.0] * 50)
    store = Store.connect(ingest_dsn)
    try:
        res = run(
            store, client, cfg=Config(time_budget_s=10), now=NOW, monotonic=lambda: next(ticks)
        )
    finally:
        store.close()
    assert res.status == "partial" and res.objects_seen == 0
