"""Vercel entrypoint (WSGI, no framework) for the weekly Sky Alerts digest.

Routes:
- GET  /api/cron/digest    authorised by `Authorization: Bearer $CRON_SECRET`
                           (Vercel Cron sends this header automatically when CRON_SECRET is set).
- POST /api/manual/digest  authorised by `Authorization: Bearer $DIGEST_TRIGGER_SECRET`
                           (separate secret used for manual trigger calls).
- POST /api/preview/digest authorised by `Authorization: Bearer $DIGEST_TRIGGER_SECRET`
                           (selects and renders digest and podcast outline; sends nothing).

Everything else is 404. Responses never echo secrets or recipient addresses.
"""

from __future__ import annotations

import hmac
import json
import logging
import os
from collections.abc import Callable, Iterable
from datetime import UTC, datetime
from typing import Any

import httpx
import psycopg

from . import logutil
from .config import ConfigError, DigestConfig
from .podcast import render_podcast
from .render import render_markdown
from .select import normalize_utc, select_digest
from .send import TIMEOUT_S, format_subject, send_digest

log = logging.getLogger("skyalerts.digest.web")
logutil.configure(os.getenv("LOG_LEVEL", "INFO"))

StartResponse = Callable[[str, list[tuple[str, str]]], Any]
HEADERS = [
    ("Content-Type", "application/json"),
    ("Cache-Control", "no-store"),
    ("X-Content-Type-Options", "nosniff"),
]
ROUTES: dict[str, tuple[str, str, str]] = {
    "/api/cron/digest": ("GET", "CRON_SECRET", "cron"),
    "/api/manual/digest": ("POST", "DIGEST_TRIGGER_SECRET", "manual"),
    "/api/preview/digest": ("POST", "DIGEST_TRIGGER_SECRET", "preview"),
}


def _json(start: StartResponse, status: str, body: dict[str, Any]) -> list[bytes]:
    start(status, HEADERS)
    return [json.dumps(body).encode()]


def authorized(header: str | None, secret: str | None) -> bool:
    if not secret or len(secret) < 16 or not header:
        return False
    return hmac.compare_digest(header.encode(), f"Bearer {secret}".encode())


def _today_utc_midnight() -> datetime:
    now = datetime.now(UTC)
    return now.replace(hour=0, minute=0, second=0, microsecond=0)


def _connect(dsn: str) -> psycopg.Connection[Any]:
    return psycopg.connect(
        dsn,
        autocommit=True,
        connect_timeout=15,
        application_name="skyalerts-digest",
    )


def _http_client() -> httpx.Client:
    return httpx.Client(timeout=TIMEOUT_S)


def _run_digest(start_response: StartResponse, *, trigger: str) -> list[bytes]:
    try:
        week_end = _today_utc_midnight()
        if trigger == "preview":
            db_url = (os.environ.get("DATABASE_URL") or "").strip()
            if not db_url:
                raise ConfigError("DATABASE_URL is required")
            with _connect(db_url) as conn:
                digest = select_digest(conn, week_end)
            week_end_str = normalize_utc(digest.week_end).strftime("%Y-%m-%d")
            return _json(
                start_response,
                "200 OK",
                {
                    "status": "ok",
                    "week_end": week_end_str,
                    "subject": format_subject(digest),
                    "headliners": len(digest.headliners),
                    "digest_markdown": render_markdown(digest),
                    "podcast_markdown": render_podcast(digest),
                },
            )

        cfg = DigestConfig.from_env()
        with _connect(cfg.database_url) as conn:
            digest = select_digest(conn, week_end)
        with _http_client() as client:
            res = send_digest(digest, cfg, client)
    except Exception:
        log.exception("%s digest failed", trigger)
        return _json(start_response, "500 Internal Server Error", {"status": "failed"})

    week_end_str = normalize_utc(digest.week_end).strftime("%Y-%m-%d")
    return _json(
        start_response,
        "200 OK",
        {
            "status": "sent",
            "week_end": week_end_str,
            "headliners": len(digest.headliners),
            "id": res.id,
        },
    )


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

    return _run_digest(start_response, trigger=trigger)
