from __future__ import annotations

from datetime import UTC, datetime

import pytest

from skyalerts_ingest.summary import (
    datetime_to_mjd,
    md_escape,
    mjd_to_datetime,
    render_markdown,
    summarize_objects,
)
from tests.conftest import load_fixture

NOW = datetime(2026, 11, 1, tzinfo=UTC)


def test_mjd_roundtrip():
    assert datetime_to_mjd(NOW) == pytest.approx(61345.0)
    assert mjd_to_datetime(40587.0) == datetime(1970, 1, 1, tzinfo=UTC)
    assert mjd_to_datetime(datetime_to_mjd(NOW)) == NOW
    with pytest.raises(ValueError):
        datetime_to_mjd(datetime(2026, 1, 1))  # noqa: DTZ001 — naive on purpose


def test_freshness_and_classes_inline():
    objs = [
        {"oid": "a", "class": "SNIa", "probability": 0.8, "firstmjd": 61344.5, "lastmjd": 61344.9},
        {"oid": "b", "class": "SNIa", "probability": 0.6, "firstmjd": 61300.0, "lastmjd": 61344.0},
        {"oid": "c", "class": None, "probability": None, "firstmjd": None, "lastmjd": None},
    ]
    s = summarize_objects("ztf", objs, NOW)
    assert s.n_objects == 3
    assert s.classes == {"SNIa": 2, "(unclassified)": 1}
    assert s.newest_age_hours == pytest.approx(2.4)
    assert s.median_age_hours == pytest.approx(13.2)
    assert s.discovered_last_24h == 1
    assert s.mean_probability == pytest.approx(0.7)
    by_name = {f.name: f for f in s.fields}
    assert by_name["class"].nulls == 1
    assert by_name["class"].types == {"str": 2, "null": 1}


@pytest.mark.parametrize("survey", ["ztf", "lsst"])
def test_fixture_invariants(survey):
    objs = load_fixture(f"{survey}_objects.json")["items"]
    s = summarize_objects(survey, objs, NOW)
    assert s.n_objects == len(objs)
    assert sum(s.classes.values()) == len(objs)
    assert {f.name for f in s.fields} == {k for o in objs for k in o}
    if s.newest_last_detection:
        assert s.oldest_last_detection <= s.newest_last_detection
    md = render_markdown([s], NOW)
    assert f"## {survey.upper()}" in md and "### Fields" in md


def test_non_numeric_and_bool_values_ignored():
    s = summarize_objects("lsst", [{"lastmjd": "garbage", "probability": True}], NOW)
    assert s.newest_last_detection is None
    assert s.mean_probability is None


def test_md_escape_neutralises_untrusted_values():
    evil = "x|y<script>[link](http://e)\n# h"
    out = md_escape(evil)
    assert "|" not in out.replace("\\|", "")
    assert "<" not in out.replace("\\<", "")
    assert "\n" not in out
    assert len(md_escape("a" * 500)) == 80


def test_render_error_section():
    from skyalerts_ingest.summary import SurveySummary

    md = render_markdown([SurveySummary.failed("lsst", "HTTP 500 | boom")], NOW)
    assert "**Error:** HTTP 500 \\| boom" in md
