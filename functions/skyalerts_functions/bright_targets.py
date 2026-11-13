"""Bright-transient, comet, NEO close-approach, and evergreen variable catalog ingestion.

Supplements the deep ALeRCE Rubin/ZTF survey stream with targets reachable by
smart telescopes (Seestar, Dwarf, Unistellar) and 4"-8" backyard rigs:
1. Active bright supernovae (Rochester Astronomy / TNS mirror `snactive.html`).
2. Upcoming NEO close approaches (NASA/JPL SBDB Close Approach Data API + Horizons).
3. Observable bright comets (MPC `Soft00Cmt.txt` + JPL Horizons).
4. Evergreen bright variable stars (curated J2000 catalog).
"""

from __future__ import annotations

import logging
import re
from datetime import UTC, datetime
from html.parser import HTMLParser
from typing import Any

import httpx

from skyalerts_functions.firestore_store import datetime_to_mjd
from skyalerts_functions.horizons import horizons_url, parse_horizons

log = logging.getLogger("skyalerts_functions.bright_targets")

SN_ACTIVE_URL = "https://www.rochesterastronomy.org/snimages/snactive.html"
JPL_CAD_URL = "https://ssd-api.jpl.nasa.gov/cad.api"
MPC_COMETS_URL = "https://www.minorplanetcenter.net/iau/Ephemerides/Comets/Soft00Cmt.txt"
USER_AGENT = "skyalerts-bright-targets/1.0 (+https://sky.henseler.app)"

_MAG_NUM_RE = re.compile(r"([+-]?\d+(?:\.\d+)?)")
_DOC_SAFE_RE = re.compile(r"[^A-Za-z0-9._-]+")


def _safe_doc_id(prefix: str, oid: str) -> str:
    cleaned = _DOC_SAFE_RE.sub("_", oid.strip()).strip("_")
    return f"{prefix}_{cleaned}"[:120]


def parse_sexagesimal_ra(ra_str: str) -> float | None:
    """Converts `HH:MM:SS.sss` (or space-separated) to J2000 degrees `[0, 360)`."""
    parts = re.split(r"[:\s]+", ra_str.strip())
    if len(parts) < 2:
        return None
    try:
        hh = float(parts[0])
        mm = float(parts[1])
        ss = float(parts[2]) if len(parts) >= 3 else 0.0
    except ValueError:
        return None
    if not (0.0 <= hh < 24.0 and 0.0 <= mm < 60.0 and 0.0 <= ss < 60.0):
        return None
    deg = (hh + mm / 60.0 + ss / 3600.0) * 15.0
    return round(deg % 360.0, 6)


def parse_sexagesimal_dec(dec_str: str) -> float | None:
    """Converts `±DD:MM:SS.ss` (or space-separated) to J2000 degrees `[-90, 90]`."""
    s = dec_str.strip()
    if not s:
        return None
    sign = -1.0 if s.startswith("-") else 1.0
    s_unsigned = s.lstrip("+-")
    parts = re.split(r"[:\s]+", s_unsigned)
    if len(parts) < 2:
        return None
    try:
        dd = float(parts[0])
        mm = float(parts[1])
        ss = float(parts[2]) if len(parts) >= 3 else 0.0
    except ValueError:
        return None
    if not (0.0 <= dd <= 90.0 and 0.0 <= mm < 60.0 and 0.0 <= ss < 60.0):
        return None
    val = sign * (dd + mm / 60.0 + ss / 3600.0)
    if val < -90.0 or val > 90.0:
        return None
    return round(val, 6)


def _parse_mag(raw: str) -> float | None:
    m = _MAG_NUM_RE.search(raw or "")
    if not m:
        return None
    val = float(m.group(1))
    return val if -3.0 <= val <= 30.0 else None


def _parse_ymd_mjd(raw: str) -> float | None:
    s = (raw or "").strip()[:10]
    for fmt in ("%Y/%m/%d", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(s, fmt).replace(tzinfo=UTC)
            return round(datetime_to_mjd(dt), 5)
        except ValueError:
            continue
    return None


class _TableRowParser(HTMLParser):
    """Extracts `<tr>` cell text lists from HTML tables."""

    def __init__(self) -> None:
        super().__init__()
        self.rows: list[list[str]] = []
        self._in_tr = False
        self._in_td = False
        self._cur_row: list[str] = []
        self._cur_cell: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        del attrs
        if tag == "tr":
            self._in_tr = True
            self._cur_row = []
        elif tag in ("td", "th") and self._in_tr:
            self._in_td = True
            self._cur_cell = []

    def handle_endtag(self, tag: str) -> None:
        if tag in ("td", "th") and self._in_td:
            self._in_td = False
            self._cur_row.append("".join(self._cur_cell).strip())
        elif tag == "tr" and self._in_tr:
            self._in_tr = False
            if self._cur_row:
                self.rows.append(self._cur_row)

    def handle_data(self, data: str) -> None:
        if self._in_td:
            self._cur_cell.append(data)


def _normalize_sn_class(sn_type: str) -> str:
    t = (sn_type or "").strip()
    if not t or t.lower() in ("n/a", "unk", "?"):
        return "Supernova"
    if t.upper().startswith("SN"):
        return t
    if t.upper() in ("EGN", "CV", "NOVA", "LBV"):
        return t.upper()
    return f"SN {t}"


def parse_bright_supernovae_html(
    html: str,
    *,
    max_mag: float = 17.5,
    limit: int = 80,
) -> list[dict[str, Any]]:
    """Parses `snactive.html` rows into normalized `objects/` payloads."""
    parser = _TableRowParser()
    parser.feed(html)
    out: list[dict[str, Any]] = []
    for cells in parser.rows:
        if len(cells) < 12:
            continue
        name = cells[0].strip()
        if not name or name.lower() in ("name", "supernova", "object"):
            continue
        ra = parse_sexagesimal_ra(cells[2])
        dec = parse_sexagesimal_dec(cells[3])
        if ra is None or dec is None:
            continue
        latest_mag = _parse_mag(cells[5])
        peak_mag = _parse_mag(cells[9])
        eff_mag = latest_mag if latest_mag is not None else peak_mag
        if eff_mag is None or eff_mag > max_mag:
            continue

        last_mjd = _parse_ymd_mjd(cells[6])
        first_mjd = _parse_ymd_mjd(cells[11]) or _parse_ymd_mjd(cells[10]) or last_mjd
        if last_mjd is None:
            last_mjd = first_mjd

        host = cells[1].strip() or None
        sn_type = cells[7].strip()
        discoverer = cells[12].strip() if len(cells) > 12 else ""
        aliases_raw = cells[13].strip() if len(cells) > 13 else ""
        aliases = [a.strip() for a in aliases_raw.split(",") if a.strip()]

        out.append(
            {
                "doc_id": _safe_doc_id("tns", name),
                "survey": "tns",
                "oid": name,
                "tier": "bright",
                "is_artifact": False,
                "meanra": ra,
                "meandec": dec,
                "firstmjd": first_mjd,
                "lastmjd": last_mjd,
                "top_class": _normalize_sn_class(sn_type),
                "top_classifier": "TNS/Rochester",
                "top_probability": 1.0,
                "latest_mag": latest_mag,
                "latest_mag_band": "V",
                "peak_mag": peak_mag if peak_mag is not None else latest_mag,
                "peak_band": "V",
                "host_galaxy": host,
                "discoverer": discoverer or None,
                "aliases": aliases,
            }
        )
        if len(out) >= limit:
            break
    return out


def fetch_bright_supernovae(
    client: httpx.Client,
    *,
    max_mag: float = 17.5,
    limit: int = 80,
) -> list[dict[str, Any]]:
    resp = client.get(SN_ACTIVE_URL)
    resp.raise_for_status()
    return parse_bright_supernovae_html(resp.text, max_mag=max_mag, limit=limit)


def parse_cad_response(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Extracts close-approach NEO entries from NASA/JPL SBDB `cad.api` JSON."""
    fields = payload.get("fields") or []
    rows = payload.get("data") or []
    if not isinstance(fields, list) or not isinstance(rows, list):
        return []
    idx = {str(name): i for i, name in enumerate(fields)}
    need = ("des", "cd", "dist", "h")
    if not all(k in idx for k in need):
        return []
    out: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, list) or len(row) <= max(idx[k] for k in need):
            continue
        des = str(row[idx["des"]]).strip()
        cd = str(row[idx["cd"]]).strip()
        try:
            dist_au = float(row[idx["dist"]])
            h_mag = float(row[idx["h"]]) if row[idx["h"]] is not None else None
        except (TypeError, ValueError):
            continue
        if not des:
            continue
        out.append(
            {
                "des": des,
                "close_approach_date": cd,
                "close_approach_au": round(dist_au, 5),
                "h_mag": h_mag,
            }
        )
    return out


def fetch_neo_close_approaches(
    client: httpx.Client,
    *,
    now: datetime | None = None,
    limit: int = 3,
) -> list[dict[str, Any]]:
    """Fetches upcoming close NEOs from JPL CAD and resolves today's sky position via Horizons."""
    ref = (now or datetime.now(UTC)).astimezone(UTC)
    day_iso = ref.strftime("%Y-%m-%d")
    now_mjd = round(datetime_to_mjd(ref), 5)

    resp = client.get(
        JPL_CAD_URL,
        params={"dist-max": "0.05", "h-max": "23.5", "limit": str(limit), "sort": "dist"},
    )
    resp.raise_for_status()
    entries = parse_cad_response(resp.json())

    out: list[dict[str, Any]] = []
    for entry in entries[:limit]:
        des = entry["des"]
        try:
            h_resp = client.get(horizons_url(f"DES={des};", day_iso))
            h_resp.raise_for_status()
            ephem = parse_horizons(str(h_resp.json().get("result") or ""))
        except Exception as exc:
            log.debug("Horizons NEO lookup failed for %s: %s", des, exc)
            continue
        if ephem is None:
            continue
        v_mag = ephem.get("v_mag")
        out.append(
            {
                "doc_id": _safe_doc_id("neo", des),
                "survey": "neo",
                "oid": des,
                "tier": "bright",
                "is_artifact": False,
                "meanra": ephem["ra"],
                "meandec": ephem["dec"],
                "firstmjd": now_mjd,
                "lastmjd": now_mjd,
                "top_class": "NEO Close Approach",
                "top_classifier": "NASA/JPL CAD",
                "top_probability": 1.0,
                "latest_mag": v_mag,
                "latest_mag_band": "V",
                "peak_mag": v_mag,
                "peak_band": "V",
                "close_approach_date": entry["close_approach_date"],
                "close_approach_au": entry["close_approach_au"],
            }
        )
    return out


def parse_mpc_comets(
    text: str,
    *,
    now: datetime | None = None,
    max_h_mag: float = 13.5,
    max_perihelion_days: int = 365,
) -> list[dict[str, Any]]:
    """Filters MPC `Soft00Cmt.txt` lines for bright comets near perihelion."""
    ref = (now or datetime.now(UTC)).astimezone(UTC)
    out: list[dict[str, Any]] = []
    for line in text.splitlines():
        parts = line.split()
        if len(parts) < 13:
            continue
        try:
            yr = int(parts[1])
            mo = int(parts[2])
            day_f = float(parts[3])
            h_mag = float(parts[10])
        except ValueError:
            continue
        m_name = re.search(
            r"\b\d{8}\s+[+-]?\d+(?:\.\d+)?\s+[+-]?\d+(?:\.\d+)?\s+(.+?)(?:\s{2,}.*)?$",
            line,
        )
        name = m_name.group(1).strip() if m_name else " ".join(parts[12:-1]).strip()
        if not name or h_mag > max_h_mag:
            continue
        try:
            peri_dt = datetime(yr, mo, max(1, min(28, int(day_f))), tzinfo=UTC)
        except ValueError:
            continue
        if abs((peri_dt - ref).days) > max_perihelion_days:
            continue
        # Extract designation prefix like `C/2025 A1` or `12P` before parenthesis.
        des = name.split("(")[0].strip()
        out.append(
            {
                "designation": des,
                "name": name,
                "h_mag": h_mag,
                "peri_days": abs((peri_dt - ref).days),
            }
        )
    out.sort(key=lambda c: (c["h_mag"], c["peri_days"]))
    return out


def fetch_bright_comets(
    client: httpx.Client,
    *,
    now: datetime | None = None,
    max_v_mag: float = 15.5,
    limit: int = 4,
) -> list[dict[str, Any]]:
    """Fetches MPC comets near perihelion and resolves live magnitude/coords via Horizons."""
    ref = (now or datetime.now(UTC)).astimezone(UTC)
    day_iso = ref.strftime("%Y-%m-%d")
    now_mjd = round(datetime_to_mjd(ref), 5)

    resp = client.get(MPC_COMETS_URL)
    resp.raise_for_status()
    candidates = parse_mpc_comets(resp.text, now=ref)[:6]

    out: list[dict[str, Any]] = []
    for cand in candidates:
        des = cand["designation"]
        try:
            h_resp = client.get(horizons_url(f"DES={des};", day_iso))
            h_resp.raise_for_status()
            ephem = parse_horizons(str(h_resp.json().get("result") or ""))
        except Exception as exc:
            log.debug("Horizons comet lookup failed for %s: %s", des, exc)
            continue
        if ephem is None:
            continue
        v_mag = ephem.get("v_mag")
        if v_mag is None or v_mag > max_v_mag:
            continue
        out.append(
            {
                "doc_id": _safe_doc_id("comet", des),
                "survey": "comet",
                "oid": cand["name"],
                "tier": "bright",
                "is_artifact": False,
                "meanra": ephem["ra"],
                "meandec": ephem["dec"],
                "firstmjd": now_mjd,
                "lastmjd": now_mjd,
                "top_class": "Comet",
                "top_classifier": "MPC/Horizons",
                "top_probability": 1.0,
                "latest_mag": v_mag,
                "latest_mag_band": "V",
                "peak_mag": v_mag,
                "peak_band": "V",
            }
        )
        if len(out) >= limit:
            break
    return out


_CURATED_VARIABLES: tuple[tuple[str, float, float, float, str], ...] = (
    ("Mira (omi Cet)", 34.8366, -2.9776, 3.0, "Mira Variable"),
    ("Algol (bet Per)", 47.0422, 40.9556, 2.1, "Eclipsing Binary"),
    ("Betelgeuse (alp Ori)", 88.7929, 7.4071, 0.5, "Semiregular Variable"),
    ("Eta Carinae", 161.2648, -59.6844, 4.3, "Luminous Blue Variable"),
    ("R Leonis", 146.8895, 11.4288, 5.8, "Mira Variable"),
    ("R Coronae Borealis", 237.1319, 28.1567, 5.9, "RCB Variable"),
    ("T Coronae Borealis", 239.8757, 25.9202, 10.0, "Recurrent Nova"),
    ("Beta Lyrae (Sheliak)", 282.5200, 33.3627, 3.4, "Eclipsing Binary"),
    ("Chi Cygni", 297.6413, 32.9141, 5.2, "Mira Variable"),
    ("SS Cygni", 325.6783, 43.5861, 8.2, "Dwarf Nova"),
    ("Mu Cephei (Garnet Star)", 325.8769, 58.7800, 4.1, "Semiregular Variable"),
    ("Delta Cephei", 337.2928, 58.4152, 3.7, "Classical Cepheid"),
)


def evergreen_variable_targets(*, now: datetime | None = None) -> list[dict[str, Any]]:
    """Returns curated iconic bright variable stars guaranteed reachable every night."""
    ref = (now or datetime.now(UTC)).astimezone(UTC)
    now_mjd = round(datetime_to_mjd(ref), 5)
    out: list[dict[str, Any]] = []
    for name, ra, dec, mag, var_class in _CURATED_VARIABLES:
        out.append(
            {
                "doc_id": _safe_doc_id("var", name),
                "survey": "variable",
                "oid": name,
                "tier": "bright",
                "is_artifact": False,
                "meanra": ra,
                "meandec": dec,
                "firstmjd": now_mjd,
                "lastmjd": now_mjd,
                "top_class": var_class,
                "top_classifier": "Curated Evergreen",
                "top_probability": 1.0,
                "latest_mag": mag,
                "latest_mag_band": "V",
                "peak_mag": mag,
                "peak_band": "V",
            }
        )
    return out


def collect_bright_targets(
    *,
    client: httpx.Client | None = None,
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    """Collects bright supernovae, NEOs, comets, and evergreen variables fault-tolerantly."""
    own_client = client is None
    http = client or httpx.Client(
        timeout=httpx.Timeout(6.0),
        headers={"User-Agent": USER_AGENT},
        follow_redirects=True,
    )
    results: list[dict[str, Any]] = []
    try:
        for label, fn in (
            ("bright_supernovae", lambda: fetch_bright_supernovae(http)),
            ("neo_close_approaches", lambda: fetch_neo_close_approaches(http, now=now)),
            ("bright_comets", lambda: fetch_bright_comets(http, now=now)),
        ):
            try:
                items = fn()
                results.extend(items)
                log.info("Collected %d %s targets", len(items), label)
            except Exception as exc:
                log.warning("Skipping %s due to fetch error: %s", label, exc)
        results.extend(evergreen_variable_targets(now=now))
        return results
    finally:
        if own_client:
            http.close()
