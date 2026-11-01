from __future__ import annotations

import json

import pytest

from skyalerts_ingest import web

SECRET = "s" * 32


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
    monkeypatch.delenv("DATABASE_URL", raising=False)


def test_unknown_path_404():
    assert call("/")[0].startswith("404")
    assert call("/api/cron/ingest/../admin")[0].startswith("404")


def test_wrong_method_405():
    assert call(method="POST", auth=f"Bearer {SECRET}")[0].startswith("405")


@pytest.mark.parametrize("auth", [None, "", "Bearer wrong", SECRET, f"bearer {SECRET}"])
def test_rejects_bad_auth(auth):
    status, headers, body = call(auth=auth)
    assert status.startswith("401") and body == {"error": "unauthorized"}
    assert headers["Cache-Control"] == "no-store"


def test_short_or_missing_secret_never_authorises(monkeypatch):
    monkeypatch.setenv("CRON_SECRET", "short")
    assert call(auth="Bearer short")[0].startswith("401")
    monkeypatch.delenv("CRON_SECRET")
    assert call(auth="Bearer ")[0].startswith("401")


def test_authorised_but_unconfigured_db_500_without_leaking():
    status, _, body = call(auth=f"Bearer {SECRET}")
    assert status.startswith("500") and body == {"error": "misconfigured"}
