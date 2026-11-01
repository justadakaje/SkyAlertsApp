"""Map raw ALeRCE list rows to database rows.

Pure functions; all upstream data is treated as untrusted. Rows that fail
validation are rejected (returned as None) rather than half-inserted.
Field names per survey are documented in docs/alerce-notes.md.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

MAX_TEXT = 128


@dataclass(frozen=True)
class ObjectRow:
    survey: str
    oid: str
    meanra: float | None
    meandec: float | None
    firstmjd: float | None
    lastmjd: float | None
    ndet: int | None
    n_forced: int | None
    stellar: bool | None
    top_class: str | None
    top_classifier: str | None
    top_classifier_version: str | None
    top_probability: float | None
    raw: dict[str, Any]


@dataclass(frozen=True)
class ClassificationRow:
    survey: str
    oid: str
    classifier_name: str
    classifier_version: str
    class_name: str
    probability: float
    ranking: int | None


def _float(v: Any, lo: float | None = None, hi: float | None = None) -> float | None:
    if v is None or isinstance(v, bool):
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(f):
        return None
    if (lo is not None and f < lo) or (hi is not None and f > hi):
        return None
    return f


def _int(v: Any) -> int | None:
    if v is None or isinstance(v, bool):
        return None
    try:
        i = int(str(v).strip())  # ZTF ndethist is a string
    except (TypeError, ValueError):
        return None
    return i if i >= 0 else None


def _text(v: Any) -> str | None:
    if v is None:
        return None
    s = "".join(ch for ch in str(v) if ch.isprintable()).strip()
    return s[:MAX_TEXT] or None


def _bool(v: Any) -> bool | None:
    return v if isinstance(v, bool) else None


def _ra(v: Any) -> float | None:
    f = _float(v, 0.0, 360.0)
    if f is None:
        return None
    return 0.0 if f == 360.0 else f


def normalize_object(
    survey: str, row: dict[str, Any]
) -> tuple[ObjectRow, ClassificationRow | None] | None:
    """Return (object, top classification) or None if the row is unusable."""
    oid = _text(row.get("oid"))
    if not oid or len(oid) > 64:
        return None

    if survey == "ztf":
        class_name = _text(row.get("class"))
        classifier = _text(row.get("classifier"))
        version = ""  # ZTF list rows don't carry the classifier version
        ndet = _int(row.get("ndet"))
        n_forced = None
    elif survey == "lsst":
        class_name = _text(row.get("class_name"))
        classifier = _text(row.get("classifier_name"))
        version = _text(row.get("classifier_version")) or ""
        ndet = _int(row.get("n_det"))
        n_forced = _int(row.get("n_forced"))
    else:
        raise ValueError(f"unknown survey {survey!r}")

    prob = _float(row.get("probability"), 0.0, 1.0)
    ranking = _int(row.get("ranking"))
    has_class = bool(class_name and classifier and prob is not None)

    obj = ObjectRow(
        survey=survey,
        oid=oid,
        meanra=_ra(row.get("meanra")),
        meandec=_float(row.get("meandec"), -90.0, 90.0),
        firstmjd=_float(row.get("firstmjd"), 0.0),
        lastmjd=_float(row.get("lastmjd"), 0.0),
        ndet=ndet,
        n_forced=n_forced,
        stellar=_bool(row.get("stellar")),
        top_class=class_name if has_class else None,
        top_classifier=classifier if has_class else None,
        top_classifier_version=version if has_class else None,
        top_probability=prob if has_class else None,
        raw=row,
    )
    cls = (
        ClassificationRow(
            survey=survey,
            oid=oid,
            classifier_name=classifier,  # type: ignore[arg-type]
            classifier_version=version,
            class_name=class_name,  # type: ignore[arg-type]
            probability=prob,  # type: ignore[arg-type]
            ranking=ranking if ranking and ranking >= 1 else None,
        )
        if has_class
        else None
    )
    return obj, cls
