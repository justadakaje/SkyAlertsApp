"""Markdown script/outline rendering for the weekly Sky Alerts podcast segment.

All upstream ALeRCE values (oid, survey, class names, bands) are treated as
untrusted input: Markdown control characters and non-printable characters are
stripped so they cannot inject links, headings, or raw HTML.
"""

from __future__ import annotations

from datetime import datetime
from urllib.parse import quote

from .classes import class_info
from .render import SITE_BASE_URL
from .select import Digest, DigestObject, normalize_utc

_MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
_MD_CONTROL_CHARS = frozenset("\\`*[]()<>|#~")


def _clean_text(value: object) -> str:
    raw = "".join(ch if ch.isprintable() else " " for ch in str(value))
    cleaned = "".join(ch for ch in raw if ch not in _MD_CONTROL_CHARS)
    return " ".join(cleaned.split())


def _safe_url_segment(value: object) -> str:
    cleaned = _clean_text(value).replace("/", "")
    return quote(cleaned, safe="")


def _plain_object_url(survey: str, oid: str) -> str:
    return f"{SITE_BASE_URL}/objects/{_safe_url_segment(survey)}/{_safe_url_segment(oid)}"


def _fmt_short_date(dt: datetime) -> str:
    utc_dt = normalize_utc(dt)
    return f"{_MONTHS[utc_dt.month - 1]} {utc_dt.day}"


def _article_for(label: str) -> str:
    first = label[:1].lower()
    if first in ("a", "e", "i", "o", "u"):
        return "an"
    return "a"


def _spoken_confidence(prob: float | None) -> str | None:
    if prob is None:
        return None
    return f"about {round(prob * 100)} percent"


def _cold_open(d: Digest, window: str) -> str:
    if d.headliners:
        top = d.headliners[0]
        info = class_info(top.top_class)
        label = _clean_text(info.label) or "transient"
        oid = _clean_text(top.oid) or "an alert"
        survey = _clean_text(top.survey.upper()) or "SURVEY"
        conf = _spoken_confidence(top.top_probability)
        conf_clause = f" at {conf} confidence" if conf else ""
        blurb_clause = f" {info.blurb}" if info.blurb else ""
        return (
            f"Leading the sky for {window}, {survey} flagged {oid} as "
            f"{_article_for(label)} {label.lower()}{conf_clause}.{blurb_clause}"
        )
    if d.is_empty:
        return (
            f"The sky took a breather from {window} — no new alerts crossed our "
            "filters this week, making it a quiet stretch for the survey cameras."
        )
    return (
        f"From {window}, the survey cameras logged {d.stats.new_objects} new "
        "objects across the night sky with no major new explosions."
    )


def _headliner_sentence(obj: DigestObject, *, include_blurb: bool = True) -> str:
    info = class_info(obj.top_class)
    oid = _clean_text(obj.oid) or "unknown object"
    survey = _clean_text(obj.survey.upper()) or "SURVEY"
    label = _clean_text(info.label) or "unclassified object"
    conf = _spoken_confidence(obj.top_probability)

    parts = [f"{oid} from {survey} is classified as {_article_for(label)} {label}"]
    if conf:
        parts.append(f"with {conf} confidence")
    if obj.ndet is not None:
        det_word = "detection" if obj.ndet == 1 else "detections"
        parts.append(f"across {obj.ndet} {det_word}")
    sentence = f"- {' '.join(parts)}."
    if include_blurb and info.blurb:
        sentence += f" {info.blurb}"
    return sentence


def _brightest_sentence(obj: DigestObject, *, include_blurb: bool = True) -> str:
    info = class_info(obj.top_class)
    oid = _clean_text(obj.oid) or "unknown object"
    survey = _clean_text(obj.survey.upper()) or "SURVEY"
    label = _clean_text(info.label) or "unclassified object"
    conf = _spoken_confidence(obj.top_probability)

    mag_clause = ""
    if obj.peak_mag is not None:
        band = _clean_text(obj.peak_band) if obj.peak_band else ""
        band_part = f" in the {band} band" if band else ""
        mag_clause = f" peaked at magnitude {obj.peak_mag:.2f}{band_part}"
    else:
        mag_clause = " was among the week's notable detections"

    conf_part = f" ({conf} confidence)" if conf else ""
    sentence = f"- {oid} ({survey}), {_article_for(label)} {label}{conf_part},{mag_clause}."
    if include_blurb and info.blurb:
        sentence += f" {info.blurb}"
    return sentence


def _spoken_asteroid_example(ex: DigestObject) -> str:
    oid = _clean_text(ex.oid) or "object"
    survey = _clean_text(ex.survey.upper()) or "SURVEY"
    if ex.sso_name:
        name = _clean_text(ex.sso_name)
        if name:
            if ex.sso_number is not None:
                return f"asteroid {ex.sso_number} {name} ({oid}, {survey})"
            return f"asteroid {name} ({oid}, {survey})"
    return f"{oid} ({survey})"


def _collect_show_notes(d: Digest) -> list[tuple[str, str]]:
    seen: set[tuple[str, str]] = set()
    notes: list[tuple[str, str]] = []
    for group in (d.headliners, d.brightest, d.solar_system.examples):
        for obj in group:
            key = (obj.survey, obj.oid)
            if key in seen:
                continue
            seen.add(key)
            label_oid = _clean_text(obj.oid) or "object"
            label_survey = _clean_text(obj.survey.upper()) or "SURVEY"
            url = _plain_object_url(obj.survey, obj.oid)
            notes.append((f"{label_oid} ({label_survey})", url))
    return notes


def render_podcast(digest: Digest) -> str:
    start = _fmt_short_date(digest.week_start)
    end = _fmt_short_date(digest.week_end)
    window = f"{start}\u2013{end}"

    lines: list[str] = [
        f"# What the sky did this week · {window}",
        "",
        "## Cold open",
        "",
        _cold_open(digest, window),
        "",
        "## Headliners",
        "",
    ]

    if digest.headliners:
        seen_hl_classes: set[str | None] = set()
        for obj in digest.headliners:
            show_blurb = obj.top_class not in seen_hl_classes
            seen_hl_classes.add(obj.top_class)
            lines.append(_headliner_sentence(obj, include_blurb=show_blurb))
    else:
        lines.append(
            "It was a quiet week for major cosmic explosions — no new supernovae, "
            "tidal disruption events, or kilonovae made the headliner list."
        )
    lines.append("")

    lines.extend(["## Brightest new", ""])
    if digest.brightest:
        seen_br_classes: set[str | None] = set()
        for obj in digest.brightest:
            show_blurb = obj.top_class not in seen_br_classes
            seen_br_classes.add(obj.top_class)
            lines.append(_brightest_sentence(obj, include_blurb=show_blurb))
    else:
        lines.append("No new bright transients stood out in the photometry this week.")
    lines.append("")

    lines.extend(["## Solar-system roundup", ""])
    if digest.solar_system.asteroid_count > 0:
        ast_info = class_info("asteroid")
        count = digest.solar_system.asteroid_count
        noun = "asteroid" if count == 1 else "asteroids"
        verb = "was" if count == 1 else "were"
        lines.append(
            f"{count} moving solar-system {noun} {verb} picked up this week. {ast_info.blurb}"
        )
        if digest.solar_system.examples:
            example_names = ", ".join(
                _spoken_asteroid_example(ex) for ex in digest.solar_system.examples
            )
            lines.append(f"Notable tracks include {example_names}.")
    else:
        lines.append("No new asteroids were logged moving across the survey fields this week.")
    lines.append("")

    lines.extend(
        [
            "## By the numbers",
            "",
            f"- New objects this week: {digest.stats.new_objects}",
        ]
    )
    for grp in digest.stats.new_by_group:
        lines.append(f"  - {_clean_text(grp.label)}: {grp.count}")
    lines.extend(
        [
            f"- Total objects tracked: {digest.stats.total_objects}",
            f"- Light-curve points stored: {digest.stats.total_detections}",
            "",
            "## Outro",
            "",
            "That's what the sky did this week. You can explore the light curves, "
            f"coordinates, and classification breakdowns at {SITE_BASE_URL}.",
            "",
            "[Show notes]",
            "",
        ]
    )

    notes = _collect_show_notes(digest)
    if notes:
        for label, url in notes:
            lines.append(f"- {label}: {url}")
    else:
        lines.append(f"- Dashboard: {SITE_BASE_URL}")
    lines.append("")

    return "\n".join(lines)
