"""Vercel entrypoint (WSGI, no framework).

Routes:
- GET  /api/cron/ingest   authorised by `Authorization: Bearer $CRON_SECRET`
                          (Vercel Cron sends this header automatically when CRON_SECRET is set).
- POST /api/manual/ingest authorised by `Authorization: Bearer $MANUAL_TRIGGER_SECRET`
                          (separate secret used by the web /admin manual re-run action).

Everything else is 404. Responses never echo secrets or upstream payloads.
"""

from __future__ import annotations

import hmac
import json
import logging
import os
from collections.abc import Callable, Iterable
from typing import Any

from . import logutil
from .alerce_client import AlerceClient
from .ingest import Config, run
from .store import Store

log = logging.getLogger("skyalerts.web")
logutil.configure(os.getenv("LOG_LEVEL", "INFO"))

StartResponse = Callable[[str, list[tuple[str, str]]], Any]
HEADERS = [
    ("Content-Type", "application/json"),
    ("Cache-Control", "no-store"),
    ("X-Content-Type-Options", "nosniff"),
]
ROUTES: dict[str, tuple[str, str, str]] = {
    "/api/cron/ingest": ("GET", "CRON_SECRET", "cron"),
    "/api/manual/ingest": ("POST", "MANUAL_TRIGGER_SECRET", "manual"),
}


def _json(start: StartResponse, status: str, body: dict[str, Any]) -> list[bytes]:
    # A fresh list per response: servers may append to it (wsgiref adds Content-Length).
    start(status, list(HEADERS))
    return [json.dumps(body).encode()]


def authorized(header: str | None, secret: str | None) -> bool:
    if not secret or len(secret) < 16 or not header:
        return False
    return hmac.compare_digest(header.encode(), f"Bearer {secret}".encode())


def _run_ingest(start_response: StartResponse, *, trigger: str) -> list[bytes]:
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        log.error("DATABASE_URL not configured")
        return _json(start_response, "500 Internal Server Error", {"error": "misconfigured"})

    try:
        store = Store.connect(dsn)
        try:
            with AlerceClient() as client:
                res = run(store, client, trigger=trigger, cfg=Config.from_env())
        finally:
            store.close()
    except Exception:
        log.exception("%s ingest failed", trigger)
        return _json(start_response, "500 Internal Server Error", {"status": "failed"})

    status = (
        "200 OK" if res.status in ("success", "partial", "skipped") else "500 Internal Server Error"
    )
    return _json(start_response, status, res.as_dict())


def app(environ: dict[str, Any], start_response: StartResponse) -> Iterable[bytes]:
    route = environ.get("PATH_INFO", "").rstrip("/")
    method = environ.get("REQUEST_METHOD", "GET")
    spec = ROUTES.get(route)
    if spec is None:
        return _json(start_response, "404 Not Found", {"error": "not found"})
    expected_method, secret_env, trigger = spec
    if method != expected_method:
        return _json(start_response, "405 Method Not Allowed", {"error": "method not allowed"})
    if not authorized(environ.get("HTTP_AUTHORIZATION"), os.environ.get(secret_env)):
        log.warning(
            "unauthorized %s call",
            trigger,
            extra={"route": route, "ua": environ.get("HTTP_USER_AGENT", "")},
        )
        return _json(start_response, "401 Unauthorized", {"error": "unauthorized"})

    return _run_ingest(start_response, trigger=trigger)
