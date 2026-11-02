"""Resend email delivery for the weekly Sky Alerts digest.

Never logs the Resend API key or full recipient addresses (logs recipient count
and domain only).
"""

from __future__ import annotations

import base64
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

import httpx

from .config import DigestConfig
from .podcast import render_podcast
from .render import render_html, render_markdown
from .select import Digest, normalize_utc

log = logging.getLogger("skyalerts.digest.send")

RESEND_EMAILS_URL = "https://api.resend.com/emails"
TIMEOUT_S = 10.0
MAX_RETRY_AFTER_S = 10.0
DEFAULT_RETRY_DELAY_S = 0.05
MAX_ATTEMPTS = 2
RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504})

_MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


class SendError(Exception):
    """Typed error raised when Resend delivery fails."""

    def __init__(self, message: str, *, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status


ResendError = SendError


@dataclass(frozen=True)
class SendResult:
    id: str
    subject: str
    week_end: str
    headliners: int


def _fmt_short_date(dt: datetime) -> str:
    utc_dt = normalize_utc(dt)
    return f"{_MONTHS[utc_dt.month - 1]} {utc_dt.day}"


def format_subject(digest: Digest) -> str:
    start = _fmt_short_date(digest.week_start)
    end = _fmt_short_date(digest.week_end)
    base = f"What the sky did this week · {start}\u2013{end}"
    headliner_count = len(digest.headliners)
    if headliner_count > 0:
        return f"{base} ({headliner_count} new explosions)"
    return base


def idempotency_key(digest: Digest) -> str:
    utc_end = normalize_utc(digest.week_end)
    return f"digest-{utc_end.strftime('%Y-%m-%d')}"


def _parse_retry_after(value: str | None) -> float:
    if value is not None:
        try:
            parsed = float(value.strip())
            return min(max(parsed, 0.0), MAX_RETRY_AFTER_S)
        except ValueError:
            pass
    return DEFAULT_RETRY_DELAY_S


def _is_retryable(status_code: int) -> bool:
    return status_code in RETRYABLE_STATUS or 500 <= status_code < 600


def send_digest(
    digest: Digest,
    cfg: DigestConfig,
    client: httpx.Client | None = None,
    *,
    sleep: Callable[[float], None] = time.sleep,
) -> SendResult:
    if client is None:
        with httpx.Client(timeout=TIMEOUT_S) as owned_client:
            return send_digest(digest, cfg, owned_client, sleep=sleep)

    week_end_str = normalize_utc(digest.week_end).strftime("%Y-%m-%d")
    subject = format_subject(digest)
    idem_key = idempotency_key(digest)
    html_body = render_html(digest)
    text_body = render_markdown(digest)
    podcast_md = render_podcast(digest)
    podcast_b64 = base64.b64encode(podcast_md.encode("utf-8")).decode("ascii")

    headers = {
        "Authorization": f"Bearer {cfg.resend_api_key}",
        "Idempotency-Key": idem_key,
    }
    payload = {
        "from": cfg.digest_from,
        "to": list(cfg.digest_to),
        "subject": subject,
        "html": html_body,
        "text": text_body,
        "attachments": [
            {
                "filename": f"sky-this-week-{week_end_str}.md",
                "content": podcast_b64,
            }
        ],
    }

    domains = cfg.recipient_domains
    recipient_domain = domains[0] if len(domains) == 1 else ",".join(domains)
    recipient_count = len(cfg.digest_to)

    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            resp = client.post(
                RESEND_EMAILS_URL,
                headers=headers,
                json=payload,
                timeout=TIMEOUT_S,
            )
        except httpx.TransportError as exc:
            err_type = type(exc).__name__
            log.warning(
                "resend transport error",
                extra={
                    "attempt": attempt,
                    "error": err_type,
                    "recipient_count": recipient_count,
                    "recipient_domain": recipient_domain,
                },
            )
            if attempt < MAX_ATTEMPTS:
                sleep(DEFAULT_RETRY_DELAY_S)
                continue
            raise SendError(
                f"Resend transport error after {attempt} attempts ({err_type})"
            ) from None

        if _is_retryable(resp.status_code):
            log.warning(
                "resend retryable status",
                extra={
                    "status": resp.status_code,
                    "attempt": attempt,
                    "recipient_count": recipient_count,
                    "recipient_domain": recipient_domain,
                },
            )
            if attempt < MAX_ATTEMPTS:
                delay = _parse_retry_after(resp.headers.get("Retry-After"))
                sleep(delay)
                continue
            raise SendError(
                f"Resend failed with HTTP {resp.status_code} after {attempt} attempts",
                status=resp.status_code,
            )

        if resp.status_code >= 400:
            log.error(
                "resend request rejected",
                extra={
                    "status": resp.status_code,
                    "attempt": attempt,
                    "recipient_count": recipient_count,
                    "recipient_domain": recipient_domain,
                },
            )
            raise SendError(
                f"Resend rejected request with HTTP {resp.status_code}",
                status=resp.status_code,
            )

        try:
            data = resp.json()
        except ValueError as exc:
            raise SendError(
                "Resend returned a non-JSON response",
                status=resp.status_code,
            ) from exc

        email_id = data.get("id") if isinstance(data, dict) else None
        if not isinstance(email_id, str) or not email_id:
            raise SendError(
                "Resend response missing email id",
                status=resp.status_code,
            )

        log.info(
            "digest email sent",
            extra={
                "id": email_id,
                "week_end": week_end_str,
                "headliners": len(digest.headliners),
                "recipient_count": recipient_count,
                "recipient_domain": recipient_domain,
                "attempt": attempt,
            },
        )
        return SendResult(
            id=email_id,
            subject=subject,
            week_end=week_end_str,
            headliners=len(digest.headliners),
        )

    raise SendError("Resend delivery failed")  # pragma: no cover
