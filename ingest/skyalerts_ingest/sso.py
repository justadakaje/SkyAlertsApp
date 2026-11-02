"""Identify asteroid alerts against known Solar System objects via IMCCE SkyBoT.

    DATABASE_URL=... python -m skyalerts_ingest.sso [--max N]

Queries SkyBoT cone search at each asteroid candidate's (meanra, meandec, firstmjd)
with radius 0.003 deg (10.8") and stores the closest match within 10". See
docs/decisions.md #29.
"""

from __future__ import annotations

import argparse
import logging
import math
import os
import sys
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass
from typing import Any

import httpx
import psycopg

from . import logutil
from .alerce_client import USER_AGENT
from .store import Store

log = logging.getLogger("skyalerts.sso")

DEFAULT_SKYBOT_URL = "https://ssp.imcce.fr/webservices/skybot/api/conesearch.php"
OBSERVATORY_CODES: dict[str, str] = {"ztf": "I41", "lsst": "X05"}
MJD_TO_JD_OFFSET = 2400000.5
DEFAULT_RADIUS_DEG = 0.003  # 10.8"
MAX_SEP_ARCSEC = 10.0
DEFAULT_IDENTIFY_MAX = 30
DEFAULT_TIME_BUDGET_S = 240.0

IDENTIFY_CANDIDATES = """
SELECT o.survey, o.oid, o.meanra, o.meandec, o.firstmjd
  FROM objects o
  LEFT JOIN sso_identifications s ON s.survey = o.survey AND s.oid = o.oid
 WHERE o.top_class = 'asteroid'
   AND o.meanra IS NOT NULL
   AND o.meandec IS NOT NULL
   AND o.firstmjd IS NOT NULL
   AND (s.oid IS NULL
        OR (s.status = 'error' AND s.queried_at < now() - interval '1 day'))
 ORDER BY CASE WHEN o.survey = 'ztf' THEN 0 ELSE 1 END ASC,
          o.top_probability DESC NULLS LAST,
          o.lastmjd DESC NULLS LAST
 LIMIT %s
"""

UPSERT_SSO_IDENTIFICATION = """
INSERT INTO sso_identifications (
    survey, oid, obs_mjd, queried_at, status,
    sso_number, sso_name, sso_class, predicted_mag, sep_arcsec,
    ra_rate_arcsec_h, dec_rate_arcsec_h, geo_dist_au, helio_dist_au, error
)
VALUES (%s, %s, %s, now(), %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
ON CONFLICT (survey, oid) DO UPDATE SET
    obs_mjd           = EXCLUDED.obs_mjd,
    queried_at        = now(),
    status            = EXCLUDED.status,
    sso_number        = EXCLUDED.sso_number,
    sso_name          = EXCLUDED.sso_name,
    sso_class         = EXCLUDED.sso_class,
    predicted_mag     = EXCLUDED.predicted_mag,
    sep_arcsec        = EXCLUDED.sep_arcsec,
    ra_rate_arcsec_h  = EXCLUDED.ra_rate_arcsec_h,
    dec_rate_arcsec_h = EXCLUDED.dec_rate_arcsec_h,
    geo_dist_au       = EXCLUDED.geo_dist_au,
    helio_dist_au     = EXCLUDED.helio_dist_au,
    error             = EXCLUDED.error
"""


class SkyBotError(Exception):
    """SkyBoT transport, HTTP, or response-format error (never carries raw upstream body)."""

    def __init__(self, message: str, *, status: int | None = None):
        super().__init__(message)
        self.status = status


@dataclass(frozen=True)
class SkyBotHit:
    sso_number: int | None
    sso_name: str
    sso_class: str | None
    predicted_mag: float | None
    sep_arcsec: float
    ra_rate_arcsec_h: float | None
    dec_rate_arcsec_h: float | None
    geo_dist_au: float | None
    helio_dist_au: float | None


@dataclass
class IdentifyResult:
    queried: int = 0
    matched: int = 0
    no_match: int = 0
    errors: int = 0
    budget_hit: bool = False

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _opt_float(val: str) -> float | None:
    s = val.strip()
    if not s or s == "-":
        return None
    x = float(s)
    return x if math.isfinite(x) else None


def _opt_pos_float(val: str) -> float | None:
    x = _opt_float(val)
    return x if x is not None and x > 0 else None


def parse_conesearch(text: str) -> list[SkyBotHit]:
    """Parse a SkyBoT `-mime=text -output=basic` conesearch response, sorted by sep_arcsec ASC.

    An empty body means no match (`[]`). A negative `# Flag:` or malformed body raises SkyBotError.
    """
    if not text.strip():
        return []

    flag: int | None = None
    hits: list[SkyBotHit] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("#"):
            if line.lower().startswith("# flag:"):
                flag_str = line.split(":", 1)[1].strip()
                try:
                    flag = int(flag_str)
                except ValueError as exc:
                    raise SkyBotError("Invalid # Flag header in SkyBoT response") from exc
                if flag < 0:
                    raise SkyBotError(f"SkyBoT error flag: {flag}")
            continue

        if flag is None:
            raise SkyBotError("Missing # Flag header in SkyBoT response")
        parts = [p.strip() for p in line.split("|")]
        if len(parts) < 12:
            raise SkyBotError(f"Malformed SkyBoT row ({len(parts)} columns, expected 12)")
        num_s, name, _ra, _dec, sso_cls, mv_s, _err_s, d_s, dra_s, ddec_s, dg_s, dh_s = parts[:12]
        if not name:
            raise SkyBotError("Empty object name in SkyBoT row")
        try:
            sso_num = None if num_s in ("-", "") else int(num_s)
            if sso_num is not None and sso_num < 1:
                raise SkyBotError("Invalid object number in SkyBoT row")
            sep = float(d_s)
            if not math.isfinite(sep) or sep < 0:
                raise SkyBotError("Invalid separation in SkyBoT row")
            hit = SkyBotHit(
                sso_number=sso_num,
                sso_name=name[:128],
                sso_class=sso_cls[:64] if sso_cls else None,
                predicted_mag=_opt_float(mv_s),
                sep_arcsec=sep,
                ra_rate_arcsec_h=_opt_float(dra_s),
                dec_rate_arcsec_h=_opt_float(ddec_s),
                geo_dist_au=_opt_pos_float(dg_s),
                helio_dist_au=_opt_pos_float(dh_s),
            )
        except ValueError as exc:
            raise SkyBotError("Non-numeric value in SkyBoT row") from exc
        hits.append(hit)

    if flag is None:
        raise SkyBotError("Missing # Flag header in SkyBoT response")

    hits.sort(key=lambda h: h.sep_arcsec)
    return hits


class SkyBotClient:
    def __init__(
        self,
        *,
        url: str | None = None,
        min_interval: float | None = None,
        timeout: float = 30.0,
        radius_deg: float = DEFAULT_RADIUS_DEG,
        transport: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.url = url or os.getenv("SKYBOT_URL") or DEFAULT_SKYBOT_URL
        if min_interval is None:
            min_interval = float(os.getenv("SKYBOT_MIN_INTERVAL_S", "1.0"))
        self.min_interval = max(0.0, min_interval)
        self.radius_deg = radius_deg
        self.timeout_s = timeout
        self._sleep = sleep
        self._clock = clock
        self._last_request: float | None = None
        self.request_count = 0
        self._http = httpx.Client(
            timeout=httpx.Timeout(timeout),
            headers={"User-Agent": USER_AGENT},
            transport=transport,
            follow_redirects=False,
        )

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> SkyBotClient:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def _throttle(self) -> None:
        if self._last_request is not None:
            wait = self.min_interval - (self._clock() - self._last_request)
            if wait > 0:
                self._sleep(wait)
        self._last_request = self._clock()

    def conesearch(
        self,
        survey: str,
        ra: float,
        dec: float,
        mjd: float,
        *,
        radius_deg: float | None = None,
    ) -> list[SkyBotHit]:
        loc = OBSERVATORY_CODES.get(survey)
        if loc is None:
            raise ValueError(f"survey must be one of {tuple(OBSERVATORY_CODES)}")
        if not (math.isfinite(ra) and math.isfinite(dec) and math.isfinite(mjd)):
            raise ValueError("ra, dec, and mjd must be finite")

        rd = self.radius_deg if radius_deg is None else radius_deg
        params = {
            "-ep": str(mjd + MJD_TO_JD_OFFSET),
            "-ra": str(ra),
            "-dec": str(dec),
            "-rd": str(rd),
            "-loc": loc,
            "-mime": "text",
            "-output": "basic",
        }
        self._throttle()
        self.request_count += 1
        started = self._clock()
        try:
            resp = self._http.get(self.url, params=params)
        except httpx.HTTPError as exc:
            raise SkyBotError(f"transport error: {type(exc).__name__}") from exc

        elapsed_ms = round((self._clock() - started) * 1000)
        log.info(
            "skybot request",
            extra={"survey": survey, "status": resp.status_code, "elapsed_ms": elapsed_ms},
        )
        if resp.status_code != 200:
            raise SkyBotError(f"HTTP {resp.status_code} from SkyBoT", status=resp.status_code)
        return parse_conesearch(resp.text)


def _upsert_identification(
    conn: psycopg.Connection[Any],
    survey: str,
    oid: str,
    obs_mjd: float,
    status: str,
    hit: SkyBotHit | None,
    error: str | None,
) -> None:
    conn.execute(
        UPSERT_SSO_IDENTIFICATION,
        (
            survey,
            oid,
            obs_mjd,
            status,
            hit.sso_number if hit else None,
            hit.sso_name if hit else None,
            hit.sso_class if hit else None,
            hit.predicted_mag if hit else None,
            hit.sep_arcsec if hit else None,
            hit.ra_rate_arcsec_h if hit else None,
            hit.dec_rate_arcsec_h if hit else None,
            hit.geo_dist_au if hit else None,
            hit.helio_dist_au if hit else None,
            error,
        ),
    )


def identify_run(
    store_or_conn: Store | psycopg.Connection[Any],
    client: SkyBotClient,
    max_objects: int | None = None,
    time_budget_s: float | None = None,
    *,
    monotonic: Callable[[], float] = time.monotonic,
) -> IdentifyResult:
    if max_objects is None:
        max_objects = int(os.getenv("IDENTIFY_MAX", str(DEFAULT_IDENTIFY_MAX)))
    if time_budget_s is None:
        time_budget_s = float(os.getenv("IDENTIFY_TIME_BUDGET_S", str(DEFAULT_TIME_BUDGET_S)))

    res = IdentifyResult()
    if max_objects <= 0:
        return res

    conn = store_or_conn.conn if isinstance(store_or_conn, Store) else store_or_conn
    started = monotonic()
    rows = conn.execute(IDENTIFY_CANDIDATES, (max_objects,)).fetchall()
    for survey_raw, oid_raw, ra_raw, dec_raw, mjd_raw in rows:
        survey, oid = str(survey_raw), str(oid_raw)
        ra, dec, firstmjd = float(ra_raw), float(dec_raw), float(mjd_raw)
        # Reserve one full request timeout so a slow last query still ends inside the
        # budget (240 s budget + 30 s timeout stays under Vercel's 300 s maxDuration).
        if monotonic() - started + client.timeout_s > time_budget_s:
            res.budget_hit = True
            log.warning("identify time budget reached", extra={"survey": survey, "oid": oid})
            break

        res.queried += 1
        try:
            hits = client.conesearch(survey, ra, dec, firstmjd)
        except SkyBotError as exc:
            err_msg = str(exc)[:200]
            _upsert_identification(conn, survey, oid, firstmjd, "error", None, err_msg)
            res.errors += 1
            log.warning(
                "skybot query failed",
                extra={"survey": survey, "oid": oid, "error": err_msg},
            )
            continue

        best = hits[0] if hits and hits[0].sep_arcsec <= MAX_SEP_ARCSEC else None
        if best is not None:
            _upsert_identification(conn, survey, oid, firstmjd, "matched", best, None)
            res.matched += 1
            log.info(
                "sso matched",
                extra={
                    "survey": survey,
                    "oid": oid,
                    "sso_name": best.sso_name,
                    "sep_arcsec": best.sep_arcsec,
                },
            )
        else:
            _upsert_identification(conn, survey, oid, firstmjd, "no_match", None, None)
            res.no_match += 1
            log.info("sso no match", extra={"survey": survey, "oid": oid})

    log.info("identify finished", extra=res.as_dict())
    return res


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--max", dest="max_objects", type=int, default=None)
    args = ap.parse_args(argv)
    logutil.configure(os.getenv("LOG_LEVEL", "INFO"))
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        print("DATABASE_URL is not set", file=sys.stderr)
        return 2
    store = Store.connect(dsn)
    try:
        with SkyBotClient() as client:
            identify_run(store, client, max_objects=args.max_objects)
    finally:
        store.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
