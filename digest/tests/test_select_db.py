"""Database integration tests for weekly digest selection.

Applies db/migrations via db/migrate.py against TEST_DATABASE_URL, inserts
sample objects and detections, and verifies selection rules as skyalerts_ro.
"""

from __future__ import annotations

import importlib.util
import json
import os
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import psycopg
import pytest
from psycopg import conninfo
from psycopg.types.json import Jsonb

from skyalerts_digest import web
from skyalerts_digest.__main__ import main as cli_main
from skyalerts_digest.config import DigestConfig
from skyalerts_digest.render import render_html, render_markdown
from skyalerts_digest.select import Digest, datetime_to_mjd, select_digest
from skyalerts_digest.send import RESEND_EMAILS_URL, send_digest

ADMIN_URL = os.environ.get("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not ADMIN_URL, reason="TEST_DATABASE_URL not set")

WEEK_END = datetime(2026, 11, 1, tzinfo=UTC)  # MJD 61345.0
END_MJD = datetime_to_mjd(WEEK_END)
START_MJD = END_MJD - 7.0  # MJD 61338.0

_spec = importlib.util.spec_from_file_location(
    "migrate", Path(__file__).resolve().parents[2] / "db" / "migrate.py"
)
assert _spec is not None and _spec.loader is not None
migrate = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(migrate)


@pytest.fixture
def db_urls() -> Any:
    assert ADMIN_URL is not None
    name = f"t_digest_{uuid.uuid4().hex[:10]}"
    with psycopg.connect(ADMIN_URL, autocommit=True) as c:
        c.execute(f'CREATE DATABASE "{name}"')
    admin_dsn = conninfo.make_conninfo(ADMIN_URL, dbname=name)
    migrate.migrate(admin_dsn)
    with psycopg.connect(ADMIN_URL, autocommit=True) as c:
        c.execute("ALTER ROLE skyalerts_ro PASSWORD 'test-ro-password'")
    ro_dsn = conninfo.make_conninfo(admin_dsn, user="skyalerts_ro", password="test-ro-password")
    try:
        yield admin_dsn, ro_dsn
    finally:
        with psycopg.connect(ADMIN_URL, autocommit=True) as c:
            c.execute(f'DROP DATABASE "{name}" WITH (FORCE)')


def _insert_object(
    conn: psycopg.Connection[Any],
    *,
    survey: str = "ztf",
    oid: str,
    top_class: str | None,
    top_probability: float | None = 0.9,
    firstmjd: float,
    lastmjd: float | None = None,
    ndet: int = 5,
) -> None:
    conn.execute(
        """INSERT INTO objects (survey, oid, meanra, meandec, firstmjd, lastmjd, ndet,
                                top_class, top_classifier, top_probability, raw)
           VALUES (%s, %s, 10.0, 20.0, %s, %s, %s, %s, 'lc_classifier', %s, %s)""",
        (
            survey,
            oid,
            firstmjd,
            lastmjd if lastmjd is not None else firstmjd + 0.5,
            ndet,
            top_class,
            top_probability,
            Jsonb({"oid": oid}),
        ),
    )


def _insert_detection(
    conn: psycopg.Connection[Any],
    *,
    survey: str = "ztf",
    oid: str,
    measurement_id: str,
    mjd: float,
    mag: float | None,
    band: str | None = "g",
) -> None:
    conn.execute(
        """INSERT INTO detections (survey, oid, measurement_id, mjd, band, mag, raw)
           VALUES (%s, %s, %s, %s, %s, %s, %s)""",
        (survey, oid, measurement_id, mjd, band, mag, Jsonb({"id": measurement_id})),
    )


def test_select_digest_excludes_bogus_and_orders_correctly(db_urls: tuple[str, str]) -> None:
    admin_dsn, ro_dsn = db_urls
    with psycopg.connect(admin_dsn, autocommit=True) as conn:
        # Bogus artifact in the week with high probability and bright detection -> excluded
        _insert_object(
            conn,
            oid="ZTF26bogus",
            top_class="bogus",
            top_probability=0.99,
            firstmjd=END_MJD - 1.0,
        )
        _insert_detection(
            conn,
            oid="ZTF26bogus",
            measurement_id="det_bogus",
            mjd=END_MJD - 0.5,
            mag=12.0,
        )

        # 6 transient-tier objects in the week to test ordering & LIMIT 5
        _insert_object(
            conn,
            oid="ZTF26sn_top",
            top_class="SNIa",
            top_probability=0.98,
            firstmjd=END_MJD - 2.0,
            lastmjd=END_MJD - 1.0,
        )
        _insert_object(
            conn,
            oid="ZTF26tde_tie_newer",
            top_class="TDE",
            top_probability=0.90,
            firstmjd=END_MJD - 3.0,
            lastmjd=END_MJD - 0.2,
        )
        _insert_object(
            conn,
            oid="ZTF26kn_tie_older",
            top_class="KN",
            top_probability=0.90,
            firstmjd=END_MJD - 3.0,
            lastmjd=END_MJD - 1.5,
        )
        _insert_object(
            conn,
            oid="ZTF26slsn",
            top_class="SLSN",
            top_probability=0.85,
            firstmjd=END_MJD - 4.0,
        )
        _insert_object(
            conn,
            oid="ZTF26cv",
            top_class="CV/Nova",
            top_probability=0.80,
            firstmjd=END_MJD - 5.0,
        )
        _insert_object(
            conn,
            oid="ZTF26sn_sixth",
            top_class="SNII",
            top_probability=0.70,
            firstmjd=END_MJD - 6.0,
        )

        # Non-transient objects in the week (should NOT appear in headliners)
        _insert_object(
            conn,
            oid="ZTF26agn",
            top_class="AGN",
            top_probability=0.99,
            firstmjd=END_MJD - 1.0,
        )
        _insert_object(
            conn,
            oid="ZTF26rrl",
            top_class="RRL",
            top_probability=0.95,
            firstmjd=END_MJD - 2.0,
        )

        # 4 asteroids in the week -> count = 4, up to 3 examples
        for i, prob in enumerate((0.99, 0.95, 0.90, 0.85), start=1):
            _insert_object(
                conn,
                oid=f"ZTF26ast{i}",
                top_class="asteroid",
                top_probability=prob,
                firstmjd=END_MJD - 1.0,
            )
            _insert_detection(
                conn,
                oid=f"ZTF26ast{i}",
                measurement_id=f"det_ast{i}",
                mjd=END_MJD - 0.9,
                mag=13.0,  # bright, but asteroids must be excluded from Brightest new
            )

        # Detections for non-bogus, non-asteroid objects in the week
        # ZTF26agn has two detections (17.5 and 15.2) -> min mag is 15.2
        _insert_detection(conn, oid="ZTF26agn", measurement_id="d1", mjd=END_MJD - 0.8, mag=17.5)
        _insert_detection(
            conn, oid="ZTF26agn", measurement_id="d2", mjd=END_MJD - 0.5, mag=15.2, band="r"
        )
        _insert_detection(
            conn, oid="ZTF26sn_top", measurement_id="d3", mjd=END_MJD - 0.9, mag=16.1, band="g"
        )
        _insert_detection(
            conn, oid="ZTF26rrl", measurement_id="d4", mjd=END_MJD - 1.2, mag=16.8, band="g"
        )
        _insert_detection(
            conn, oid="ZTF26slsn", measurement_id="d5", mjd=END_MJD - 2.0, mag=18.4, band="i"
        )
        # Flux-only detection (mag=None) on ZTF26cv should not qualify it as brightest
        _insert_detection(
            conn, oid="ZTF26cv", measurement_id="d6", mjd=END_MJD - 2.0, mag=None, band="g"
        )

    with psycopg.connect(ro_dsn, autocommit=True) as ro_conn:
        digest = select_digest(ro_conn, WEEK_END)

    assert isinstance(digest, Digest)
    assert [h.oid for h in digest.headliners] == [
        "ZTF26sn_top",
        "ZTF26tde_tie_newer",
        "ZTF26kn_tie_older",
        "ZTF26slsn",
        "ZTF26cv",
    ]

    assert [b.oid for b in digest.brightest] == [
        "ZTF26agn",
        "ZTF26sn_top",
        "ZTF26rrl",
    ]
    assert digest.brightest[0].peak_mag == pytest.approx(15.2)
    assert digest.brightest[0].peak_band == "r"

    assert digest.solar_system.asteroid_count == 4
    assert [a.oid for a in digest.solar_system.examples] == [
        "ZTF26ast1",
        "ZTF26ast2",
        "ZTF26ast3",
    ]

    # Week in numbers (bogus object & its detection excluded)
    assert digest.stats.count_for("transient") == 6
    assert digest.stats.count_for("stochastic") == 1
    assert digest.stats.count_for("variable") == 1
    assert digest.stats.count_for("solar") == 4
    assert digest.stats.count_for("other") == 0
    assert digest.stats.new_objects == 12
    assert digest.stats.total_objects == 12
    # 4 asteroid detections + 6 object detections = 10 (bogus detection excluded)
    assert digest.stats.total_detections == 10


def test_week_boundaries_and_empty_brightest(db_urls: tuple[str, str]) -> None:
    admin_dsn, ro_dsn = db_urls
    with psycopg.connect(admin_dsn, autocommit=True) as conn:
        # Older than week_start (START_MJD - 0.1) -> excluded from week, counted in total_objects
        _insert_object(
            conn,
            oid="ZTF26old",
            top_class="SNIa",
            top_probability=0.99,
            firstmjd=START_MJD - 0.1,
            lastmjd=END_MJD - 1.0,
        )
        _insert_detection(conn, oid="ZTF26old", measurement_id="d_old", mjd=END_MJD - 1.0, mag=14.0)

        # Newer than week_end (END_MJD + 0.1) -> excluded from weekly sections
        _insert_object(
            conn,
            oid="ZTF26future",
            top_class="SNIa",
            top_probability=0.99,
            firstmjd=END_MJD + 0.1,
            lastmjd=END_MJD + 0.2,
        )

        # Exactly on boundaries START_MJD and END_MJD -> included in the week, no detections
        _insert_object(
            conn,
            oid="ZTF26at_start",
            top_class="SN",
            top_probability=0.80,
            firstmjd=START_MJD,
            lastmjd=START_MJD + 0.1,
        )
        _insert_object(
            conn,
            oid="ZTF26at_end",
            top_class="SN",
            top_probability=0.85,
            firstmjd=END_MJD,
            lastmjd=END_MJD,
        )

    with psycopg.connect(ro_dsn, autocommit=True) as ro_conn:
        digest = select_digest(ro_conn, WEEK_END)

    assert [h.oid for h in digest.headliners] == ["ZTF26at_end", "ZTF26at_start"]
    assert digest.brightest == ()
    assert digest.stats.new_objects == 2
    assert digest.stats.total_objects == 4
    assert digest.stats.total_detections == 1

    # Render omits Brightest new when there are no detections for the week's objects
    md = render_markdown(digest)
    assert "Brightest new" not in md


def test_cli_prints_markdown_and_html(
    db_urls: tuple[str, str],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    admin_dsn, ro_dsn = db_urls
    with psycopg.connect(admin_dsn, autocommit=True) as conn:
        _insert_object(
            conn,
            oid="ZTF26cli",
            top_class="SNIa",
            top_probability=0.93,
            firstmjd=END_MJD - 1.0,
        )

    monkeypatch.setenv("DATABASE_URL", ro_dsn)

    rc_md = cli_main(["--week-end", "2026-11-01"])
    out_md = capsys.readouterr().out
    assert rc_md == 0
    assert "# Sky Alerts Weekly Digest" in out_md
    assert "https://sky.henseler.app/objects/ztf/ZTF26cli" in out_md

    rc_html = cli_main(["--week-end", "2026-11-01", "--html"])
    out_html = capsys.readouterr().out
    assert rc_html == 0
    assert "<h1>Sky Alerts Weekly Digest</h1>" in out_html
    assert 'href="https://sky.henseler.app/objects/ztf/ZTF26cli"' in out_html
    assert render_html is not None


def test_db_backed_end_to_end_digest_send_and_wsgi(
    db_urls: tuple[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    admin_dsn, ro_dsn = db_urls
    with psycopg.connect(admin_dsn, autocommit=True) as conn:
        _insert_object(
            conn,
            oid="ZTF26e2e_sn",
            top_class="SNIa",
            top_probability=0.96,
            firstmjd=END_MJD - 1.5,
            lastmjd=END_MJD - 0.5,
            ndet=9,
        )
        _insert_detection(
            conn,
            oid="ZTF26e2e_sn",
            measurement_id="det_e2e_1",
            mjd=END_MJD - 0.5,
            mag=15.75,
            band="g",
        )
        _insert_object(
            conn,
            oid="ZTF26e2e_ast",
            top_class="asteroid",
            top_probability=0.99,
            firstmjd=END_MJD - 2.0,
        )

    captured_requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured_requests.append(request)
        return httpx.Response(200, json={"id": "re_e2e_999"})

    transport = httpx.MockTransport(handler)
    cron_secret = "c" * 32
    resend_key = "re_e2e_test_secret_key_000000"

    monkeypatch.setenv("CRON_SECRET", cron_secret)
    monkeypatch.setenv("DATABASE_URL", ro_dsn)
    monkeypatch.setenv("RESEND_API_KEY", resend_key)
    monkeypatch.setenv("DIGEST_TO", "owner@example.com")
    monkeypatch.setattr(web, "_today_utc_midnight", lambda: WEEK_END)
    monkeypatch.setattr(
        web,
        "_http_client",
        lambda: httpx.Client(transport=transport, timeout=10.0),
    )

    resp_meta: dict[str, Any] = {}

    def start_response(status: str, headers: list[tuple[str, str]]) -> None:
        resp_meta["status"] = status
        resp_meta["headers"] = dict(headers)

    raw_body = b"".join(
        web.app(
            {
                "PATH_INFO": "/api/cron/digest",
                "REQUEST_METHOD": "GET",
                "HTTP_AUTHORIZATION": f"Bearer {cron_secret}",
            },
            start_response,
        )
    )
    body = json.loads(raw_body)
    assert resp_meta["status"].startswith("200")
    assert body == {
        "status": "sent",
        "week_end": "2026-11-01",
        "headliners": 1,
        "id": "re_e2e_999",
    }

    assert len(captured_requests) == 1
    req = captured_requests[0]
    assert str(req.url) == RESEND_EMAILS_URL
    assert req.headers["Authorization"] == f"Bearer {resend_key}"
    assert req.headers["Idempotency-Key"] == "digest-2026-11-01"

    payload = json.loads(req.content.decode())
    assert payload["from"] == "Sky Alerts <digest@sky.henseler.app>"
    assert payload["to"] == ["owner@example.com"]
    assert payload["subject"] == "What the sky did this week · Oct 25\u2013Nov 1 (1 new explosions)"
    assert "ZTF26e2e_sn" in payload["html"]
    assert "ZTF26e2e_ast" in payload["html"]
    assert "mag 15.75 (g)" in payload["html"]
    assert "ZTF26e2e_sn" in payload["text"]
    assert "ZTF26e2e_ast" in payload["text"]
    assert "mag 15.75 (g)" in payload["text"]

    # Also verify direct select_digest + send_digest call
    cfg = DigestConfig.from_env()
    with (
        psycopg.connect(ro_dsn, autocommit=True) as ro_conn,
        httpx.Client(transport=transport) as client,
    ):
        digest = select_digest(ro_conn, WEEK_END)
        direct_res = send_digest(digest, cfg, client)
    assert direct_res.id == "re_e2e_999"
    assert len(captured_requests) == 2


def test_db_backed_preview_route_end_to_end(
    db_urls: tuple[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    admin_dsn, ro_dsn = db_urls
    with psycopg.connect(admin_dsn, autocommit=True) as conn:
        _insert_object(
            conn,
            oid="ZTF26prev_sn",
            top_class="SNIa",
            top_probability=0.92,
            firstmjd=END_MJD - 1.2,
            lastmjd=END_MJD - 0.3,
            ndet=8,
        )
        _insert_detection(
            conn,
            oid="ZTF26prev_sn",
            measurement_id="det_prev_1",
            mjd=END_MJD - 0.3,
            mag=16.05,
            band="r",
        )
        _insert_object(
            conn,
            oid="ZTF26prev_ast",
            top_class="asteroid",
            top_probability=0.98,
            firstmjd=END_MJD - 2.0,
        )

    captured_requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured_requests.append(request)
        return httpx.Response(200, json={"id": "should_not_be_called"})

    transport = httpx.MockTransport(handler)
    trigger_secret = "t" * 32

    monkeypatch.setenv("DIGEST_TRIGGER_SECRET", trigger_secret)
    monkeypatch.setenv("DATABASE_URL", ro_dsn)
    monkeypatch.delenv("RESEND_API_KEY", raising=False)
    monkeypatch.delenv("DIGEST_TO", raising=False)
    monkeypatch.setattr(web, "_today_utc_midnight", lambda: WEEK_END)
    monkeypatch.setattr(
        web,
        "_http_client",
        lambda: httpx.Client(transport=transport, timeout=10.0),
    )

    resp_meta: dict[str, Any] = {}

    def start_response(status: str, headers: list[tuple[str, str]]) -> None:
        resp_meta["status"] = status
        resp_meta["headers"] = dict(headers)

    raw_body = b"".join(
        web.app(
            {
                "PATH_INFO": "/api/preview/digest",
                "REQUEST_METHOD": "POST",
                "HTTP_AUTHORIZATION": f"Bearer {trigger_secret}",
            },
            start_response,
        )
    )
    body = json.loads(raw_body)
    assert resp_meta["status"].startswith("200")
    assert set(body.keys()) == {
        "status",
        "week_end",
        "subject",
        "headliners",
        "digest_markdown",
        "podcast_markdown",
    }
    assert body["status"] == "ok"
    assert body["week_end"] == "2026-11-01"
    assert body["subject"] == "What the sky did this week · Oct 25\u2013Nov 1 (1 new explosions)"
    assert body["headliners"] == 1
    assert "# Sky Alerts Weekly Digest" in body["digest_markdown"]
    assert "ZTF26prev_sn" in body["digest_markdown"]
    assert "# What the sky did this week · Oct 25\u2013Nov 1" in body["podcast_markdown"]
    assert "ZTF26prev_sn" in body["podcast_markdown"]
    assert "about 92 percent" in body["podcast_markdown"]
    assert "https://sky.henseler.app/objects/ztf/ZTF26prev_sn" in body["podcast_markdown"]
    assert captured_requests == []
