from __future__ import annotations

import contextlib
import json

import pytest

from skyalerts_ingest import web
from skyalerts_ingest.ingest import RunResult

SECRET = "s" * 32
MANUAL_SECRET = "m" * 32


def call(path="/api/cron/ingest", method="GET", auth=None):
    captured = {}

    def start(status, headers):
        captured["status"] = status
        captured["headers"] = dict(headers)

    env = {"PATH_INFO": path, "REQUEST_METHOD": method}
    if auth is not None:
        env["HTTP_AUTHORIZATION"] = auth
    body = b"".join(web.app(env, start))
    return captured["status"], captured["headers"], json.loads(body)


@pytest.fixture(autouse=True)
def env(monkeypatch):
    monkeypatch.setenv("CRON_SECRET", SECRET)
    monkeypatch.setenv("MANUAL_TRIGGER_SECRET", MANUAL_SECRET)
    monkeypatch.delenv("DATABASE_URL", raising=False)


def test_unknown_path_404():
    assert call("/")[0].startswith("404")
    assert call("/api/cron/ingest/../admin")[0].startswith("404")


def test_wrong_method_405():
    assert call(method="POST", auth=f"Bearer {SECRET}")[0].startswith("405")
    assert call(path="/api/manual/ingest", method="GET", auth=f"Bearer {MANUAL_SECRET}")[
        0
    ].startswith("405")


@pytest.mark.parametrize("auth", [None, "", "Bearer wrong", SECRET, f"bearer {SECRET}"])
def test_rejects_bad_auth(auth):
    status, headers, body = call(auth=auth)
    assert status.startswith("401") and body == {"error": "unauthorized"}
    assert headers["Cache-Control"] == "no-store"


@pytest.mark.parametrize(
    "auth", [None, "", "Bearer wrong", MANUAL_SECRET, f"bearer {MANUAL_SECRET}"]
)
def test_manual_rejects_bad_auth(auth):
    status, headers, body = call(path="/api/manual/ingest", method="POST", auth=auth)
    assert status.startswith("401") and body == {"error": "unauthorized"}
    assert headers["Cache-Control"] == "no-store"
    assert MANUAL_SECRET not in json.dumps(body)


def test_secrets_are_not_interchangeable(caplog):
    s1, _, b1 = call(path="/api/manual/ingest", method="POST", auth=f"Bearer {SECRET}")
    s2, _, b2 = call(path="/api/cron/ingest", method="GET", auth=f"Bearer {MANUAL_SECRET}")
    assert s1.startswith("401") and b1 == {"error": "unauthorized"}
    assert s2.startswith("401") and b2 == {"error": "unauthorized"}
    routes = [r.route for r in caplog.records if hasattr(r, "route")]
    assert routes == ["/api/manual/ingest", "/api/cron/ingest"]


def test_short_or_missing_secret_never_authorises(monkeypatch):
    monkeypatch.setenv("CRON_SECRET", "short")
    assert call(auth="Bearer short")[0].startswith("401")
    monkeypatch.delenv("CRON_SECRET")
    assert call(auth="Bearer ")[0].startswith("401")

    monkeypatch.setenv("MANUAL_TRIGGER_SECRET", "short")
    assert call(path="/api/manual/ingest", method="POST", auth="Bearer short")[0].startswith("401")
    monkeypatch.delenv("MANUAL_TRIGGER_SECRET")
    assert call(path="/api/manual/ingest", method="POST", auth="Bearer ")[0].startswith("401")


def test_authorised_but_unconfigured_db_500_without_leaking():
    status, _, body = call(auth=f"Bearer {SECRET}")
    assert status.startswith("500") and body == {"error": "misconfigured"}


@pytest.mark.parametrize(
    ("run_status", "http_prefix"),
    [("success", "200"), ("partial", "200"), ("skipped", "200"), ("failed", "500")],
)
def test_manual_trigger_runs_with_manual_trigger_and_maps_status(
    monkeypatch, run_status, http_prefix
):
    monkeypatch.setenv("DATABASE_URL", "postgresql://fake/db")
    calls = {}

    class FakeStore:
        def close(self):
            calls["closed"] = True

    monkeypatch.setattr(web.Store, "connect", staticmethod(lambda dsn: FakeStore()))
    monkeypatch.setattr(web, "AlerceClient", lambda: contextlib.nullcontext("fake-client"))

    def fake_run(store, client, *, trigger, cfg):
        calls["trigger"] = trigger
        calls["client"] = client
        return RunResult(run_id=7, status=run_status, objects_upserted=3)

    monkeypatch.setattr(web, "run", fake_run)

    status, _, body = call(path="/api/manual/ingest", method="POST", auth=f"Bearer {MANUAL_SECRET}")
    assert status.startswith(http_prefix)
    assert calls == {"trigger": "manual", "client": "fake-client", "closed": True}
    assert body["status"] == run_status and body["run_id"] == 7
    assert MANUAL_SECRET not in json.dumps(body) and SECRET not in json.dumps(body)
