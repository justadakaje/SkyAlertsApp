"""End-to-end ingest against real Postgres + mocked ALeRCE.

Needs TEST_DATABASE_URL (superuser on a throwaway server). Applies the real
db/migrations, then runs ingest as skyalerts_ingest to prove the grants suffice.
"""

from __future__ import annotations

import importlib.util
import itertools
import os
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import psycopg
import pytest
from psycopg import conninfo

from skyalerts_ingest.ingest import LSST_STAMP_CLASSIFIER, Config, Source, run
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


def alerce(lsst_status=200, ztf_status=200, enrich_status=200):
    def handler(req: httpx.Request) -> httpx.Response:
        page = int(req.url.params.get("page", "1"))
        if req.url.host == "lsst.test":
            if req.url.path == "/lightcurve_api/detections":
                if enrich_status != 200:
                    return httpx.Response(enrich_status)
                return httpx.Response(200, json=load_fixture("lsst_detections_live.json"))
            if req.url.path == "/probability_api/probability":
                if enrich_status != 200:
                    return httpx.Response(enrich_status)
                return httpx.Response(200, json=load_fixture("lsst_probabilities_live.json"))
            if lsst_status != 200:
                return httpx.Response(lsst_status)
            items = load_fixture("lsst_objects.json")["items"] if page == 1 else []
            return httpx.Response(200, json={"items": items})
        if req.url.host == "ztf.test":
            if req.url.path.endswith("/detections"):
                if enrich_status != 200:
                    return httpx.Response(enrich_status)
                return httpx.Response(200, json=load_fixture("ztf_detections_live.json"))
            if req.url.path.endswith("/probabilities"):
                if enrich_status != 200:
                    return httpx.Response(enrich_status)
                return httpx.Response(200, json=load_fixture("ztf_probabilities_live.json"))
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
        # 2 non-bogus/asteroid LSST objects + 6 ZTF objects = 8 enriched
        assert res.objects_enriched == 8
        assert res.detections_upserted == 2 * 20 + 6 * 32
        assert _count(ingest_dsn, "SELECT count(*) FROM detections") == res.detections_upserted
        first_cls = _count(ingest_dsn, "SELECT count(*) FROM classifications")
        assert first_cls > 0

        res2 = run(store, client, trigger="cli", cfg=Config(page_size=100), now=NOW)
        assert res2.status == "success"
        assert res2.objects_enriched == 0 and res2.detections_upserted == 0
        assert _count(ingest_dsn, "SELECT count(*) FROM objects") == n_lsst + n_ztf
        assert _count(ingest_dsn, "SELECT count(*) FROM classifications") == first_cls
        assert _count(ingest_dsn, "SELECT count(*) FROM detections") == res.detections_upserted
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
    assert status == "partial" and n_err == 2
    assert [e["source"] for e in errs] == ["lsst:default", f"lsst:{LSST_STAMP_CLASSIFIER}:SN"]


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


# -- catch-up window (docs/decisions.md #24) ----------------------------------

SAMPLE = Source("lsst", complete=False, max_pages=2)
SN = Source("lsst", "clf", "SN", max_pages=3)
VS = Source("lsst", "clf", "VS", max_pages=3)
_oids = itertools.count(1)


def night(newest, n, *, cls="SN"):
    """n LSST list rows 0.01 d apart, newest first: a synthetic observing night."""
    base = load_fixture("lsst_objects.json")["items"][0]
    return [
        dict(base, oid=next(_oids), lastmjd=round(newest - i * 0.01, 5), class_name=cls)
        for i in range(n)
    ]


NIGHT1 = night(61343.3, 5)
OLD = night(61342.3, 10)


def serve_list(items, fail_class=None):
    """Serve `items` like ALeRCE list_objects: newest first, paged, filtered by class_name."""

    def handler(req: httpx.Request) -> httpx.Response:
        if req.url.path != "/object_api/list_objects":
            return httpx.Response(200, json=[])
        cls = req.url.params.get("class_name")
        if cls is not None and cls == fail_class:
            return httpx.Response(404)
        sel = sorted(
            (it for it in items if cls in (None, it["class_name"])),
            key=lambda it: it["lastmjd"],
            reverse=True,
        )
        size, page = int(req.url.params["page_size"]), int(req.url.params["page"])
        return httpx.Response(200, json={"items": sel[(page - 1) * size : page * size]})

    return handler


def ingest_lsst(dsn, make_client, items, sources, *, now=NOW, fail_class=None, **cfg):
    client, _ = make_client(serve_list(items, fail_class), max_attempts=1)
    store = Store.connect(dsn)
    try:
        return run(
            store,
            client,
            surveys=("lsst",),
            sources=sources,
            cfg=Config(page_size=10, enrich_max_objects=0, **cfg),
            now=now,
        )
    finally:
        store.close()


def watermark(dsn, source):
    store = Store.connect(dsn)
    try:
        return store.source_watermark(source)
    finally:
        store.close()


def test_capped_sample_source_is_success(ingest_dsn, make_client):
    # Production run 1: the unfiltered LSST stream overran the page cap every day.
    items = night(61344.3, 60, cls="AGN") + night(61344.295, 4)
    res = ingest_lsst(ingest_dsn, make_client, items, (SAMPLE, SN))
    assert res.status == "success" and res.errors == []
    assert (res.coverage[SAMPLE.key].outcome, res.coverage[SAMPLE.key].pages) == ("sample", 2)
    assert res.coverage[SN.key].outcome == "complete"


def test_cap_reached_without_gap_is_success(ingest_dsn, make_client):
    assert ingest_lsst(ingest_dsn, make_client, OLD + NIGHT1, (SN,)).status == "success"
    assert watermark(ingest_dsn, SN.key) == pytest.approx(61343.3)
    # 15 new rows. Floor = 61343.3 - 1 d overlap, and the 3rd (last allowed) page gets
    # below it: the cap was reached, but every row since the last watermark was read.
    res = ingest_lsst(ingest_dsn, make_client, OLD + NIGHT1 + night(61344.3, 15), (SN,))
    cov = res.coverage[SN.key]
    assert res.status == "success", res.errors
    assert (cov.outcome, cov.pages) == ("complete", 3)
    assert cov.floor_mjd == pytest.approx(61342.3)
    assert watermark(ingest_dsn, SN.key) == pytest.approx(61344.3)


def test_cap_reached_with_possible_gap_is_partial_and_recorded(ingest_dsn, make_client):
    ingest_lsst(ingest_dsn, make_client, OLD + NIGHT1, (SN,))
    busy = OLD + NIGHT1 + night(61344.3, 25)  # 3 pages can't get back to 61342.3
    res = ingest_lsst(ingest_dsn, make_client, busy, (SN,))
    cov = res.coverage[SN.key]
    assert res.status == "partial"
    assert (cov.outcome, cov.pages) == ("capped", 3)
    [gap] = res.errors
    assert gap["source"] == SN.key
    assert gap["gap_mjd"] == [pytest.approx(61342.3), pytest.approx(61343.26)]
    with psycopg.connect(ingest_dsn) as c:
        status, errs, stored = c.execute(
            "SELECT status, errors, coverage FROM ingest_runs ORDER BY id DESC LIMIT 1"
        ).fetchone()
    assert status == "partial" and errs == [gap]
    assert stored[SN.key]["outcome"] == "capped" and stored[SN.key]["advances"] is True
    # The gap is on record, so the window moves on and the next quiet run is clean.
    again = ingest_lsst(ingest_dsn, make_client, busy, (SN,))
    assert again.status == "success" and again.errors == []
    assert again.coverage[SN.key].floor_mjd == pytest.approx(61343.3)


def test_window_advances_across_consecutive_successful_runs(ingest_dsn, make_client):
    items = OLD + NIGHT1
    res = ingest_lsst(ingest_dsn, make_client, items, (SN,))
    assert res.coverage[SN.key].floor_mjd == pytest.approx(61343.3 - 1.2)  # no watermark yet
    prev = 61343.3
    for day in range(3):
        newest = 61344.3 + day
        items = [*items, *night(newest, 8)]
        res = ingest_lsst(ingest_dsn, make_client, items, (SN,), now=NOW + timedelta(days=day))
        cov = res.coverage[SN.key]
        assert res.status == "success", res.errors
        assert cov.floor_mjd == pytest.approx(prev - 1.0)  # last watermark - overlap
        assert cov.oldest_mjd < cov.floor_mjd and cov.pages == 2  # stopped just past it
        assert watermark(ingest_dsn, SN.key) == pytest.approx(newest)
        prev = newest
    with psycopg.connect(ingest_dsn) as c:
        statuses = [r[0] for r in c.execute("SELECT status FROM ingest_runs ORDER BY id")]
    assert statuses == ["success"] * 4


def test_failed_source_keeps_its_window_while_others_advance(ingest_dsn, make_client):
    items = NIGHT1 + night(61343.3, 5, cls="VS")
    ingest_lsst(ingest_dsn, make_client, items, (SN, VS))
    items = items + night(61344.3, 5) + night(61344.3, 5, cls="VS")
    res = ingest_lsst(ingest_dsn, make_client, items, (SN, VS), fail_class="SN")
    assert res.status == "partial"
    assert (res.coverage[SN.key].outcome, res.coverage[VS.key].outcome) == ("error", "complete")
    assert watermark(ingest_dsn, SN.key) == pytest.approx(61343.3)  # re-covered next run
    assert watermark(ingest_dsn, VS.key) == pytest.approx(61344.3)


def test_future_lastmjd_does_not_lift_the_window(ingest_dsn, make_client):
    glitch = night(61400.0, 1)  # 55 days ahead of the wall clock
    res = ingest_lsst(ingest_dsn, make_client, glitch + NIGHT1, (SN,))
    assert res.status == "success"
    assert watermark(ingest_dsn, SN.key) == pytest.approx(61343.3)


def test_stale_filtered_source_is_partial(ingest_dsn, make_client):
    # A renamed classifier leaves its old list frozen, yet it still "completes" daily.
    sn = Source("lsst", "clf", "SN", stale_after_days=2.0)
    items = night(61344.3, 5, cls="AGN") + night(61341.0, 5)
    res = ingest_lsst(ingest_dsn, make_client, items, (SAMPLE, sn))
    assert res.status == "partial" and res.coverage[sn.key].outcome == "complete"
    assert [e["source"] for e in res.errors] == [sn.key]
    assert res.errors[0]["error"].startswith("stale: 3.3 d behind newest lsst row")


def test_window_older_than_max_lookback_is_a_recorded_gap(ingest_dsn, make_client):
    ingest_lsst(ingest_dsn, make_client, night(61330.0, 3), (SN,))
    items = night(61330.0, 3) + night(61337.0, 3) + night(61344.3, 5)
    res = ingest_lsst(ingest_dsn, make_client, items, (SN,))
    [gap] = res.errors
    assert res.status == "partial" and res.coverage[SN.key].outcome == "complete"
    assert gap["gap_mjd"] == [pytest.approx(61329.0), pytest.approx(61337.3)]
    assert watermark(ingest_dsn, SN.key) == pytest.approx(61344.3)  # clean from here on


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
    client, seen = make_client(alerce())
    ticks = iter([0.0] + [1000.0] * 50)
    store = Store.connect(ingest_dsn)
    try:
        res = run(
            store, client, cfg=Config(time_budget_s=10), now=NOW, monotonic=lambda: next(ticks)
        )
    finally:
        store.close()
    assert res.status == "partial" and res.objects_seen == 0 and res.objects_enriched == 0
    assert seen == []


def test_enrichment_candidates_ordering_and_filtering(ingest_dsn):
    from skyalerts_ingest.normalize import ObjectRow

    def mk(oid, cls, prob, mjd):
        return ObjectRow(
            survey="ztf",
            oid=oid,
            meanra=10.0,
            meandec=10.0,
            firstmjd=mjd - 1.0,
            lastmjd=mjd,
            ndet=5,
            n_forced=None,
            stellar=False,
            top_class=cls,
            top_classifier="lc_classifier" if cls else None,
            top_classifier_version="1.0" if cls else None,
            top_probability=prob,
            raw={"oid": oid},
        )

    store = Store.connect(ingest_dsn)
    try:
        r1 = store.start_run("cli", ["ztf"])
        store.upsert_batch(r1, [mk("other_run", "SNIa", 0.99, 61344.9)], [])
        store.finish_run(
            r1,
            status="success",
            objects_seen=1,
            objects_upserted=1,
            classifications_upserted=0,
            requests=1,
            errors=[],
            duration_ms=10,
        )

        r2 = store.start_run("cli", ["ztf"])
        objs = [
            mk("bogus1", "bogus", 0.99, 61344.9),
            mk("ast1", "asteroid", 0.99, 61344.9),
            mk("agn_hi", "AGN", 0.95, 61344.9),  # tier 3
            mk("blazar_lo", "Blazar", 0.60, 61344.8),  # tier 3
            mk("vs_hi", "RRL", 0.90, 61344.5),  # tier 2
            mk("vs_null", None, None, 61344.9),  # tier 2 (null prob last)
            mk("sn_lo_older", "SNII", 0.70, 61344.1),  # tier 1
            mk("sn_lo_newer", "TDE", 0.70, 61344.8),  # tier 1 (tie-break by lastmjd DESC)
            mk("sn_hi", "SNIa", 0.92, 61344.2),  # tier 1
            mk("already_fresh", "SN", 0.99, 61344.0),  # will be marked enriched at 61344.0
            mk("re_brightened", "KN", 0.85, 61344.5),  # enriched at 61343.0, then new det
        ]
        store.upsert_batch(r2, objs, [])
        store.enrich_object("ztf", "already_fresh", [], [])
        with psycopg.connect(ingest_dsn, autocommit=True) as c:
            c.execute(
                "UPDATE objects SET enriched_at = now(), enriched_lastmjd = 61343.0"
                " WHERE oid = 're_brightened'"
            )

        cands = store.enrichment_candidates(r2, limit=20)
        assert [oid for _, oid in cands] == [
            "sn_hi",
            "re_brightened",
            "sn_lo_newer",
            "sn_lo_older",
            "vs_hi",
            "vs_null",
            "agn_hi",
            "blazar_lo",
        ]
        assert len(store.enrichment_candidates(r2, limit=3)) == 3
        assert store.enrichment_candidates(r2, limit=0) == []
    finally:
        store.close()


def test_enrich_object_idempotent_and_updates_when_lastmjd_advances(ingest_dsn):
    from skyalerts_ingest.normalize import (
        normalize_detection,
        normalize_object,
        normalize_probability,
    )

    store = Store.connect(ingest_dsn)
    try:
        r1 = store.start_run("cli", ["lsst"])
        raw_obj = dict(load_fixture("lsst_objects.json")["items"][0], oid=313708285401235521)
        obj, cls = normalize_object("lsst", raw_obj)
        store.upsert_batch(r1, [obj], [cls])

        dets = [
            normalize_detection("lsst", obj.oid, r)
            for r in load_fixture("lsst_detections_live.json")[:5]
        ]
        probs = [
            normalize_probability("lsst", obj.oid, r)
            for r in load_fixture("lsst_probabilities_live.json")[:4]
        ]
        n_d, n_c = store.enrich_object("lsst", obj.oid, dets, probs)
        assert (n_d, n_c) == (5, 4)
        assert store.enrichment_candidates(r1, 10) == []

        # Re-enriching with overlapping data updates in place without duplicating rows
        dets_updated = [
            dets[0],
            normalize_detection("lsst", obj.oid, load_fixture("lsst_detections_live.json")[5]),
        ]
        store.enrich_object("lsst", obj.oid, dets_updated, probs)
        assert _count(ingest_dsn, "SELECT count(*) FROM detections") == 6

        # Advancing lastmjd makes the object eligible again
        newer_obj, _ = normalize_object("lsst", raw_obj | {"lastmjd": obj.lastmjd + 1.0})
        store.upsert_batch(r1, [newer_obj], [])
        assert store.enrichment_candidates(r1, 10) == [("lsst", obj.oid)]
    finally:
        store.close()


def test_enrichment_caps_detections_and_probabilities(ingest_dsn, make_client):
    base_det = load_fixture("ztf_detections_live.json")[0]
    many_dets = [dict(base_det, candid=f"c{i}", mjd=60000.0 + i) for i in range(250)]
    # Group 1: has explicit rankings 1..5 -> keep 3. Group 2: missing rankings -> top 3 by prob.
    probs = [
        {
            "classifier_name": "clf_a",
            "classifier_version": "1",
            "class_name": f"c{i}",
            "probability": 0.1 * i,
            "ranking": i,
        }
        for i in range(1, 6)
    ] + [
        {
            "classifier_name": "clf_b",
            "classifier_version": "1",
            "class_name": f"u{i}",
            "probability": p,
        }
        for i, p in enumerate([0.05, 0.50, 0.20, 0.30, 0.01])
    ]

    def handler(req: httpx.Request) -> httpx.Response:
        if req.url.path.endswith("/detections"):
            return httpx.Response(200, json=many_dets)
        if req.url.path.endswith("/probabilities"):
            return httpx.Response(200, json=probs)
        if (
            req.url.params.get("page") == "1"
            and req.url.params.get("classifier") == "lc_classifier"
        ):
            it = dict(load_fixture("ztf_objects.json")["items"][0], oid="ZTF26cap")
            return httpx.Response(200, json={"items": [it]})
        return httpx.Response(200, json={"items": []})

    client, _ = make_client(handler)
    store = Store.connect(ingest_dsn)
    try:
        res = run(store, client, surveys=("ztf",), cfg=Config(), now=NOW)
    finally:
        store.close()
    assert res.status == "success"
    assert res.objects_enriched == 1 and res.detections_upserted == 200
    with psycopg.connect(ingest_dsn) as c:
        min_mjd = c.execute("SELECT min(mjd) FROM detections WHERE oid='ZTF26cap'").fetchone()[0]
        b_classes = [
            r[0]
            for r in c.execute(
                "SELECT class_name FROM classifications"
                " WHERE oid='ZTF26cap' AND classifier_name='clf_b' ORDER BY probability DESC"
            )
        ]
        a_count = c.execute(
            "SELECT count(*) FROM classifications WHERE oid='ZTF26cap' AND classifier_name='clf_a'"
        ).fetchone()[0]
    assert min_mjd == 60050.0  # 200 newest out of 60000..60249
    assert a_count == 3
    assert b_classes == ["u1", "u3", "u2"]


def test_enrichment_failure_leaves_status_success(ingest_dsn, make_client):
    client, _ = make_client(alerce(enrich_status=404), max_attempts=1)
    store = Store.connect(ingest_dsn)
    try:
        res = run(store, client, surveys=("lsst",), cfg=Config(), now=NOW)
    finally:
        store.close()
    assert res.status == "success"
    assert res.objects_enriched == 0 and res.detections_upserted == 0
    assert len(res.errors) == 2 and all(e["source"] == "enrich" for e in res.errors)
    with psycopg.connect(ingest_dsn) as c:
        row = c.execute(
            "SELECT status, objects_enriched, detections_upserted, error_count"
            " FROM ingest_runs ORDER BY id DESC LIMIT 1"
        ).fetchone()
    assert row == ("success", 0, 0, 2)


def test_unexpected_enrichment_error_is_isolated(ingest_dsn, make_client, monkeypatch):
    client, _ = make_client(alerce())
    real = client.detections
    calls = []

    def flaky(survey, oid):
        calls.append(oid)
        if len(calls) == 1:
            raise RuntimeError("unexpected payload")
        return real(survey, oid)

    monkeypatch.setattr(client, "detections", flaky)
    store = Store.connect(ingest_dsn)
    try:
        res = run(store, client, surveys=("lsst",), cfg=Config(), now=NOW)
    finally:
        store.close()
    assert res.status == "success"
    assert len(calls) == 2 and res.objects_enriched == 1
    assert [e["source"] for e in res.errors] == ["enrich"]
    assert res.errors[0]["error"].startswith("RuntimeError")


def test_enrichment_stops_on_budget_without_demoting_status(ingest_dsn, make_client):
    client, _ = make_client(alerce())
    # Start + LSST sample page + LSST SN page + 1st candidate, then budget expires
    ticks = iter([0.0, 1.0, 2.0, 3.0] + [500.0] * 20)
    store = Store.connect(ingest_dsn)
    try:
        res = run(
            store,
            client,
            surveys=("lsst",),
            cfg=Config(time_budget_s=10.0),
            now=NOW,
            monotonic=lambda: next(ticks),
        )
    finally:
        store.close()
    assert res.status == "success"
    assert res.objects_enriched == 1
