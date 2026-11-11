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
from skyalerts_digest.podcast import render_podcast
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


def test_render_podcast_content_ordering_and_show_notes() -> None:
    headliner1 = DigestObject(
        survey="ztf",
        oid="ZTF26top",
        top_class="SNIa",
        top_probability=0.852,
        firstmjd=61340.0,
        lastmjd=61344.5,
        ndet=7,
    )
    headliner2 = DigestObject(
        survey="lsst",
        oid="313708285401235521",
        top_class="KN",
        top_probability=0.739,
        firstmjd=61341.0,
        lastmjd=61344.2,
        ndet=1,
    )
    bright = DigestObject(
        survey="ztf",
        oid="ZTF26bright",
        top_class="TDE",
        top_probability=0.91,
        firstmjd=61341.0,
        lastmjd=61344.8,
        ndet=12,
        peak_mag=15.40,
        peak_band="r",
    )
    asteroid = DigestObject(
        survey="ztf",
        oid="ZTF26rock",
        top_class="asteroid",
        top_probability=0.99,
        firstmjd=61342.0,
        lastmjd=61342.1,
        ndet=3,
    )
    digest = Digest(
        week_start=WEEK_START,
        week_end=WEEK_END,
        start_mjd=START_MJD,
        end_mjd=END_MJD,
        headliners=(headliner1, headliner2),
        brightest=(bright, headliner1),
        solar_system=SolarSystemSection(asteroid_count=3, examples=(asteroid,)),
        stats=_stats(
            transient=3,
            solar=3,
            total_objects=250,
            total_detections=3400,
        ),
    )

    out = render_podcast(digest)
    assert out.startswith("# What the sky did this week · Oct 25\u2013Nov 1\n")

    # Section ordering
    sections = [
        "## Cold open",
        "## Headliners",
        "## Brightest new",
        "## Solar-system roundup",
        "## By the numbers",
        "## Outro",
        "[Show notes]",
    ]
    indices = [out.index(s) for s in sections]
    assert indices == sorted(indices)

    # Cold open references top headliner & spoken confidence
    assert "ZTF26top" in out.split("## Headliners")[0]
    assert "about 85 percent" in out
    assert "about 74 percent" in out
    assert "about 91 percent" in out

    # Headliner ordering and plain-English blurbs
    hl_section = out.split("## Headliners")[1].split("## Brightest new")[0]
    assert hl_section.index("ZTF26top") < hl_section.index("313708285401235521")
    assert "A white dwarf blown apart." in hl_section
    assert "The glow left behind when two neutron stars merge." in hl_section
    assert "across 7 detections" in hl_section
    assert "across 1 detection." in hl_section

    # Brightest new section
    br_section = out.split("## Brightest new")[1].split("## Solar-system roundup")[0]
    assert "ZTF26bright" in br_section
    assert "magnitude 15.40 in the r band" in br_section
    assert "A star torn apart by a supermassive black hole." in br_section

    # Solar-system roundup
    ss_section = out.split("## Solar-system roundup")[1].split("## By the numbers")[0]
    assert "3 moving solar-system asteroids were picked up this week." in ss_section
    assert "A solar-system body caught moving across the field." in ss_section
    assert "ZTF26rock (ZTF)" in ss_section

    # By the numbers
    num_section = out.split("## By the numbers")[1].split("## Outro")[0]
    assert "New objects this week: 6" in num_section
    assert "Explosions & outbursts: 3" in num_section
    assert "Solar system: 3" in num_section
    assert "Total objects tracked: 250" in num_section
    assert "Light-curve points stored: 3400" in num_section

    # Outro & Show notes plain links (deduplicated)
    outro_and_notes = out.split("## Outro")[1]
    assert "sky.henseler.app" in outro_and_notes
    notes_section = out.split("[Show notes]")[1]
    assert "https://sky.henseler.app/objects/ztf/ZTF26top" in notes_section
    assert "https://sky.henseler.app/objects/lsst/313708285401235521" in notes_section
    assert "https://sky.henseler.app/objects/ztf/ZTF26bright" in notes_section
    assert "https://sky.henseler.app/objects/ztf/ZTF26rock" in notes_section
    assert notes_section.count("https://sky.henseler.app/objects/ztf/ZTF26top") == 1
    assert "<" not in out and ">" not in out


def test_render_podcast_quiet_week() -> None:
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
    out = render_podcast(empty)
    assert out.startswith("# What the sky did this week · Oct 25\u2013Nov 1\n")
    assert "quiet" in out.lower()
    assert "## Cold open" in out
    assert "## Headliners" in out
    assert "## Brightest new" in out
    assert "## Solar-system roundup" in out
    assert "## By the numbers" in out
    assert "## Outro" in out
    assert "[Show notes]" in out
    assert "sky.henseler.app" in out


def test_render_podcast_strips_markdown_injection_and_raw_html() -> None:
    injected_link = DigestObject(
        survey="ztf",
        oid="ZTF26](http://evil.example/pwn)",
        top_class="# Injected Heading\n[click](http://evil.example)",
        top_probability=0.88,
        firstmjd=61340.0,
        lastmjd=61344.0,
        ndet=4,
        peak_mag=16.0,
        peak_band="*bold*_<script>",
    )
    injected_heading = DigestObject(
        survey="lsst",
        oid="# x",
        top_class="<script>alert(1)</script>",
        top_probability=0.75,
        firstmjd=61341.0,
        lastmjd=61343.0,
        ndet=2,
    )
    digest = Digest(
        week_start=WEEK_START,
        week_end=WEEK_END,
        start_mjd=START_MJD,
        end_mjd=END_MJD,
        headliners=(injected_link, injected_heading),
        brightest=(injected_link,),
        solar_system=SolarSystemSection(asteroid_count=1, examples=(injected_heading,)),
        stats=_stats(other=2, total_objects=10, total_detections=20),
    )

    out = render_podcast(digest)
    assert "](http://evil" not in out
    assert "(http://evil" not in out
    assert "<script>" not in out
    assert "</script>" not in out
    assert "<" not in out and ">" not in out

    # No injected headings beyond the expected template headings
    heading_lines = [line for line in out.splitlines() if line.startswith("#")]
    assert heading_lines == [
        "# What the sky did this week · Oct 25\u2013Nov 1",
        "## Cold open",
        "## Headliners",
        "## Brightest new",
        "## Solar-system roundup",
        "## By the numbers",
        "## Outro",
    ]


def test_render_deduplicates_class_blurbs_and_surfaces_skybot_names() -> None:
    sn1 = DigestObject(
        survey="ztf",
        oid="ZTF26sn1",
        top_class="SNIa",
        top_probability=0.97,
        firstmjd=61340.0,
        lastmjd=61344.5,
        ndet=6,
    )
    sn2 = DigestObject(
        survey="lsst",
        oid="313708285401235522",
        top_class="SNIa",
        top_probability=0.94,
        firstmjd=61341.0,
        lastmjd=61344.2,
        ndet=4,
    )
    nolan = DigestObject(
        survey="ztf",
        oid="ZTF26nolan",
        top_class="asteroid",
        top_probability=0.99,
        firstmjd=61342.0,
        lastmjd=61342.1,
        ndet=3,
        sso_name="Nolan",
        sso_number=9537,
        sep_arcsec=3.1,
    )
    digest = Digest(
        week_start=WEEK_START,
        week_end=WEEK_END,
        start_mjd=START_MJD,
        end_mjd=END_MJD,
        headliners=(sn1, sn2),
        brightest=(),
        solar_system=SolarSystemSection(asteroid_count=2, examples=(nolan,)),
        stats=_stats(transient=2, solar=2, total_objects=50, total_detections=400),
    )

    md = render_markdown(digest)
    html_out = render_html(digest)
    pod_out = render_podcast(digest)

    # SNIa blurb appears once in the Headliners section (not repeated on sn2)
    assert md.count("A white dwarf blown apart.") == 1
    assert html_out.count("A white dwarf blown apart.") == 1
    hl_pod = pod_out.split("## Headliners")[1].split("## Brightest new")[0]
    assert hl_pod.count("A white dwarf blown apart.") == 1

    # SkyBoT matched asteroid name is surfaced in Markdown, HTML, and Podcast
    assert "(9537\\) Nolan" in md or "\\(9537\\) Nolan" in md
    assert "matched within 3.1″ by SkyBoT" in md
    assert "(9537) Nolan" in html_out
    assert "matched within 3.1&Prime; by SkyBoT" in html_out
    assert "asteroid 9537 Nolan (ZTF26nolan, ZTF)" in pod_out
