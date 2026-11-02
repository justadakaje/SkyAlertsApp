"""Unit tests for DigestConfig validation and Resend email delivery."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime

import httpx
import pytest

from skyalerts_digest.config import DEFAULT_DIGEST_FROM, ConfigError, DigestConfig
from skyalerts_digest.select import (
    Digest,
    DigestObject,
    SolarSystemSection,
    datetime_to_mjd,
)
from skyalerts_digest.send import (
    RESEND_EMAILS_URL,
    SendError,
    format_subject,
    idempotency_key,
    send_digest,
)

WEEK_START = datetime(2026, 10, 25, tzinfo=UTC)
WEEK_END = datetime(2026, 11, 1, tzinfo=UTC)
START_MJD = datetime_to_mjd(WEEK_START)
END_MJD = datetime_to_mjd(WEEK_END)

FAKE_API_KEY = "re_test_secret_key_never_log_987654321"
FAKE_DB_URL = "postgresql://ro_user:ro_secret_pw@db.example.test/neondb"


def _make_digest(*, headliner_count: int = 2) -> Digest:
    headliners = tuple(
        DigestObject(
            survey="ztf",
            oid=f"ZTF26hl{i}",
            top_class="SNIa",
            top_probability=0.95,
            firstmjd=START_MJD + 1.0,
            lastmjd=END_MJD - 0.5,
            ndet=6,
        )
        for i in range(headliner_count)
    )
    return Digest(
        week_start=WEEK_START,
        week_end=WEEK_END,
        start_mjd=START_MJD,
        end_mjd=END_MJD,
        headliners=headliners,
        brightest=(),
        solar_system=SolarSystemSection(asteroid_count=0),
    )


def _make_cfg(
    *,
    to: str = "reader@example.com,second@example.test",
    from_addr: str = DEFAULT_DIGEST_FROM,
) -> DigestConfig:
    return DigestConfig.from_env(
        {
            "DATABASE_URL": FAKE_DB_URL,
            "RESEND_API_KEY": FAKE_API_KEY,
            "DIGEST_FROM": from_addr,
            "DIGEST_TO": to,
        }
    )


def test_config_from_env_defaults_and_valid_variants() -> None:
    cfg = DigestConfig.from_env(
        {
            "DATABASE_URL": FAKE_DB_URL,
            "RESEND_API_KEY": FAKE_API_KEY,
            "DIGEST_TO": "one@example.com, two@example.test",
        }
    )
    assert cfg.digest_from == "Sky Alerts <digest@sky.henseler.app>"
    assert cfg.digest_to == ("one@example.com", "two@example.test")
    assert cfg.recipient_domains == ("example.com", "example.test")
    assert FAKE_API_KEY not in repr(cfg)
    assert FAKE_DB_URL not in repr(cfg)
    assert "one@example.com" not in repr(cfg)

    bare_cfg = _make_cfg(from_addr="digest@sky.henseler.app", to="solo@example.com")
    assert bare_cfg.digest_from == "digest@sky.henseler.app"
    assert bare_cfg.digest_to == ("solo@example.com",)


@pytest.mark.parametrize(
    "bad_from",
    [
        "Sky Alerts <digest@example.com>",
        "digest@example.test",
        "digest@sub.sky.henseler.app",
        "digest@not-sky.henseler.app",
        "@sky.henseler.app",
        "Sky Alerts <@sky.henseler.app>",
        "Sky Alerts <digest@sky.henseler.app>\r\nBcc: leak@example.com",
        "",
    ],
)
def test_config_rejects_bad_from_domain_without_echoing_value(bad_from: str) -> None:
    with pytest.raises(ConfigError) as exc_info:
        DigestConfig.from_env(
            {
                "DATABASE_URL": FAKE_DB_URL,
                "RESEND_API_KEY": FAKE_API_KEY,
                "DIGEST_FROM": bad_from,
                "DIGEST_TO": "reader@example.com",
            }
        )
    if bad_from:
        assert bad_from not in str(exc_info.value)


def test_config_rejects_too_many_or_invalid_recipients_without_echoing() -> None:
    six_recipients = ",".join(f"user{i}@example.com" for i in range(6))
    with pytest.raises(ConfigError) as exc_info:
        DigestConfig.from_env(
            {
                "DATABASE_URL": FAKE_DB_URL,
                "RESEND_API_KEY": FAKE_API_KEY,
                "DIGEST_TO": six_recipients,
            }
        )
    assert "user0@example.com" not in str(exc_info.value)

    with pytest.raises(ConfigError) as exc_empty:
        DigestConfig.from_env(
            {
                "DATABASE_URL": FAKE_DB_URL,
                "RESEND_API_KEY": FAKE_API_KEY,
                "DIGEST_TO": "",
            }
        )
    assert FAKE_API_KEY not in str(exc_empty.value)

    bad_addr = "not-an-email-at-example.com"
    with pytest.raises(ConfigError) as exc_bad:
        DigestConfig.from_env(
            {
                "DATABASE_URL": FAKE_DB_URL,
                "RESEND_API_KEY": FAKE_API_KEY,
                "DIGEST_TO": bad_addr,
            }
        )
    assert bad_addr not in str(exc_bad.value)


def test_config_rejects_missing_key_or_database_url() -> None:
    with pytest.raises(ConfigError) as exc_key:
        DigestConfig.from_env(
            {
                "DATABASE_URL": FAKE_DB_URL,
                "DIGEST_TO": "reader@example.com",
            }
        )
    assert FAKE_DB_URL not in str(exc_key.value)

    with pytest.raises(ConfigError) as exc_db:
        DigestConfig.from_env(
            {
                "RESEND_API_KEY": FAKE_API_KEY,
                "DIGEST_TO": "reader@example.com",
            }
        )
    assert FAKE_API_KEY not in str(exc_db.value)


def test_subject_and_idempotency_key_formatting() -> None:
    with_headliners = _make_digest(headliner_count=3)
    assert (
        format_subject(with_headliners)
        == "What the sky did this week · Oct 25\u2013Nov 1 (3 new explosions)"
    )
    assert idempotency_key(with_headliners) == "digest-2026-11-01"

    quiet = _make_digest(headliner_count=0)
    assert format_subject(quiet) == "What the sky did this week · Oct 25\u2013Nov 1"


def test_send_digest_request_shape() -> None:
    digest = _make_digest(headliner_count=2)
    cfg = _make_cfg()
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200, json={"id": "re_msg_123"})

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        res = send_digest(digest, cfg, client)

    assert res.id == "re_msg_123"
    assert res.week_end == "2026-11-01"
    assert res.headliners == 2
    assert len(captured) == 1

    req = captured[0]
    assert str(req.url) == RESEND_EMAILS_URL
    assert req.method == "POST"
    assert req.headers["Authorization"] == f"Bearer {FAKE_API_KEY}"
    assert req.headers["Idempotency-Key"] == "digest-2026-11-01"

    body = json.loads(req.content.decode())
    assert set(body.keys()) == {"from", "to", "subject", "html", "text"}
    assert body["from"] == "Sky Alerts <digest@sky.henseler.app>"
    assert body["to"] == ["reader@example.com", "second@example.test"]
    assert body["subject"] == "What the sky did this week · Oct 25\u2013Nov 1 (2 new explosions)"
    assert "<h1>Sky Alerts Weekly Digest</h1>" in body["html"]
    assert "ZTF26hl0" in body["html"]
    assert "# Sky Alerts Weekly Digest" in body["text"]
    assert "ZTF26hl0" in body["text"]


def test_send_digest_retries_once_on_503_and_honours_retry_after() -> None:
    digest = _make_digest(headliner_count=1)
    cfg = _make_cfg(to="reader@example.com")
    attempts = 0
    slept: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return httpx.Response(503, headers={"Retry-After": "25"}, json={"message": "busy"})
        return httpx.Response(200, json={"id": "re_after_retry"})

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        res = send_digest(digest, cfg, client, sleep=slept.append)

    assert attempts == 2
    assert slept == [10.0]  # capped at 10 s
    assert res.id == "re_after_retry"


def test_send_digest_raises_on_4xx_without_retry() -> None:
    digest = _make_digest(headliner_count=0)
    cfg = _make_cfg(to="reader@example.com")
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return httpx.Response(422, json={"message": "invalid from address"})

    with (
        httpx.Client(transport=httpx.MockTransport(handler)) as client,
        pytest.raises(SendError) as exc_info,
    ):
        send_digest(digest, cfg, client)

    assert attempts == 1
    assert exc_info.value.status == 422


def test_key_and_recipient_addresses_never_appear_in_errors_or_logs(
    caplog: pytest.LogCaptureFixture,
) -> None:
    digest = _make_digest(headliner_count=1)
    recipient = "private.owner@example.com"
    cfg = _make_cfg(to=recipient)

    def failing_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            401,
            text=f"invalid key {FAKE_API_KEY} for {recipient}",
        )

    with (
        caplog.at_level(logging.DEBUG),
        httpx.Client(transport=httpx.MockTransport(failing_handler)) as client,
        pytest.raises(SendError) as exc_info,
    ):
        send_digest(digest, cfg, client)

    assert FAKE_API_KEY not in str(exc_info.value)
    assert recipient not in str(exc_info.value)
    assert FAKE_API_KEY not in caplog.text
    assert recipient not in caplog.text

    for record in caplog.records:
        serialized = json.dumps(record.__dict__, default=str)
        assert FAKE_API_KEY not in serialized
        assert recipient not in serialized

    caplog.clear()

    def ok_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"id": "re_ok_log"})

    with (
        caplog.at_level(logging.INFO, logger="skyalerts.digest.send"),
        httpx.Client(transport=httpx.MockTransport(ok_handler)) as client,
    ):
        send_digest(digest, cfg, client)

    assert FAKE_API_KEY not in caplog.text
    assert recipient not in caplog.text
    sent_records = [r for r in caplog.records if r.msg == "digest email sent"]
    assert len(sent_records) == 1
    assert sent_records[0].recipient_count == 1
    assert sent_records[0].recipient_domain == "example.com"
