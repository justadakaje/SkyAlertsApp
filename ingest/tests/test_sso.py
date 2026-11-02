from __future__ import annotations

import importlib.util
import os
import uuid
from pathlib import Path

import httpx
import psycopg
import pytest
from psycopg import conninfo

from skyalerts_ingest.alerce_client import USER_AGENT
from skyalerts_ingest.normalize import ObjectRow
from skyalerts_ingest.sso import (
    SkyBotClient,
    SkyBotError,
    SkyBotHit,
    identify_run,
    parse_conesearch,
)
from skyalerts_ingest.store import Store
from tests.conftest import FIXTURES, FakeTime

ADMIN_URL = os.environ.get("TEST_DATABASE_URL")
requires_db = pytest.mark.skipif(not ADMIN_URL, reason="TEST_DATABASE_URL not set")

_spec = importlib.util.spec_from_file_location(
    "migrate", Path(__file__).resolve().parents[2] / "db" / "migrate.py"
)
migrate = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(migrate)

MATCH_TEXT = (FIXTURES / "skybot_conesearch_ztf_match.txt").read_text()


# -- parse_conesearch ---------------------------------------------------------


def test_parse_conesearch_fixture():
    hits = parse_conesearch(MATCH_TEXT)
    assert len(hits) == 6
    # Sorted by sep_arcsec ascending; closest is (9537) Nolan at 3.112"
    first = hits[0]
    assert first == SkyBotHit(
        sso_number=9537,
        sso_name="Nolan",
        sso_class="MB>Middle",
        predicted_mag=18.6,
        sep_arcsec=pytest.approx(3.112),
        ra_rate_arcsec_h=pytest.approx(64.3693),
        dec_rate_arcsec_h=pytest.approx(-30.380),
        geo_dist_au=pytest.approx(2.98479999685),
        helio_dist_au=pytest.approx(2.31008989764),
    )
    # Unnumbered object ("-") parses with sso_number=None
    unnumbered = next(h for h in hits if h.sso_name == "2026 BF3")
    assert unnumbered.sso_number is None
    assert unnumbered.sso_class == "MB>Outer"
    assert unnumbered.sep_arcsec == pytest.approx(164.350)
    assert [h.sep_arcsec for h in hits] == sorted(h.sep_arcsec for h in hits)


def test_parse_conesearch_empty_body_is_no_match():
    assert parse_conesearch("") == []
    assert parse_conesearch("   \n\t\n  ") == []


def test_parse_conesearch_negative_flag_and_malformed_raise():
    err_body = "# Flag: -1\n# Ticket: 188071323881221409\n# Error: invalid epoch\n"
    with pytest.raises(SkyBotError, match="flag: -1"):
        parse_conesearch(err_body)

    with pytest.raises(SkyBotError, match="Missing # Flag"):
        parse_conesearch("<html>upstream proxy error</html>")

    with pytest.raises(SkyBotError, match="Malformed SkyBoT row"):
        parse_conesearch("# Flag: 1\n9537 | Nolan | too_few_cols\n")


# -- SkyBotClient -------------------------------------------------------------


def test_client_sends_expected_params_and_user_agent(fake_time: FakeTime):
    seen: list[httpx.Request] = []

    def handler(req: httpx.Request) -> httpx.Response:
        seen.append(req)
        return httpx.Response(200, text=MATCH_TEXT)

    with SkyBotClient(
        url="https://skybot.test/conesearch.php",
        min_interval=1.0,
        transport=httpx.MockTransport(handler),
        sleep=fake_time.sleep,
        clock=fake_time.clock,
    ) as client:
        hits1 = client.conesearch("ztf", 175.7877305, 0.24302, 61342.55412039999)
        hits2 = client.conesearch("lsst", 10.5, -20.25, 61343.0)

    assert len(hits1) == 6 and hits1[0].sso_name == "Nolan"
    assert len(hits2) == 6
    assert client.request_count == 2
    assert fake_time.sleeps == [1.0]

    req_ztf, req_lsst = seen
    assert req_ztf.headers["User-Agent"] == USER_AGENT
    q_ztf = dict(req_ztf.url.params)
    assert float(q_ztf["-ep"]) == pytest.approx(61342.55412039999 + 2400000.5)
    assert float(q_ztf["-ra"]) == pytest.approx(175.7877305)
    assert float(q_ztf["-dec"]) == pytest.approx(0.24302)
    assert q_ztf["-rd"] == "0.003"
    assert q_ztf["-loc"] == "I41"
    assert q_ztf["-mime"] == "text"
    assert q_ztf["-output"] == "basic"

    q_lsst = dict(req_lsst.url.params)
    assert q_lsst["-loc"] == "X05"


def test_client_maps_http_and_transport_errors_without_echoing_body(fake_time: FakeTime):
    secret_body = "UPSTREAM_INTERNAL_STACK_TRACE_DO_NOT_STORE"

    def http_500(req: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text=secret_body)

    client = SkyBotClient(
        url="https://skybot.test/conesearch.php",
        transport=httpx.MockTransport(http_500),
        sleep=fake_time.sleep,
        clock=fake_time.clock,
    )
    with pytest.raises(SkyBotError, match="HTTP 500") as ei:
        client.conesearch("ztf", 10.0, 10.0, 61342.0)
    assert ei.value.status == 500
    assert secret_body not in str(ei.value)

    def timeout_handler(req: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout(secret_body, request=req)

    client_timeout = SkyBotClient(
        url="https://skybot.test/conesearch.php",
        transport=httpx.MockTransport(timeout_handler),
        sleep=fake_time.sleep,
        clock=fake_time.clock,
    )
    with pytest.raises(SkyBotError, match="ReadTimeout") as ei_t:
        client_timeout.conesearch("lsst", 10.0, 10.0, 61342.0)
    assert secret_body not in str(ei_t.value)

    with pytest.raises(ValueError, match="survey"):
        client.conesearch("ptf", 10.0, 10.0, 61342.0)


# -- Database integration (runs as skyalerts_ingest) --------------------------


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


def _mk_obj(
    survey: str,
    oid: str,
    *,
    cls: str = "asteroid",
    prob: float | None = 0.9,
    firstmjd: float = 61342.55412039999,
    lastmjd: float = 61344.0,
    ra: float = 175.7877305,
    dec: float = 0.24302,
) -> ObjectRow:
    return ObjectRow(
        survey=survey,
        oid=oid,
        meanra=ra,
        meandec=dec,
        firstmjd=firstmjd,
        lastmjd=lastmjd,
        ndet=4,
        n_forced=0,
        stellar=False,
        top_class=cls,
        top_classifier="stamp_classifier",
        top_classifier_version="1.0",
        top_probability=prob,
        raw={"oid": oid},
    )


@requires_db
def test_identify_selection_order_upserts_and_error_retry(ingest_dsn, fake_time: FakeTime):
    store = Store.connect(ingest_dsn)
    try:
        run_id = store.start_run("cli", ["ztf", "lsst"])
        assert run_id is not None
        objs = [
            _mk_obj("lsst", "lsst_hi", prob=0.99, lastmjd=61344.9, ra=10.0),
            _mk_obj("lsst", "lsst_lo", prob=0.70, lastmjd=61344.1, ra=20.0),
            _mk_obj("ztf", "ztf_lo_old", prob=0.80, lastmjd=61343.0, ra=30.0),
            _mk_obj("ztf", "ztf_lo_new", prob=0.80, lastmjd=61344.5, ra=40.0),
            _mk_obj("ztf", "ztf_hi", prob=0.95, lastmjd=61342.6, ra=175.7877305),
            _mk_obj("ztf", "not_asteroid", cls="SNIa", prob=0.99, lastmjd=61344.9, ra=50.0),
        ]
        store.upsert_batch(run_id, objs, [])

        # Respond based on RA so each object triggers a distinct outcome:
        # - ztf_hi (ra=175.7877305): fixture match -> (9537) Nolan at 3.112" (<= 10")
        # - ztf_lo_new (ra=40.0): closest row at 12.5" (> 10") -> no_match
        # - ztf_lo_old (ra=30.0): empty body -> no_match
        # - lsst_hi (ra=10.0): "# Flag: -1" -> error
        # - lsst_lo (ra=20.0): HTTP 503 -> error
        far_only = (
            "# Flag: 1\n"
            "# Num | Name | RA(h) | DE(deg) | Class | Mv | Err | d | dRA | dDEC | Dg | Dh\n"
            " - | 2026 BF3 | 11 43 15.6 | +00 12 23.1 | MB>Outer | 24.0 | 0.0 | 12.500"
            " | 43.5 | -23.3 | 3.83 | 3.13\n"
        )
        queried_ras: list[tuple[str, float]] = []

        def handler(req: httpx.Request) -> httpx.Response:
            loc = req.url.params["-loc"]
            ra = round(float(req.url.params["-ra"]), 1)
            queried_ras.append((loc, ra))
            if ra == 175.8:
                return httpx.Response(200, text=MATCH_TEXT)
            if ra == 40.0:
                return httpx.Response(200, text=far_only)
            if ra == 30.0:
                return httpx.Response(200, text="")
            if ra == 10.0:
                return httpx.Response(200, text="# Flag: -1\n# Error: ephemeris failure\n")
            return httpx.Response(503, text="upstream maintenance")

        client = SkyBotClient(
            url="https://skybot.test/conesearch.php",
            min_interval=0.0,
            transport=httpx.MockTransport(handler),
            sleep=fake_time.sleep,
            clock=fake_time.clock,
        )
        res = identify_run(store, client, max_objects=10, time_budget_s=240.0)
        assert res.as_dict() == {
            "queried": 5,
            "matched": 1,
            "no_match": 2,
            "errors": 2,
            "budget_hit": False,
        }
        # ZTF first (by top_probability DESC, then lastmjd DESC), then LSST
        assert queried_ras == [
            ("I41", 175.8),  # ztf_hi
            ("I41", 40.0),  # ztf_lo_new
            ("I41", 30.0),  # ztf_lo_old
            ("X05", 10.0),  # lsst_hi
            ("X05", 20.0),  # lsst_lo
        ]

        rows = {
            (r[0], r[1]): r[2:]
            for r in store.conn.execute(
                "SELECT survey, oid, status, sso_number, sso_name, sso_class,"
                " sep_arcsec, error FROM sso_identifications"
            ).fetchall()
        }
        assert rows[("ztf", "ztf_hi")][:4] == ("matched", 9537, "Nolan", "MB>Middle")
        assert rows[("ztf", "ztf_hi")][4] == pytest.approx(3.112)
        assert rows[("ztf", "ztf_hi")][5] is None
        assert rows[("ztf", "ztf_lo_new")] == ("no_match", None, None, None, None, None)
        assert rows[("ztf", "ztf_lo_old")] == ("no_match", None, None, None, None, None)
        assert rows[("lsst", "lsst_hi")][0] == "error"
        assert "flag: -1" in rows[("lsst", "lsst_hi")][5]
        assert rows[("lsst", "lsst_lo")][0] == "error"
        assert "HTTP 503" in rows[("lsst", "lsst_lo")][5]

        # Immediate re-run skips matched, no_match, and fresh (<1 day) errors
        queried_ras.clear()
        res_skip = identify_run(store, client, max_objects=10, time_budget_s=240.0)
        assert res_skip.queried == 0 and queried_ras == []

        # Backdate lsst_hi's error beyond 1 day; now only lsst_hi is retried and succeeds
        store.conn.execute(
            "UPDATE sso_identifications SET queried_at = now() - interval '25 hours'"
            " WHERE survey = 'lsst' AND oid = 'lsst_hi'"
        )
        ok_client = SkyBotClient(
            url="https://skybot.test/conesearch.php",
            min_interval=0.0,
            transport=httpx.MockTransport(lambda req: httpx.Response(200, text=MATCH_TEXT)),
            sleep=fake_time.sleep,
            clock=fake_time.clock,
        )
        res_retry = identify_run(store, ok_client, max_objects=10, time_budget_s=240.0)
        assert res_retry.as_dict() == {
            "queried": 1,
            "matched": 1,
            "no_match": 0,
            "errors": 0,
            "budget_hit": False,
        }
        updated = store.conn.execute(
            "SELECT status, sso_number, sso_name, error FROM sso_identifications"
            " WHERE survey = 'lsst' AND oid = 'lsst_hi'"
        ).fetchone()
        assert updated == ("matched", 9537, "Nolan", None)
    finally:
        store.close()


@requires_db
def test_identify_stops_on_time_budget(ingest_dsn, fake_time: FakeTime):
    store = Store.connect(ingest_dsn)
    try:
        run_id = store.start_run("cli", ["ztf"])
        assert run_id is not None
        store.upsert_batch(
            run_id,
            [
                _mk_obj("ztf", "ZTF26a", prob=0.95),
                _mk_obj("ztf", "ZTF26b", prob=0.90),
            ],
            [],
        )
        client = SkyBotClient(
            url="https://skybot.test/conesearch.php",
            min_interval=0.0,
            timeout=5.0,
            transport=httpx.MockTransport(lambda req: httpx.Response(200, text=MATCH_TEXT)),
            sleep=fake_time.sleep,
            clock=fake_time.clock,
        )
        # start; 1st object at 1 s (1 + 5 s timeout <= 10, ok); 2nd at 6 s (6 + 5 > 10:
        # a slow request could overrun the budget, so it is not started)
        ticks = iter([0.0, 1.0, 6.0])
        res = identify_run(
            store,
            client,
            max_objects=10,
            time_budget_s=10.0,
            monotonic=lambda: next(ticks),
        )
        assert res.as_dict() == {
            "queried": 1,
            "matched": 1,
            "no_match": 0,
            "errors": 0,
            "budget_hit": True,
        }
    finally:
        store.close()
