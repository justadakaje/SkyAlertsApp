from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx
import pytest

from skyalerts_ingest.alerce_client import AlerceClient

FIXTURES = Path(__file__).parent / "fixtures"


def load_fixture(name: str) -> Any:
    return json.loads((FIXTURES / name).read_text())


class FakeTime:
    """Deterministic clock + sleep: sleeping advances the clock."""

    def __init__(self) -> None:
        self.now = 1000.0
        self.sleeps: list[float] = []

    def clock(self) -> float:
        return self.now

    def sleep(self, s: float) -> None:
        self.sleeps.append(s)
        self.now += s


@pytest.fixture
def fake_time() -> FakeTime:
    return FakeTime()


@pytest.fixture
def make_client(fake_time: FakeTime) -> Callable[..., tuple[AlerceClient, list[httpx.Request]]]:
    def _make(
        handler: Callable[[httpx.Request], httpx.Response], **kw: Any
    ) -> tuple[AlerceClient, list[httpx.Request]]:
        seen: list[httpx.Request] = []

        def wrapped(req: httpx.Request) -> httpx.Response:
            seen.append(req)
            return handler(req)

        kw.setdefault("min_interval", 0.0)
        client = AlerceClient(
            transport=httpx.MockTransport(wrapped),
            sleep=fake_time.sleep,
            clock=fake_time.clock,
            ztf_url="https://ztf.test",
            lsst_url="https://lsst.test",
            **kw,
        )
        return client, seen

    return _make
