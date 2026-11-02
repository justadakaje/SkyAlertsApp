"""Configuration loading and validation for the weekly Sky Alerts digest.

Validation errors never echo secret values or email addresses in their message.
"""

from __future__ import annotations

import os
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

DEFAULT_DIGEST_FROM = "Sky Alerts <digest@sky.henseler.app>"
ALLOWED_FROM_DOMAIN = "sky.henseler.app"
MIN_RECIPIENTS = 1
MAX_RECIPIENTS = 5

_EMAIL_RE = re.compile(r"^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+$")


class ConfigError(ValueError):
    """Raised when digest configuration is missing or invalid."""


def _validate_from_address(raw_from: str) -> str:
    value = raw_from.strip()
    if not value or "\r" in value or "\n" in value or "\x00" in value:
        raise ConfigError("DIGEST_FROM is invalid")

    if value.endswith(f"@{ALLOWED_FROM_DOMAIN}>"):
        if value.count("<") != 1 or value.count(">") != 1:
            raise ConfigError("DIGEST_FROM must be a valid address at sky.henseler.app")
        addr = value[value.index("<") + 1 : -1]
        if not _EMAIL_RE.match(addr):
            raise ConfigError("DIGEST_FROM must be a valid address at sky.henseler.app")
        return value

    if value.endswith(f"@{ALLOWED_FROM_DOMAIN}"):
        if "<" in value or ">" in value or not _EMAIL_RE.match(value):
            raise ConfigError("DIGEST_FROM must be a valid address at sky.henseler.app")
        return value

    raise ConfigError("DIGEST_FROM must end with @sky.henseler.app or @sky.henseler.app>")


def _validate_recipients(raw_to: str | Sequence[str]) -> tuple[str, ...]:
    if isinstance(raw_to, str):
        stripped = raw_to.strip()
        if not stripped:
            raise ConfigError("DIGEST_TO is required")
        parts = [p.strip() for p in stripped.split(",")]
    else:
        parts = [str(p).strip() for p in raw_to]

    if not parts or any(not p for p in parts):
        raise ConfigError("DIGEST_TO must contain 1 to 5 valid email addresses")
    if not (MIN_RECIPIENTS <= len(parts) <= MAX_RECIPIENTS):
        raise ConfigError("DIGEST_TO must contain between 1 and 5 recipient addresses")

    for addr in parts:
        if "\r" in addr or "\n" in addr or "\x00" in addr or not _EMAIL_RE.match(addr):
            raise ConfigError("DIGEST_TO contains an invalid email address")

    return tuple(parts)


@dataclass(frozen=True)
class DigestConfig:
    database_url: str = field(repr=False)
    resend_api_key: str = field(repr=False)
    digest_from: str = DEFAULT_DIGEST_FROM
    digest_to: tuple[str, ...] = field(default=(), repr=False)

    def __post_init__(self) -> None:
        db_url = (self.database_url or "").strip()
        if not db_url:
            raise ConfigError("DATABASE_URL is required")
        object.__setattr__(self, "database_url", db_url)

        api_key = (self.resend_api_key or "").strip()
        if not api_key:
            raise ConfigError("RESEND_API_KEY is required")
        object.__setattr__(self, "resend_api_key", api_key)

        validated_from = _validate_from_address(self.digest_from)
        object.__setattr__(self, "digest_from", validated_from)

        validated_to = _validate_recipients(self.digest_to)
        object.__setattr__(self, "digest_to", validated_to)

    @property
    def recipient_domains(self) -> tuple[str, ...]:
        return tuple(sorted({addr.rsplit("@", 1)[1].lower() for addr in self.digest_to}))

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> DigestConfig:
        source = os.environ if env is None else env
        raw_from = source.get("DIGEST_FROM")
        return cls(
            database_url=source.get("DATABASE_URL", ""),
            resend_api_key=source.get("RESEND_API_KEY", ""),
            digest_from=DEFAULT_DIGEST_FROM if raw_from is None else raw_from,
            digest_to=source.get("DIGEST_TO", ""),
        )
