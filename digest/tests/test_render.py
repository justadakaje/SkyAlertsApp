"""Unit tests for classes and digest rendering (Markdown & HTML)."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import UTC, datetime

import pytest

from skyalerts_digest.classes import (
    ARTIFACT_CLASS,
    GROUPS,
    KNOWN,
    LOW_PRIORITY_CLASSES,
    TRANSIENT_CLASSES,
    class_info,
    group_of,
)
from skyalerts_digest.render import render_html, render_markdown
from skyalerts_digest.select import (
    Digest,
    DigestObject,
    GroupCount,
    SolarSystemSection,
    WeekStats,
    datetime_to_mjd,
)

WEEK_START = datetime(2026, 10, 25, tzinfo=UTC)
WEEK_END = datetime(2026, 11, 1, tzinfo=UTC)
START_MJD = datetime_to_mjd(WEEK_START)
END_MJD = datetime_to_mjd(WEEK_END)


def _stats(
    *,
    transient: int = 0,
    stochastic: int = 0,
    variable: int = 0,
    solar: int = 0,
    other: int = 0,
    total_objects: int = 0,
    total_detections: int = 0,
) -> WeekStats:
    counts = {
        "stochastic": stochastic,
        "transient": transient,
        "variable": variable,
        "solar": solar,
        "other": other,
    }
    return WeekStats(
        new_by_group=tuple(
            GroupCount(group=g.id, label=g.label, count=counts[g.id]) for g in GROUPS
        ),
        total_objects=total_objects,
        total_detections=total_detections,
    )


def test_classes_table_matches_web_definitions() -> None:
    assert len(KNOWN) == 30
    assert TRANSIENT_CLASSES == (
        "SN",
        "SNIa",
        "SNIbc",
        "SNII",
        "SLSN",
        "TDE",
        "KN",
        "CV/Nova",
    )
    assert LOW_PRIORITY_CLASSES == ("AGN", "QSO", "Blazar")
    assert ARTIFACT_CLASS == "bogus"

    snia = class_info("SNIa")
    assert snia.label == "Type Ia supernova"
    assert snia.group == "transient"
    assert (
        snia.blurb
        == "A white dwarf blown apart. Their even brightness makes them cosmic yardsticks."
    )

    unknown = class_info("WeirdNewClass")
    assert unknown.label == "WeirdNewClass"
    assert unknown.group == "other"
    assert unknown.blurb == ""

    unclassified = class_info(None)
    assert unclassified.label == "Unclassified"
    assert unclassified.group == "other"
    assert group_of(None) == "other"


def test_dataclasses_are_frozen() -> None:
    obj = DigestObject(survey="ztf", oid="ZTF26abc", top_class="SNIa", top_probability=0.95)
    with pytest.raises(FrozenInstanceError):
        obj.oid = "mutated"  # type: ignore[misc]


def test_render_links_and_blurbs() -> None:
    headliner = DigestObject(
        survey="ztf",
        oid="ZTF26aaaaaaa",
        top_class="SNIa",
        top_probability=0.96,
        firstmjd=61340.0,
        lastmjd=61344.5,
        ndet=8,
    )
    bright = DigestObject(
        survey="lsst",
        oid="313708285401235521",
        top_class="TDE",
        top_probability=0.88,
        firstmjd=61341.0,
        lastmjd=61344.8,
        ndet=12,
        peak_mag=16.42,
        peak_band="r",
    )
    asteroid = DigestObject(
        survey="ztf",
        oid="ZTF26ast0001",
        top_class="asteroid",
        top_probability=0.99,
        firstmjd=61342.0,
        lastmjd=61342.1,
        ndet=2,
    )
    digest = Digest(
        week_start=WEEK_START,
        week_end=WEEK_END,
        start_mjd=START_MJD,
        end_mjd=END_MJD,
        headliners=(headliner,),
        brightest=(bright,),
        solar_system=SolarSystemSection(asteroid_count=4, examples=(asteroid,)),
        stats=_stats(
            transient=2,
            solar=4,
            total_objects=120,
            total_detections=1500,
        ),
    )

    md = render_markdown(digest)
    assert "https://sky.henseler.app/objects/ztf/ZTF26aaaaaaa" in md
    assert "https://sky.henseler.app/objects/lsst/313708285401235521" in md
    assert "https://sky.henseler.app/objects/ztf/ZTF26ast0001" in md
    assert "A white dwarf blown apart." in md
    assert "A star torn apart by a supermassive black hole." in md
    assert "A solar-system body caught moving across the field." in md
    assert "mag 16.42 (r)" in md
    assert "Explosions & outbursts: 2" in md
    assert "Total objects tracked:** 120" in md
    assert "Light-curve points stored:** 1500" in md

    html_out = render_html(digest)
    assert 'href="https://sky.henseler.app/objects/ztf/ZTF26aaaaaaa"' in html_out
    assert 'href="https://sky.henseler.app/objects/lsst/313708285401235521"' in html_out
    assert 'href="https://sky.henseler.app/objects/ztf/ZTF26ast0001"' in html_out
    assert "A white dwarf blown apart." in html_out
    assert "A star torn apart by a supermassive black hole." in html_out
    assert "mag 16.42 (r)" in html_out
    assert "<script" not in html_out.lower()
    assert "<img" not in html_out.lower()


def test_render_html_escapes_untrusted_script_oid_and_class() -> None:
    malicious = DigestObject(
        survey='ztf"><script>alert(1)</script>',
        oid="<script>alert('oid')</script>",
        top_class="<script>alert('cls')</script>",
        top_probability=0.91,
        firstmjd=61340.0,
        lastmjd=61344.0,
        ndet=3,
        peak_mag=15.1,
        peak_band="<img src=x onerror=alert(1)>",
    )
    digest = Digest(
        week_start=WEEK_START,
        week_end=WEEK_END,
        start_mjd=START_MJD,
        end_mjd=END_MJD,
        headliners=(malicious,),
        brightest=(malicious,),
        solar_system=SolarSystemSection(asteroid_count=1, examples=(malicious,)),
        stats=_stats(other=1, total_objects=1, total_detections=3),
    )

    html_out = render_html(digest)
    assert "<script>" not in html_out
    assert "</script>" not in html_out
    assert "<img " not in html_out
    assert "&lt;script&gt;alert(&#x27;oid&#x27;)&lt;/script&gt;" in html_out
    assert "&lt;script&gt;alert(&#x27;cls&#x27;)&lt;/script&gt;" in html_out
    assert "&lt;img src=x onerror=alert(1)&gt;" in html_out

    md_out = render_markdown(digest)
    assert "<script>" not in md_out
    assert "\\<script\\>" in md_out


def test_render_skips_brightest_when_no_detections() -> None:
    headliner = DigestObject(
        survey="ztf",
        oid="ZTF26no_det",
        top_class="SN",
        top_probability=0.85,
        firstmjd=61340.0,
        lastmjd=61341.0,
        ndet=4,
    )
    digest = Digest(
        week_start=WEEK_START,
        week_end=WEEK_END,
        start_mjd=START_MJD,
        end_mjd=END_MJD,
        headliners=(headliner,),
        brightest=(),
        solar_system=SolarSystemSection(asteroid_count=0, examples=()),
        stats=_stats(transient=1, total_objects=10, total_detections=0),
    )

    md = render_markdown(digest)
    html_out = render_html(digest)
    assert "Headliners" in md
    assert "Brightest new" not in md
    assert "Headliners" in html_out
    assert "Brightest new" not in html_out


def test_render_empty_week_shows_quiet_week_message() -> None:
    empty = Digest(
        week_start=WEEK_START,
        week_end=WEEK_END,
        start_mjd=START_MJD,
        end_mjd=END_MJD,
        headliners=(),
        brightest=(),
        solar_system=SolarSystemSection(asteroid_count=0, examples=()),
        stats=_stats(total_objects=42, total_detections=300),
    )
    assert empty.is_empty

    md = render_markdown(empty)
    html_out = render_html(empty)
    assert "quiet week" in md.lower()
    assert "quiet week" in html_out.lower()
    assert "Headliners" not in md
    assert "Brightest new" not in md
    assert "Headliners" not in html_out
    assert "Brightest new" not in html_out
    assert "42" in md and "42" in html_out
