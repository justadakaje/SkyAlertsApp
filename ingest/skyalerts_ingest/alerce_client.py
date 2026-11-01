"""Thin, defensive ALeRCE REST client.

Mirrors the endpoint map of the official `alerce` client (2.3.1) but adds what it
lacks: request timeouts, a client-side rate limiter, and retry with exponential
backoff that honours `Retry-After`. See docs/alerce-notes.md.

ZTF uses the legacy API; LSST uses the multisurvey API (which rejects survey=ztf).
"""

from __future__ import annotations

import logging
import os
import random
import time
from collections.abc import Callable, Mapping
from typing import Any, Literal
from urllib.parse import quote

import httpx

from . import __version__

log = logging.getLogger(__name__)

Survey = Literal["ztf", "lsst"]
SURVEYS: tuple[Survey, ...] = ("ztf", "lsst")

DEFAULT_ZTF_URL = "https://api.alerce.online"
DEFAULT_LSST_URL = "https://api-lsst.alerce.online"
USER_AGENT = f"skyalerts/{__version__} (+https://github.com/justadakaje/skyalerts)"

RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504})
MAX_PAGE_SIZE = 100  # self-imposed; ALeRCE publishes no maximum


class AlerceError(Exception):
    """Non-retryable error, or retries exhausted."""

    def __init__(self, message: str, *, status: int | None = None, url: str | None = None):
        super().__init__(message)
        self.status = status
        self.url = url


class AlerceSchemaError(AlerceError):
    """Response did not match the expected shape."""


class AlerceClient:
    def __init__(
        self,
        *,
        ztf_url: str | None = None,
        lsst_url: str | None = None,
        min_interval: float | None = None,
        timeout: float = 30.0,
        max_attempts: int = 5,
        max_backoff: float = 60.0,
        transport: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.ztf_url = (ztf_url or os.getenv("ALERCE_ZTF_URL") or DEFAULT_ZTF_URL).rstrip("/")
        self.lsst_url = (lsst_url or os.getenv("ALERCE_LSST_URL") or DEFAULT_LSST_URL).rstrip("/")
        if min_interval is None:
            min_interval = float(os.getenv("ALERCE_MIN_INTERVAL_S", "1.0"))
        if max_attempts < 1:
            raise ValueError("max_attempts must be >= 1")
        self.min_interval = max(0.0, min_interval)
        self.max_attempts = max_attempts
        self.max_backoff = max_backoff
        self._sleep = sleep
        self._clock = clock
        self._last_request: float | None = None
        self.request_count = 0
        self._http = httpx.Client(
            timeout=httpx.Timeout(timeout),
            headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
            transport=transport,
            follow_redirects=False,
        )

    # -- lifecycle ---------------------------------------------------------
    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> AlerceClient:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # -- transport ---------------------------------------------------------
    def _throttle(self) -> None:
        if self._last_request is not None:
            wait = self.min_interval - (self._clock() - self._last_request)
            if wait > 0:
                self._sleep(wait)
        self._last_request = self._clock()

    def _backoff(self, attempt: int, retry_after: str | None) -> float:
        if retry_after:
            try:
                return min(max(float(retry_after), 0.0), self.max_backoff)
            except ValueError:
                pass  # HTTP-date form: fall through to exponential
        base = min(2.0 ** (attempt - 1), self.max_backoff)
        return min(base + random.uniform(0, base / 2), self.max_backoff)

    def _get_json(self, url: str, params: Mapping[str, Any] | None = None) -> Any:
        clean = {k: v for k, v in (params or {}).items() if v is not None}
        last_err: str = ""
        for attempt in range(1, self.max_attempts + 1):
            self._throttle()
            self.request_count += 1
            started = self._clock()
            try:
                resp = self._http.get(url, params=clean)
            except httpx.TransportError as exc:
                last_err = f"{type(exc).__name__}: {exc}"
                log.warning(
                    "alerce transport error",
                    extra={"url": url, "attempt": attempt, "error": last_err},
                )
                if attempt < self.max_attempts:
                    self._sleep(self._backoff(attempt, None))
                continue

            elapsed_ms = round((self._clock() - started) * 1000)
            log.info(
                "alerce request",
                extra={
                    "url": url,
                    "status": resp.status_code,
                    "attempt": attempt,
                    "elapsed_ms": elapsed_ms,
                },
            )
            if resp.status_code in RETRYABLE_STATUS:
                last_err = f"HTTP {resp.status_code}"
                if attempt < self.max_attempts:
                    self._sleep(self._backoff(attempt, resp.headers.get("Retry-After")))
                continue
            if 300 <= resp.status_code < 400:
                raise AlerceError(
                    f"Unexpected redirect ({resp.status_code}) to {resp.headers.get('Location')!r}",
                    status=resp.status_code,
                    url=url,
                )
            if resp.status_code >= 400:
                raise AlerceError(
                    f"HTTP {resp.status_code} from ALeRCE: {resp.text[:300]!r}",
                    status=resp.status_code,
                    url=url,
                )
            try:
                return resp.json()
            except ValueError as exc:
                raise AlerceSchemaError(f"Non-JSON response from {url}", url=url) from exc

        raise AlerceError(
            f"Gave up after {self.max_attempts} attempts: {last_err}",
            status=None,
            url=url,
        )

    # -- API ---------------------------------------------------------------
    def list_objects(
        self,
        survey: Survey,
        *,
        page_size: int = 25,
        page: int = 1,
        order_by: str | None = "lastmjd",
        order_mode: Literal["ASC", "DESC"] = "DESC",
        classifier: str | None = None,
        class_name: str | None = None,
        probability: float | None = None,
        firstmjd: float | None = None,
        lastmjd: float | None = None,
    ) -> list[dict[str, Any]]:
        if not 1 <= page_size <= MAX_PAGE_SIZE:
            raise ValueError(f"page_size must be 1..{MAX_PAGE_SIZE}")
        params: dict[str, Any] = {
            "page": page,
            "page_size": page_size,
            "order_by": order_by,
            "order_mode": order_mode if order_by else None,
            "classifier": classifier,
            "probability": probability,
            "firstmjd": firstmjd,
            "lastmjd": lastmjd,
        }
        if survey == "ztf":
            params["class"] = class_name  # legacy API name
            url = f"{self.ztf_url}/ztf/v1/objects"
        elif survey == "lsst":
            params["survey"] = "lsst"
            params["class_name"] = class_name
            url = f"{self.lsst_url}/object_api/list_objects"
        else:
            raise ValueError(f"survey must be one of {SURVEYS}")

        data = self._get_json(url, params)
        items = data.get("items") if isinstance(data, dict) else None
        if not isinstance(items, list) or not all(isinstance(i, dict) for i in items):
            raise AlerceSchemaError(f"Expected {{'items': [objects]}} from {url}", url=url)
        return items

    def probabilities(self, survey: Survey, oid: str | int) -> list[dict[str, Any]]:
        if survey == "ztf":
            # OIDs come from upstream data: encode so nothing can alter the path.
            url = f"{self.ztf_url}/ztf/v1/objects/{quote(str(oid), safe='')}/probabilities"
            data = self._get_json(url)
        elif survey == "lsst":
            url = f"{self.lsst_url}/probability_api/probability"
            data = self._get_json(url, {"survey_id": "lsst", "oid": oid})
        else:
            raise ValueError(f"survey must be one of {SURVEYS}")
        if isinstance(data, dict) and isinstance(data.get("items"), list):
            data = data["items"]
        if not isinstance(data, list):
            raise AlerceSchemaError(f"Expected a list of probabilities from {url}", url=url)
        return [d for d in data if isinstance(d, dict)]

    def ztf_classifiers(self) -> list[dict[str, Any]]:
        url = f"{self.ztf_url}/ztf/v1/classifiers"
        data = self._get_json(url)
        if not isinstance(data, list):
            raise AlerceSchemaError(f"Expected a list of classifiers from {url}", url=url)
        return [d for d in data if isinstance(d, dict)]
