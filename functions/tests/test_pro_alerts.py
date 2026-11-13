"""Tests for Pro clear-sky backyard alert matching and dispatch."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from skyalerts_functions.notifications import NotificationPayload
from skyalerts_functions.pro_alerts import (
    dispatch_pro_backyard_alerts,
    evaluate_backyard_alert_match,
    max_transit_altitude_deg,
)


@dataclass
class _FakeSnap:
    id: str
    _data: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return dict(self._data)


class _FakeCollection:
    def __init__(self, docs: list[_FakeSnap]) -> None:
        self._docs = docs

    def stream(self) -> list[_FakeSnap]:
        return list(self._docs)


class _FakeDb:
    def __init__(self, users: list[_FakeSnap]) -> None:
        self._users = users

    def collection(self, name: str) -> _FakeCollection:
        if name == "users":
            return _FakeCollection(self._users)
        return _FakeCollection([])


def test_max_transit_altitude_deg() -> None:
    assert max_transit_altitude_deg(40.0, 40.0) == 90.0
    assert max_transit_altitude_deg(40.0, 10.0) == 60.0
    assert max_transit_altitude_deg(40.0, -45.0) == 5.0


def test_evaluate_backyard_alert_match_filters() -> None:
    user = {
        "rounded_lat": 40.0,
        "rounded_lon": -75.0,
        "scope_preset": "seestar_s50",
    }
    bright_northern = {"oid": "SN2026abc", "latest_mag": 14.2, "mean_dec": 35.0}
    too_faint = {"oid": "ZTF26faint", "latest_mag": 18.4, "mean_dec": 35.0}
    too_low = {"oid": "SN2026south", "latest_mag": 12.0, "mean_dec": -40.0}

    assert evaluate_backyard_alert_match(user, bright_northern, cloud_cover_pct=15.0) is True
    assert evaluate_backyard_alert_match(user, too_faint, cloud_cover_pct=15.0) is False
    assert evaluate_backyard_alert_match(user, too_low, cloud_cover_pct=15.0) is False
    assert evaluate_backyard_alert_match(user, bright_northern, cloud_cover_pct=75.0) is False
    assert evaluate_backyard_alert_match({}, bright_northern, cloud_cover_pct=10.0) is False


def test_dispatch_pro_backyard_alerts_sends_one_push_per_eligible_user() -> None:
    db = _FakeDb(
        [
            _FakeSnap(
                "u1",
                {
                    "rounded_lat": 40.0,
                    "rounded_lon": -75.0,
                    "scope_preset": "seestar_s50",
                    "fcm_tokens": ["tok-1"],
                },
            ),
            _FakeSnap(
                "u2_cloudy",
                {
                    "rounded_lat": -30.0,
                    "rounded_lon": -70.0,
                    "scope_preset": "seestar_s50",
                    "fcm_tokens": ["tok-2"],
                },
            ),
            _FakeSnap(
                "u3_no_coords",
                {
                    "scope_preset": "seestar_s50",
                    "fcm_tokens": ["tok-3"],
                },
            ),
        ]
    )
    targets = [
        {"oid": "SN2026b", "survey": "bright_sn", "latest_mag": 15.1, "mean_dec": 32.0},
        {"oid": "SN2026a", "survey": "ztf", "latest_mag": 13.8, "mean_dec": 28.0},
    ]
    sent: list[NotificationPayload] = []

    def fake_clouds(lat: float, _lon: float) -> float:
        return 10.0 if lat > 0 else 80.0

    result = dispatch_pro_backyard_alerts(
        db,
        targets,
        send_fn=sent.append,
        cloud_cover_fn=fake_clouds,
    )

    assert len(result) == 1
    assert sent[0].tokens == ("tok-1",)
    assert "SN2026a" in sent[0].title
    assert "(+1 more)" in sent[0].title
    assert sent[0].data["route"] == "/tonight"
