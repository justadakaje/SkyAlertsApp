"""JPL Horizons nightly ephemeris fetcher for the outer Solar System roster.

Stores nightly positions for Pluto + 8 dwarf planets/candidates in
`rollups/overview.solar_ephemerides` so the Flutter iOS, Android, and Web apps
read ephemerides in the single `rollups/overview` Firestore read without CORS issues.
"""

from __future__ import annotations

import logging
import math
import re
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlencode

import httpx

log = logging.getLogger("skyalerts_functions.horizons")

SOLAR_BODIES: tuple[tuple[str, int], ...] = (
    ("ceres", 1),
    ("pluto", 134340),
    ("eris", 136199),
    ("haumea", 136108),
    ("makemake", 136472),
    ("gonggong", 225088),
    ("quaoar", 50000),
    ("sedna", 90377),
    ("orcus", 90482),
)

_CONSTELLATION_RE = re.compile(r"^[A-Z][a-z]{2}$")
HORIZONS_GIVE_UP_AFTER = 2


def horizons_url(command: int | str, day_iso: str) -> str:
    day_dt = datetime.fromisoformat(f"{day_iso}T00:00:00+00:00")
    next_iso = (day_dt + timedelta(days=1)).strftime("%Y-%m-%d")
    cmd_str = f"'{command};'" if isinstance(command, int) else f"'{command}'"
    params = {
        "format": "json",
        "COMMAND": cmd_str,
        "EPHEM_TYPE": "OBSERVER",
        "CENTER": "'500@399'",
        "START_TIME": f"'{day_iso}'",
        "STOP_TIME": f"'{next_iso}'",
        "STEP_SIZE": "'1 d'",
        "QUANTITIES": "'1,9,20,23,29'",
        "ANG_FORMAT": "DEG",
        "OBJ_DATA": "NO",
        "CSV_FORMAT": "YES",
    }
    return f"https://ssd.jpl.nasa.gov/api/horizons.api?{urlencode(params)}"


def parse_horizons(result: str) -> dict[str, Any] | None:
    """Parses the first observer row between `$$SOE` and `$$EOE`."""
    start = result.find("$$SOE")
    end = result.find("$$EOE")
    if start < 0 or end < start:
        return None
    lines = [ln.strip() for ln in result[start + 5 : end].splitlines() if ln.strip()]
    if not lines:
        return None
    cols = [c.strip() for c in lines[0].split(",")]
    if len(cols) < 12:
        return None
    try:
        ra = float(cols[3])
        dec = float(cols[4])
        mag = None if cols[5] == "n.a." else float(cols[5])
        distance_au = float(cols[7])
        elongation = float(cols[9])
        constellation = cols[11]
    except ValueError:
        return None

    if not all(math.isfinite(x) for x in (ra, dec, distance_au, elongation)):
        return None
    if ra < 0.0 or ra >= 360.0 or dec < -90.0 or dec > 90.0:
        return None
    if mag is not None and not math.isfinite(mag):
        return None
    if not _CONSTELLATION_RE.match(constellation):
        return None

    return {
        "ra": ra,
        "dec": dec,
        "mag": mag,
        "distance_au": distance_au,
        "elongation": elongation,
        "constellation": constellation,
    }


def fetch_all_ephemerides(
    *,
    now: datetime | None = None,
    http_client: httpx.Client | None = None,
) -> dict[str, dict[str, Any] | None]:
    """Looks up each body sequentially; gives up early if JPL is unreachable."""
    current = now or datetime.now(UTC)
    day_iso = current.strftime("%Y-%m-%d")
    own_client = http_client is None
    client = http_client or httpx.Client(
        timeout=5.0,
        headers={"User-Agent": "sky.henseler.app/1.0 (+https://sky.henseler.app/about)"},
    )
    out: dict[str, dict[str, Any] | None] = {}
    ok = 0
    failed = 0
    try:
        for body_id, number in SOLAR_BODIES:
            if ok == 0 and failed >= HORIZONS_GIVE_UP_AFTER:
                out[body_id] = None
                continue
            out[body_id] = None
            try:
                resp = client.get(horizons_url(number, day_iso))
                if resp.status_code == 200:
                    payload = resp.json()
                    raw_res = payload.get("result")
                    if isinstance(raw_res, str):
                        out[body_id] = parse_horizons(raw_res)
            except Exception as exc:
                log.warning("horizons_lookup_failed body=%s err=%s", body_id, exc)
            if out[body_id] is not None:
                ok += 1
            else:
                failed += 1
    finally:
        if own_client:
            client.close()
    return out
