"""Markdown and HTML rendering for the weekly Sky Alerts digest.

All upstream ALeRCE values (oid, survey, class names, bands) are treated as
untrusted input and escaped before rendering. HTML uses inline-safe simple
markup only: no scripts, no external images.
"""

from __future__ import annotations

import html
from datetime import datetime

from .classes import class_info
from .select import Digest, DigestObject

SITE_BASE_URL = "https://sky.henseler.app"


def object_url(survey: str, oid: str) -> str:
    return f"{SITE_BASE_URL}/objects/{survey}/{oid}"


def _esc_html(value: object) -> str:
    return html.escape(str(value), quote=True)


def _esc_md(value: object) -> str:
    s = "".join(ch if ch.isprintable() else " " for ch in str(value))
    for ch in ("\\", "`", "*", "_", "[", "]", "(", ")", "<", ">", "|"):
        s = s.replace(ch, "\\" + ch)
    return s


def _esc_md_url(url: str) -> str:
    s = "".join(ch if ch.isprintable() and ch != " " else "" for ch in url)
    return (
        s.replace("<", "%3C")
        .replace(">", "%3E")
        .replace("(", "%28")
        .replace(")", "%29")
        .replace('"', "%22")
    )


def _fmt_date(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d")


def _fmt_prob(prob: float | None) -> str | None:
    if prob is None:
        return None
    return f"{round(prob * 100)}%"


def _fmt_mag(mag: float | None, band: str | None) -> str | None:
    if mag is None:
        return None
    if band:
        return f"mag {mag:.2f} ({band})"
    return f"mag {mag:.2f}"


def _fmt_sso_label(sso_name: str | None, sso_number: int | None) -> str | None:
    if not sso_name:
        return None
    trimmed = sso_name.strip()
    if not trimmed:
        return None
    if sso_number is not None and not trimmed.startswith("("):
        return f"({sso_number}) {trimmed}"
    return trimmed


def _md_object_line(
    obj: DigestObject, *, show_mag: bool = False, include_blurb: bool = True
) -> str:
    info = class_info(obj.top_class)
    url = _esc_md_url(object_url(obj.survey, obj.oid))
    oid = _esc_md(obj.oid)
    survey = _esc_md(obj.survey.upper())
    label = _esc_md(info.label)

    details: list[str] = [label]
    if show_mag and obj.peak_mag is not None:
        band_part = f" ({_esc_md(obj.peak_band)})" if obj.peak_band else ""
        details.append(f"mag {obj.peak_mag:.2f}{band_part}")
    prob = _fmt_prob(obj.top_probability)
    if prob is not None:
        details.append(f"{prob} confidence")
    if obj.ndet is not None:
        details.append(f"{obj.ndet} detections")

    line = f"- **[{oid}]({url})** ({survey}) — {', '.join(details)}."
    if include_blurb and info.blurb:
        line += f" {_esc_md(info.blurb)}"
    return line


def render_markdown(d: Digest) -> str:
    window = f"{_fmt_date(d.week_start)} to {_fmt_date(d.week_end)} UTC"
    lines: list[str] = [
        "# Sky Alerts Weekly Digest",
        "",
        f"Week of {window}",
        "",
    ]

    if d.is_empty:
        lines.extend(
            [
                "It was a quiet week in the sky — no new alerts were recorded during this window.",
                "",
            ]
        )
    else:
        if d.headliners:
            lines.extend(["## Headliners", ""])
            seen_hl_classes: set[str | None] = set()
            for obj in d.headliners:
                show_blurb = obj.top_class not in seen_hl_classes
                seen_hl_classes.add(obj.top_class)
                lines.append(_md_object_line(obj, include_blurb=show_blurb))
            lines.append("")

        if d.brightest:
            lines.extend(["## Brightest new", ""])
            seen_br_classes: set[str | None] = set()
            for obj in d.brightest:
                show_blurb = obj.top_class not in seen_br_classes
                seen_br_classes.add(obj.top_class)
                lines.append(_md_object_line(obj, show_mag=True, include_blurb=show_blurb))
            lines.append("")

        lines.extend(["## Solar system", ""])
        if d.solar_system.asteroid_count > 0:
            ast_info = class_info("asteroid")
            noun = "asteroid" if d.solar_system.asteroid_count == 1 else "asteroids"
            lines.append(
                f"**{d.solar_system.asteroid_count}** {noun} recorded this week. "
                f"{_esc_md(ast_info.blurb)}"
            )
            if d.solar_system.examples:
                lines.append("")
                for ex in d.solar_system.examples:
                    url = _esc_md_url(object_url(ex.survey, ex.oid))
                    sso_label = _fmt_sso_label(ex.sso_name, ex.sso_number)
                    if sso_label:
                        sep_part = (
                            f" — matched within {ex.sep_arcsec:.1f}″ by SkyBoT"
                            if ex.sep_arcsec is not None
                            else ""
                        )
                        lines.append(
                            f"- **{_esc_md(sso_label)}** · "
                            f"[{_esc_md(ex.oid)}]({url}) ({_esc_md(ex.survey.upper())}){sep_part}"
                        )
                    else:
                        lines.append(f"- [{_esc_md(ex.oid)}]({url}) ({_esc_md(ex.survey.upper())})")
        else:
            lines.append("No asteroids recorded this week.")
        lines.append("")

    lines.extend(
        [
            "## Week in numbers",
            "",
            f"- **New objects this week:** {d.stats.new_objects}",
        ]
    )
    for grp in d.stats.new_by_group:
        lines.append(f"  - {_esc_md(grp.label)}: {grp.count}")
    lines.extend(
        [
            f"- **Total objects tracked:** {d.stats.total_objects}",
            f"- **Light-curve points stored:** {d.stats.total_detections}",
            "",
        ]
    )
    return "\n".join(lines)


def _html_object_item(
    obj: DigestObject, *, show_mag: bool = False, include_blurb: bool = True
) -> str:
    info = class_info(obj.top_class)
    url = _esc_html(object_url(obj.survey, obj.oid))
    oid = _esc_html(obj.oid)
    survey = _esc_html(obj.survey.upper())
    label = _esc_html(info.label)

    details: list[str] = [label]
    if show_mag and obj.peak_mag is not None:
        mag_str = _fmt_mag(obj.peak_mag, obj.peak_band)
        if mag_str:
            details.append(_esc_html(mag_str))
    prob = _fmt_prob(obj.top_probability)
    if prob is not None:
        details.append(_esc_html(f"{prob} confidence"))
    if obj.ndet is not None:
        details.append(_esc_html(f"{obj.ndet} detections"))

    blurb_html = f" {_esc_html(info.blurb)}" if include_blurb and info.blurb else ""
    return (
        f'<li><a href="{url}"><strong>{oid}</strong></a> ({survey}) — '
        f"{', '.join(details)}.{blurb_html}</li>"
    )


def render_html(d: Digest) -> str:
    window = _esc_html(f"{_fmt_date(d.week_start)} to {_fmt_date(d.week_end)} UTC")
    parts: list[str] = [
        '<div style="font-family: system-ui, -apple-system, sans-serif; '
        'max-width: 640px; margin: 0 auto; line-height: 1.5; color: #111827;">',
        "<h1>Sky Alerts Weekly Digest</h1>",
        f"<p>Week of {window}</p>",
    ]

    if d.is_empty:
        parts.append(
            "<p>It was a quiet week in the sky — no new alerts were recorded "
            "during this window.</p>"
        )
    else:
        if d.headliners:
            parts.append("<h2>Headliners</h2>")
            parts.append("<ul>")
            seen_hl_classes: set[str | None] = set()
            for obj in d.headliners:
                show_blurb = obj.top_class not in seen_hl_classes
                seen_hl_classes.add(obj.top_class)
                parts.append(_html_object_item(obj, include_blurb=show_blurb))
            parts.append("</ul>")

        if d.brightest:
            parts.append("<h2>Brightest new</h2>")
            parts.append("<ul>")
            seen_br_classes: set[str | None] = set()
            for obj in d.brightest:
                show_blurb = obj.top_class not in seen_br_classes
                seen_br_classes.add(obj.top_class)
                parts.append(_html_object_item(obj, show_mag=True, include_blurb=show_blurb))
            parts.append("</ul>")

        parts.append("<h2>Solar system</h2>")
        if d.solar_system.asteroid_count > 0:
            ast_info = class_info("asteroid")
            noun = "asteroid" if d.solar_system.asteroid_count == 1 else "asteroids"
            parts.append(
                f"<p><strong>{int(d.solar_system.asteroid_count)}</strong> {noun} "
                f"recorded this week. {_esc_html(ast_info.blurb)}</p>"
            )
            if d.solar_system.examples:
                parts.append("<ul>")
                for ex in d.solar_system.examples:
                    url = _esc_html(object_url(ex.survey, ex.oid))
                    oid = _esc_html(ex.oid)
                    survey = _esc_html(ex.survey.upper())
                    sso_label = _fmt_sso_label(ex.sso_name, ex.sso_number)
                    if sso_label:
                        sep_part = (
                            f" — matched within {ex.sep_arcsec:.1f}&Prime; by SkyBoT"
                            if ex.sep_arcsec is not None
                            else ""
                        )
                        parts.append(
                            f"<li><strong>{_esc_html(sso_label)}</strong> &middot; "
                            f'<a href="{url}">{oid}</a> ({survey}){sep_part}</li>'
                        )
                    else:
                        parts.append(f'<li><a href="{url}">{oid}</a> ({survey})</li>')
                parts.append("</ul>")
        else:
            parts.append("<p>No asteroids recorded this week.</p>")

    parts.append("<h2>Week in numbers</h2>")
    parts.append("<ul>")
    parts.append(f"<li><strong>New objects this week:</strong> {int(d.stats.new_objects)}<ul>")
    for grp in d.stats.new_by_group:
        parts.append(f"<li>{_esc_html(grp.label)}: {int(grp.count)}</li>")
    parts.append("</ul></li>")
    parts.append(f"<li><strong>Total objects tracked:</strong> {int(d.stats.total_objects)}</li>")
    parts.append(
        f"<li><strong>Light-curve points stored:</strong> {int(d.stats.total_detections)}</li>"
    )
    parts.append("</ul>")
    parts.append("</div>")
    return "\n".join(parts) + "\n"
