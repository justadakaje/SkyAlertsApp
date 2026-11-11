"""Map raw ALeRCE rows to database rows.

Pure functions; all upstream data is treated as untrusted. Rows that fail
validation are rejected (returned as None) rather than half-inserted.
Field names per survey are documented in docs/alerce-notes.md.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

MAX_TEXT = 128

ZTF_BANDS: dict[int, str] = {1: "g", 2: "r", 3: "i"}
LSST_BANDS: dict[str, str] = {"1": "g", "2": "r", "3": "i", "4": "z", "5": "y", "6": "u"}

ZTF_RAW_KEYS: tuple[str, ...] = (
    "candid",
    "fid",
    "isdiffpos",
    "rb",
    "drb",
    "dubious",
    "diffmaglim",
    "magpsf_corr",
    "sigmapsf_corr",
    "corrected",
    "has_stamp",
)
LSST_RAW_KEYS: tuple[str, ...] = (
    "band",
    "psfFlux_flag",
    "isNegative",
    "snr",
    "scienceFlux",
    "scienceFluxErr",
    "has_stamp",
)


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


@dataclass(frozen=True)
class DetectionRow:
    survey: str
    oid: str
    measurement_id: str
    mjd: float
    band: str | None
    mag: float | None
    mag_err: float | None
    flux_njy: float | None
    flux_err_njy: float | None
    raw: dict[str, Any]


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


INT32_MAX = 2**31 - 1
INT16_MAX = 2**15 - 1


def _int(v: Any, hi: int = INT32_MAX) -> int | None:
    if v is None or isinstance(v, bool):
        return None
    try:
        i = int(str(v).strip())  # ZTF ndethist is a string
    except (TypeError, ValueError):
        return None
    return i if 0 <= i <= hi else None


def _text(v: Any) -> str | None:
    if v is None or isinstance(v, bool):
        return None
    s = "".join(ch for ch in str(v) if ch.isprintable() and not "\ud800" <= ch <= "\udfff")
    s = s.strip()
    return s[:MAX_TEXT] or None


def _bool(v: Any) -> bool | None:
    return v if isinstance(v, bool) else None


def _ra(v: Any) -> float | None:
    f = _float(v, 0.0, 360.0)
    if f is None:
        return None
    return 0.0 if f == 360.0 else f


def _clean_raw_val(v: Any) -> Any:
    if v is None or isinstance(v, (bool, int)):
        return v
    if isinstance(v, float):
        return v if math.isfinite(v) else None
    if isinstance(v, str):
        return _text(v)
    return None


def _slim_raw(row: dict[str, Any], keys: tuple[str, ...]) -> dict[str, Any]:
    return {k: _clean_raw_val(row[k]) for k in keys if k in row}


def _lsst_band(row: dict[str, Any]) -> str | None:
    raw_band = row.get("band")
    if raw_band is None or isinstance(raw_band, bool):
        return None
    key = str(raw_band).strip()
    bmap = row.get("band_map")
    if isinstance(bmap, dict) and key in bmap:
        mapped = _text(bmap[key])
        if mapped:
            return mapped
    return LSST_BANDS.get(key) or (key if key in ("u", "g", "r", "i", "z", "y") else None)


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
    ranking = _int(row.get("ranking"), hi=INT16_MAX)
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


def normalize_detection(survey: str, oid: str | int, row: dict[str, Any]) -> DetectionRow | None:
    """Return a normalized DetectionRow, or None if id or mjd is unusable."""
    clean_oid = _text(oid)
    if not clean_oid or len(clean_oid) > 64:
        return None
    mjd = _float(row.get("mjd"), 0.0)
    if mjd is None:
        return None

    if survey == "ztf":
        mid = _text(row.get("candid"))
        if not mid:
            return None
        fid = _int(row.get("fid"))
        band = ZTF_BANDS.get(fid) if fid is not None else None
        raw_mag = _float(row.get("magpsf"))
        mag = raw_mag if raw_mag is not None and 0.0 < raw_mag < 40.0 else None
        mag_err = _float(row.get("sigmapsf"), 0.0) if mag is not None else None
        flux_njy = None
        flux_err_njy = None
        raw = _slim_raw(row, ZTF_RAW_KEYS)
    elif survey == "lsst":
        mid = _text(row.get("measurement_id"))
        if not mid:
            return None
        band = _lsst_band(row)
        flux_njy = _float(row.get("psfFlux"))
        flux_err_njy = _float(row.get("psfFluxErr"))
        if flux_njy is not None and flux_njy > 0.0:
            mag = -2.5 * math.log10(flux_njy) + 31.4
            mag_err = (
                1.0857 * flux_err_njy / flux_njy
                if flux_err_njy is not None and flux_err_njy >= 0.0
                else None
            )
        else:
            mag = None
            mag_err = None
        raw = _slim_raw(row, LSST_RAW_KEYS)
    else:
        raise ValueError(f"unknown survey {survey!r}")

    return DetectionRow(
        survey=survey,
        oid=clean_oid,
        measurement_id=mid,
        mjd=mjd,
        band=band,
        mag=mag,
        mag_err=mag_err,
        flux_njy=flux_njy,
        flux_err_njy=flux_err_njy,
        raw=raw,
    )


def normalize_probability(
    survey: str, oid: str | int, row: dict[str, Any]
) -> ClassificationRow | None:
    """Return a normalized ClassificationRow from a per-object probability row."""
    if survey not in ("ztf", "lsst"):
        raise ValueError(f"unknown survey {survey!r}")
    clean_oid = _text(oid)
    if not clean_oid or len(clean_oid) > 64:
        return None
    classifier = _text(row.get("classifier_name"))
    class_name = _text(row.get("class_name"))
    prob = _float(row.get("probability"), 0.0, 1.0)
    if not classifier or not class_name or prob is None:
        return None
    version = _text(row.get("classifier_version")) or ""
    ranking = _int(row.get("ranking"), hi=INT16_MAX)
    return ClassificationRow(
        survey=survey,
        oid=clean_oid,
        classifier_name=classifier,
        classifier_version=version,
        class_name=class_name,
        probability=prob,
        ranking=ranking if ranking and ranking >= 1 else None,
    )
