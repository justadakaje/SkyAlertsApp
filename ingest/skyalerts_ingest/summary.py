"""Pure functions that summarise ALeRCE object samples (fields, classes, freshness).

Kept I/O-free so they're testable against fixtures. All upstream values are
treated as untrusted: anything rendered to Markdown goes through `md_escape`.
"""

from __future__ import annotations

import math
import statistics
from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

MJD_UNIX_EPOCH = 40587.0  # MJD of 1970-01-01T00:00:00Z

# Field-name candidates per concept; first present wins. LSST list fields are
# undocumented (docs/alerce-notes.md), so stay tolerant.
CLASS_KEYS = ("class", "class_name")
CLASSIFIER_KEYS = ("classifier", "classifier_name")
PROB_KEYS = ("probability",)
LASTMJD_KEYS = ("lastmjd", "last_mjd", "lastMjd")
FIRSTMJD_KEYS = ("firstmjd", "first_mjd", "firstMjd")
NDET_KEYS = ("ndet", "n_det")


def mjd_to_datetime(mjd: float) -> datetime:
    return datetime(1970, 1, 1, tzinfo=UTC) + timedelta(days=mjd - MJD_UNIX_EPOCH)


def datetime_to_mjd(dt: datetime) -> float:
    if dt.tzinfo is None:
        raise ValueError("datetime must be timezone-aware")
    return dt.timestamp() / 86400.0 + MJD_UNIX_EPOCH


def _first(obj: dict[str, Any], keys: tuple[str, ...]) -> Any:
    for k in keys:
        if k in obj and obj[k] is not None:
            return obj[k]
    return None


def _num(v: Any) -> float | None:
    if isinstance(v, bool):
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def _type_name(v: Any) -> str:
    if v is None:
        return "null"
    return {bool: "bool", int: "int", float: "float", str: "str", list: "list", dict: "object"}.get(
        type(v), type(v).__name__
    )


def md_escape(value: Any, max_len: int = 80) -> str:
    """Make an untrusted value safe for a Markdown table cell."""
    s = str(value)
    s = "".join(ch if ch.isprintable() else " " for ch in s)
    for ch in ("\\", "|", "`", "*", "_", "[", "]", "<", ">", "#"):
        s = s.replace(ch, "\\" + ch)
    return s if len(s) <= max_len else s[: max_len - 1] + "…"


@dataclass
class FieldStat:
    name: str
    types: Counter[str] = field(default_factory=Counter)
    nulls: int = 0
    example: Any = None


@dataclass
class SurveySummary:
    survey: str
    n_objects: int
    fields: list[FieldStat]
    classes: Counter[str]
    classifiers: Counter[str]
    newest_last_detection: datetime | None
    oldest_last_detection: datetime | None
    median_age_hours: float | None
    newest_age_hours: float | None
    discovered_last_24h: int
    mean_probability: float | None
    probability_classifiers: Counter[str] = field(default_factory=Counter)
    error: str | None = None

    @classmethod
    def failed(cls, survey: str, error: str) -> SurveySummary:
        return cls(
            survey=survey,
            n_objects=0,
            fields=[],
            classes=Counter(),
            classifiers=Counter(),
            newest_last_detection=None,
            oldest_last_detection=None,
            median_age_hours=None,
            newest_age_hours=None,
            discovered_last_24h=0,
            mean_probability=None,
            error=error,
        )


def summarize_objects(
    survey: str,
    objects: list[dict[str, Any]],
    now: datetime,
    probabilities: list[dict[str, Any]] | None = None,
) -> SurveySummary:
    stats: dict[str, FieldStat] = {}
    classes: Counter[str] = Counter()
    classifiers: Counter[str] = Counter()
    last_mjds: list[float] = []
    probs: list[float] = []
    now_mjd = datetime_to_mjd(now)
    discovered_24h = 0

    for obj in objects:
        for k, v in obj.items():
            st = stats.setdefault(k, FieldStat(k))
            st.types[_type_name(v)] += 1
            if v is None:
                st.nulls += 1
            elif st.example is None:
                st.example = v
        cls = _first(obj, CLASS_KEYS)
        classes[str(cls) if cls is not None else "(unclassified)"] += 1
        clf = _first(obj, CLASSIFIER_KEYS)
        if clf is not None:
            classifiers[str(clf)] += 1
        if (p := _num(_first(obj, PROB_KEYS))) is not None:
            probs.append(p)
        if (lm := _num(_first(obj, LASTMJD_KEYS))) is not None:
            last_mjds.append(lm)
        if (fm := _num(_first(obj, FIRSTMJD_KEYS))) is not None and now_mjd - fm <= 1.0:
            discovered_24h += 1

    ages_h = [(now_mjd - m) * 24.0 for m in last_mjds]
    prob_clfs: Counter[str] = Counter()
    for p in probabilities or []:
        name = p.get("classifier_name")
        ver = p.get("classifier_version")
        if name is not None:
            prob_clfs[f"{name} {ver}" if ver else str(name)] += 1

    return SurveySummary(
        survey=survey,
        n_objects=len(objects),
        fields=sorted(stats.values(), key=lambda s: s.name),
        classes=classes,
        classifiers=classifiers,
        newest_last_detection=mjd_to_datetime(max(last_mjds)) if last_mjds else None,
        oldest_last_detection=mjd_to_datetime(min(last_mjds)) if last_mjds else None,
        median_age_hours=round(statistics.median(ages_h), 1) if ages_h else None,
        newest_age_hours=round(min(ages_h), 1) if ages_h else None,
        discovered_last_24h=discovered_24h,
        mean_probability=round(statistics.fmean(probs), 3) if probs else None,
        probability_classifiers=prob_clfs,
    )


def _na(v: Any) -> str:
    return "n/a" if v is None else str(v)


def _fmt_dt(dt: datetime | None) -> str:
    return dt.strftime("%Y-%m-%d %H:%M UTC") if dt else "n/a"


def render_markdown(summaries: list[SurveySummary], now: datetime) -> str:
    out = [f"# ALeRCE exploration — {_fmt_dt(now)}", ""]
    for s in summaries:
        out.append(f"## {s.survey.upper()}")
        out.append("")
        if s.error:
            out += [f"**Error:** {md_escape(s.error, 300)}", ""]
            continue
        out += [
            f"- Objects sampled: **{s.n_objects}** (ordered by last detection, newest first)",
            f"- Newest last detection: {_fmt_dt(s.newest_last_detection)}"
            f" ({_na(s.newest_age_hours)} h ago)",
            f"- Oldest in sample: {_fmt_dt(s.oldest_last_detection)}",
            f"- Median age of last detection: {_na(s.median_age_hours)} h",
            f"- First detected in last 24 h: {s.discovered_last_24h}",
            f"- Mean top-class probability: {_na(s.mean_probability)}",
            "",
            "### Classes",
            "",
            "| Class | Count |",
            "|---|---:|",
        ]
        out += [f"| {md_escape(c)} | {n} |" for c, n in s.classes.most_common()]
        out.append("")
        if s.classifiers:
            out.append(
                "Classifier(s) on list rows: "
                + ", ".join(f"{md_escape(c)} ({n})" for c, n in s.classifiers.most_common())
            )
            out.append("")
        if s.probability_classifiers:
            out.append(
                "Classifiers seen in probability samples: "
                + ", ".join(md_escape(c) for c in sorted(s.probability_classifiers))
            )
            out.append("")
        out += ["### Fields", "", "| Field | Type(s) | Nulls | Example |", "|---|---|---:|---|"]
        for f in s.fields:
            types = "/".join(t for t, _ in f.types.most_common())
            out.append(
                f"| `{md_escape(f.name, 40)}` | {types} | {f.nulls} | "
                f"{md_escape(f.example) if f.example is not None else ''} |"
            )
        out.append("")
    return "\n".join(out)
