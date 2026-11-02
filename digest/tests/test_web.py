"""Tests for the digest WSGI entrypoint (routes, auth, and error handling)."""

from __future__ import annotations

import contextlib
import json
from datetime import UTC, datetime
from typing import Any

import pytest

from skyalerts_digest import web
from skyalerts_digest.podcast import render_podcast
from skyalerts_digest.render import render_markdown
from skyalerts_digest.select import (
    Digest,
    DigestObject,
    SolarSystemSection,
    datetime_to_mjd,
)
from skyalerts_digest.send import SendError, SendResult, format_subject

CRON_SECRET = "c" * 32
TRIGGER_SECRET = "t" * 32
RESEND_KEY = "re_secret_key_for_web_tests_123456"
DB_URL = "postgresql://ro:secret@db.example.test/neondb"


def call(
    path: str = "/api/cron/digest",
    method: str = "GET",
    auth: str | None = None,
) -> tuple[str, dict[str, str], dict[str, Any]]:
    captured: dict[str, Any] = {}

    def start(status: str, headers: list[tuple[str, str]]) -> None:
        captured["status"] = status
        captured["headers"] = dict(headers)

    env: dict[str, Any] = {"PATH_INFO": path, "REQUEST_METHOD": method}
    if auth is not None:
        env["HTTP_AUTHORIZATION"] = auth
    body = b"".join(web.app(env, start))
    return captured["status"], captured["headers"], json.loads(body)


@pytest.fixture(autouse=True)
def env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CRON_SECRET", CRON_SECRET)
    monkeypatch.setenv("DIGEST_TRIGGER_SECRET", TRIGGER_SECRET)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("RESEND_API_KEY", raising=False)
    monkeypatch.delenv("DIGEST_TO", raising=False)
    monkeypatch.delenv("DIGEST_FROM", raising=False)


def test_unknown_path_404() -> None:
    assert call("/")[0].startswith("404")
    assert call("/api/cron/ingest")[0].startswith("404")
    assert call("/api/cron/digest/../admin")[0].startswith("404")


def test_wrong_method_405() -> None:
    assert call(method="POST", auth=f"Bearer {CRON_SECRET}")[0].startswith("405")
    assert call(path="/api/manual/digest", method="GET", auth=f"Bearer {TRIGGER_SECRET}")[
        0
    ].startswith("405")
    assert call(path="/api/preview/digest", method="GET", auth=f"Bearer {TRIGGER_SECRET}")[
        0
    ].startswith("405")
    assert call(path="/api/preview/digest", method="PUT", auth=f"Bearer {TRIGGER_SECRET}")[
        0
    ].startswith("405")


@pytest.mark.parametrize(
    "auth",
    [None, "", "Bearer wrong", CRON_SECRET, f"bearer {CRON_SECRET}"],
)
def test_cron_rejects_bad_auth(auth: str | None) -> None:
    status, headers, body = call(auth=auth)
    assert status.startswith("401") and body == {"error": "unauthorized"}
    assert headers["Cache-Control"] == "no-store"
    assert CRON_SECRET not in json.dumps(body)


@pytest.mark.parametrize(
    "auth",
    [None, "", "Bearer wrong", TRIGGER_SECRET, f"bearer {TRIGGER_SECRET}"],
)
def test_manual_rejects_bad_auth(auth: str | None) -> None:
    status, headers, body = call(path="/api/manual/digest", method="POST", auth=auth)
    assert status.startswith("401") and body == {"error": "unauthorized"}
    assert headers["Cache-Control"] == "no-store"
    assert TRIGGER_SECRET not in json.dumps(body)


@pytest.mark.parametrize(
    "auth",
    [None, "", "Bearer wrong", TRIGGER_SECRET, f"bearer {TRIGGER_SECRET}"],
)
def test_preview_rejects_bad_auth(auth: str | None) -> None:
    status, headers, body = call(path="/api/preview/digest", method="POST", auth=auth)
    assert status.startswith("401") and body == {"error": "unauthorized"}
    assert headers["Cache-Control"] == "no-store"
    assert TRIGGER_SECRET not in json.dumps(body)


def test_secrets_are_not_interchangeable(caplog: pytest.LogCaptureFixture) -> None:
    s1, _, b1 = call(path="/api/manual/digest", method="POST", auth=f"Bearer {CRON_SECRET}")
    s2, _, b2 = call(path="/api/cron/digest", method="GET", auth=f"Bearer {TRIGGER_SECRET}")
    s3, _, b3 = call(path="/api/preview/digest", method="POST", auth=f"Bearer {CRON_SECRET}")
    assert s1.startswith("401") and b1 == {"error": "unauthorized"}
    assert s2.startswith("401") and b2 == {"error": "unauthorized"}
    assert s3.startswith("401") and b3 == {"error": "unauthorized"}
    routes = [r.route for r in caplog.records if hasattr(r, "route")]
    assert routes == ["/api/manual/digest", "/api/cron/digest", "/api/preview/digest"]


def test_short_or_missing_secret_never_authorises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CRON_SECRET", "short")
    assert call(auth="Bearer short")[0].startswith("401")
    monkeypatch.delenv("CRON_SECRET")
    assert call(auth="Bearer ")[0].startswith("401")

    monkeypatch.setenv("DIGEST_TRIGGER_SECRET", "short")
    assert call(path="/api/manual/digest", method="POST", auth="Bearer short")[0].startswith("401")
    monkeypatch.delenv("DIGEST_TRIGGER_SECRET")
    assert call(path="/api/manual/digest", method="POST", auth="Bearer ")[0].startswith("401")


def test_config_or_send_failure_returns_500_without_leaking(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Missing config -> 500 {"status": "failed"}
    status, _, body = call(auth=f"Bearer {CRON_SECRET}")
    assert status.startswith("500")
    assert body == {"status": "failed"}

    # Send failure -> 500 {"status": "failed"}
    monkeypatch.setenv("DATABASE_URL", DB_URL)
    monkeypatch.setenv("RESEND_API_KEY", RESEND_KEY)
    monkeypatch.setenv("DIGEST_TO", "owner@example.com")

    week_end = datetime(2026, 11, 2, tzinfo=UTC)
    week_start = datetime(2026, 10, 26, tzinfo=UTC)
    fake_digest = Digest(
        week_start=week_start,
        week_end=week_end,
        start_mjd=datetime_to_mjd(week_start),
        end_mjd=datetime_to_mjd(week_end),
    )

    monkeypatch.setattr(web, "_connect", lambda dsn: contextlib.nullcontext("fake-conn"))
    monkeypatch.setattr(web, "select_digest", lambda conn, we: fake_digest)
    monkeypatch.setattr(web, "_http_client", lambda: contextlib.nullcontext("fake-http"))

    def failing_send(digest: Any, cfg: Any, client: Any) -> SendResult:
        raise SendError("Resend failed with HTTP 503", status=503)

    monkeypatch.setattr(web, "send_digest", failing_send)

    s2, _, b2 = call(path="/api/manual/digest", method="POST", auth=f"Bearer {TRIGGER_SECRET}")
    assert s2.startswith("500")
    assert b2 == {"status": "failed"}
    assert RESEND_KEY not in json.dumps(b2)


@pytest.mark.parametrize(
    ("path", "method", "secret"),
    [
        ("/api/cron/digest", "GET", CRON_SECRET),
        ("/api/manual/digest", "POST", TRIGGER_SECRET),
    ],
)
def test_routes_succeed_with_monkeypatched_select_and_send(
    monkeypatch: pytest.MonkeyPatch,
    path: str,
    method: str,
    secret: str,
) -> None:
    monkeypatch.setenv("DATABASE_URL", DB_URL)
    monkeypatch.setenv("RESEND_API_KEY", RESEND_KEY)
    monkeypatch.setenv("DIGEST_TO", "owner@example.com")

    fixed_today = datetime(2026, 11, 2, 0, 0, 0, tzinfo=UTC)
    week_start = datetime(2026, 10, 26, 0, 0, 0, tzinfo=UTC)
    headliner = DigestObject(
        survey="ztf",
        oid="ZTF26abc123",
        top_class="SNIa",
        top_probability=0.97,
    )
    fake_digest = Digest(
        week_start=week_start,
        week_end=fixed_today,
        start_mjd=datetime_to_mjd(week_start),
        end_mjd=datetime_to_mjd(fixed_today),
        headliners=(headliner,),
        solar_system=SolarSystemSection(asteroid_count=0),
    )

    calls: dict[str, Any] = {}
    monkeypatch.setattr(web, "_today_utc_midnight", lambda: fixed_today)
    monkeypatch.setattr(web, "_connect", lambda dsn: contextlib.nullcontext("fake-conn"))
    monkeypatch.setattr(web, "_http_client", lambda: contextlib.nullcontext("fake-http"))

    def fake_select(conn: Any, week_end: datetime) -> Digest:
        calls["conn"] = conn
        calls["week_end"] = week_end
        return fake_digest

    def fake_send(digest: Digest, cfg: Any, client: Any) -> SendResult:
        calls["digest"] = digest
        calls["client"] = client
        return SendResult(
            id="re_sent_42",
            subject="What the sky did this week · Oct 26\u2013Nov 2 (1 new explosions)",
            week_end="2026-11-02",
            headliners=1,
        )

    monkeypatch.setattr(web, "select_digest", fake_select)
    monkeypatch.setattr(web, "send_digest", fake_send)

    status, _, body = call(path=path, method=method, auth=f"Bearer {secret}")
    assert status.startswith("200")
    assert body == {
        "status": "sent",
        "week_end": "2026-11-02",
        "headliners": 1,
        "id": "re_sent_42",
    }
    assert calls["conn"] == "fake-conn"
    assert calls["week_end"] == fixed_today
    assert calls["client"] == "fake-http"
    assert secret not in json.dumps(body)
    assert RESEND_KEY not in json.dumps(body)


def test_preview_route_returns_contract_shape_and_never_sends(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DATABASE_URL", DB_URL)
    # Even without RESEND_API_KEY or DIGEST_TO, preview succeeds and never calls Resend.
    fixed_today = datetime(2026, 11, 2, 0, 0, 0, tzinfo=UTC)
    week_start = datetime(2026, 10, 26, 0, 0, 0, tzinfo=UTC)
    headliner = DigestObject(
        survey="ztf",
        oid="ZTF26abc123",
        top_class="SNIa",
        top_probability=0.97,
        ndet=5,
    )
    fake_digest = Digest(
        week_start=week_start,
        week_end=fixed_today,
        start_mjd=datetime_to_mjd(week_start),
        end_mjd=datetime_to_mjd(fixed_today),
        headliners=(headliner,),
        solar_system=SolarSystemSection(asteroid_count=0),
    )

    monkeypatch.setattr(web, "_today_utc_midnight", lambda: fixed_today)
    monkeypatch.setattr(web, "_connect", lambda dsn: contextlib.nullcontext("fake-conn"))
    monkeypatch.setattr(web, "select_digest", lambda conn, we: fake_digest)

    def forbidden_http_client() -> Any:
        raise AssertionError("_http_client must not be called on preview")

    def forbidden_send(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("send_digest must not be called on preview")

    monkeypatch.setattr(web, "_http_client", forbidden_http_client)
    monkeypatch.setattr(web, "send_digest", forbidden_send)

    status, headers, body = call(
        path="/api/preview/digest",
        method="POST",
        auth=f"Bearer {TRIGGER_SECRET}",
    )
    assert status.startswith("200")
    assert headers["Content-Type"] == "application/json"
    assert headers["Cache-Control"] == "no-store"
    assert body == {
        "status": "ok",
        "week_end": "2026-11-02",
        "subject": format_subject(fake_digest),
        "headliners": 1,
        "digest_markdown": render_markdown(fake_digest),
        "podcast_markdown": render_podcast(fake_digest),
    }
    assert set(body.keys()) == {
        "status",
        "week_end",
        "subject",
        "headliners",
        "digest_markdown",
        "podcast_markdown",
    }
    assert TRIGGER_SECRET not in json.dumps(body)
    assert DB_URL not in json.dumps(body)


def test_preview_route_failure_returns_500_without_leaking(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Missing DATABASE_URL -> 500 {"status": "failed"}
    s1, _, b1 = call(path="/api/preview/digest", method="POST", auth=f"Bearer {TRIGGER_SECRET}")
    assert s1.startswith("500")
    assert b1 == {"status": "failed"}

    # DB failure -> 500 {"status": "failed"} without leaking DB_URL
    monkeypatch.setenv("DATABASE_URL", DB_URL)

    def failing_connect(dsn: str) -> Any:
        raise RuntimeError(f"could not connect to {dsn}")

    monkeypatch.setattr(web, "_connect", failing_connect)
    s2, _, b2 = call(path="/api/preview/digest", method="POST", auth=f"Bearer {TRIGGER_SECRET}")
    assert s2.startswith("500")
    assert b2 == {"status": "failed"}
    assert DB_URL not in json.dumps(b2)


def test_shared_headers_are_not_mutated_between_responses():
    # wsgiref appends Content-Length to the list it is given; a shared module-level
    # list would leak the first response's length into later ones and truncate them.
    def start_response(status, headers):
        headers.append(("Content-Length", "1"))

    for _ in range(2):
        list(web.app({"PATH_INFO": "/nope", "REQUEST_METHOD": "GET"}, start_response))
    assert all(name != "Content-Length" for name, _ in web.HEADERS)
