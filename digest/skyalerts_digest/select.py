"""Weekly digest selection from Postgres (runs as read-only role skyalerts_ro).

Every statement is parameterized. Returns deeply immutable frozen dataclasses.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import psycopg

from .classes import (
    ARTIFACT_CLASS,
    ASTEROID_CLASS,
    GROUPS,
    TRANSIENT_CLASSES,
    ClassGroup,
    group_of,
)

MJD_UNIX_EPOCH = 40587.0
HEADLINER_LIMIT = 5
BRIGHTEST_LIMIT = 3
SOLAR_EXAMPLE_LIMIT = 3

HEADLINERS_SQL = """
SELECT survey, oid, top_class, top_probability, firstmjd, lastmjd, ndet
  FROM objects
 WHERE firstmjd >= %s
   AND firstmjd <= %s
   AND top_class IS DISTINCT FROM %s
   AND top_class = ANY(%s)
 ORDER BY top_probability DESC NULLS LAST,
          lastmjd DESC NULLS LAST,
          survey ASC,
          oid ASC
 LIMIT %s
"""

BRIGHTEST_SQL = """
SELECT o.survey, o.oid, o.top_class, o.top_probability, o.firstmjd, o.lastmjd, o.ndet,
       d.eff_mag AS peak_mag, d.band AS peak_band
  FROM objects o
  JOIN (
      SELECT DISTINCT ON (survey, oid)
             survey,
             oid,
             COALESCE(mag, (-2.5 * log10(flux_njy) + 31.4)::real) AS eff_mag,
             band
        FROM detections
       WHERE mag IS NOT NULL
          OR (flux_njy IS NOT NULL AND flux_njy > 0)
       ORDER BY survey,
                oid,
                COALESCE(mag, (-2.5 * log10(flux_njy) + 31.4)::real) ASC,
                mjd DESC,
                measurement_id ASC
  ) d ON d.survey = o.survey AND d.oid = o.oid
 WHERE o.firstmjd >= %s
   AND o.firstmjd <= %s
   AND o.top_class IS DISTINCT FROM %s
   AND o.top_class IS DISTINCT FROM %s
 ORDER BY d.eff_mag ASC,
          o.top_probability DESC NULLS LAST,
          o.lastmjd DESC NULLS LAST,
          o.survey ASC,
          o.oid ASC
 LIMIT %s
"""

SOLAR_COUNT_SQL = """
SELECT count(*)::int
  FROM objects
 WHERE firstmjd >= %s
   AND firstmjd <= %s
   AND top_class = %s
"""

SOLAR_EXAMPLES_SQL = """
SELECT o.survey, o.oid, o.top_class, o.top_probability, o.firstmjd, o.lastmjd, o.ndet,
       NULL::real AS peak_mag, NULL::text AS peak_band,
       s.sso_name, s.sso_number, s.sep_arcsec
  FROM objects o
  LEFT JOIN sso_identifications s
    ON s.survey = o.survey
   AND s.oid = o.oid
   AND s.status = 'matched'
 WHERE o.firstmjd >= %s
   AND o.firstmjd <= %s
   AND o.top_class = %s
 ORDER BY (s.sso_name IS NOT NULL) DESC,
          o.top_probability DESC NULLS LAST,
          o.lastmjd DESC NULLS LAST,
          o.survey ASC,
          o.oid ASC
 LIMIT %s
"""

NEW_BY_CLASS_SQL = """
SELECT top_class, count(*)::int
  FROM objects
 WHERE firstmjd >= %s
   AND firstmjd <= %s
   AND top_class IS DISTINCT FROM %s
 GROUP BY top_class
"""

TOTALS_SQL = """
SELECT (SELECT count(*)::int FROM objects WHERE top_class IS DISTINCT FROM %s),
       (SELECT count(*)::int
          FROM detections d
          JOIN objects o USING (survey, oid)
         WHERE o.top_class IS DISTINCT FROM %s)
"""


def normalize_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def datetime_to_mjd(dt: datetime) -> float:
    return normalize_utc(dt).timestamp() / 86400.0 + MJD_UNIX_EPOCH


def mjd_to_datetime(mjd: float) -> datetime:
    return datetime(1970, 1, 1, tzinfo=UTC) + timedelta(days=mjd - MJD_UNIX_EPOCH)


@dataclass(frozen=True)
class DigestObject:
    survey: str
    oid: str
    top_class: str | None = None
    top_probability: float | None = None
    firstmjd: float | None = None
    lastmjd: float | None = None
    ndet: int | None = None
    peak_mag: float | None = None
    peak_band: str | None = None
    sso_name: str | None = None
    sso_number: int | None = None
    sep_arcsec: float | None = None


@dataclass(frozen=True)
class SolarSystemSection:
    asteroid_count: int
    examples: tuple[DigestObject, ...] = ()


@dataclass(frozen=True)
class GroupCount:
    group: ClassGroup
    label: str
    count: int


@dataclass(frozen=True)
class WeekStats:
    new_by_group: tuple[GroupCount, ...]
    total_objects: int
    total_detections: int

    @property
    def new_objects(self) -> int:
        return sum(g.count for g in self.new_by_group)

    def count_for(self, group: ClassGroup) -> int:
        for g in self.new_by_group:
            if g.group == group:
                return g.count
        return 0


@dataclass(frozen=True)
class Digest:
    week_start: datetime
    week_end: datetime
    start_mjd: float
    end_mjd: float
    headliners: tuple[DigestObject, ...] = ()
    brightest: tuple[DigestObject, ...] = ()
    solar_system: SolarSystemSection = SolarSystemSection(asteroid_count=0)
    stats: WeekStats = WeekStats(
        new_by_group=tuple(GroupCount(group=g.id, label=g.label, count=0) for g in GROUPS),
        total_objects=0,
        total_detections=0,
    )

    @property
    def is_empty(self) -> bool:
        return (
            not self.headliners
            and not self.brightest
            and self.solar_system.asteroid_count == 0
            and self.stats.new_objects == 0
        )


def _row_to_object(row: tuple[Any, ...]) -> DigestObject:
    survey, oid, top_class, top_prob, firstmjd, lastmjd, ndet = row[:7]
    peak_mag = float(row[7]) if len(row) > 7 and row[7] is not None else None
    peak_band = str(row[8]) if len(row) > 8 and row[8] is not None else None
    sso_name = str(row[9]) if len(row) > 9 and row[9] is not None else None
    sso_number = int(row[10]) if len(row) > 10 and row[10] is not None else None
    sep_arcsec = float(row[11]) if len(row) > 11 and row[11] is not None else None
    return DigestObject(
        survey=str(survey),
        oid=str(oid),
        top_class=str(top_class) if top_class is not None else None,
        top_probability=float(top_prob) if top_prob is not None else None,
        firstmjd=float(firstmjd) if firstmjd is not None else None,
        lastmjd=float(lastmjd) if lastmjd is not None else None,
        ndet=int(ndet) if ndet is not None else None,
        peak_mag=peak_mag,
        peak_band=peak_band,
        sso_name=sso_name,
        sso_number=sso_number,
        sep_arcsec=sep_arcsec,
    )


def select_digest(conn: psycopg.Connection[Any], week_end: datetime) -> Digest:
    end_dt = normalize_utc(week_end)
    start_dt = end_dt - timedelta(days=7)
    end_mjd = datetime_to_mjd(end_dt)
    start_mjd = end_mjd - 7.0

    headliner_rows = conn.execute(
        HEADLINERS_SQL,
        (start_mjd, end_mjd, ARTIFACT_CLASS, list(TRANSIENT_CLASSES), HEADLINER_LIMIT),
    ).fetchall()
    headliners = tuple(_row_to_object(r) for r in headliner_rows)

    brightest_rows = conn.execute(
        BRIGHTEST_SQL,
        (start_mjd, end_mjd, ARTIFACT_CLASS, ASTEROID_CLASS, BRIGHTEST_LIMIT),
    ).fetchall()
    brightest = tuple(_row_to_object(r) for r in brightest_rows)

    solar_count_row = conn.execute(
        SOLAR_COUNT_SQL,
        (start_mjd, end_mjd, ASTEROID_CLASS),
    ).fetchone()
    solar_count = int(solar_count_row[0]) if solar_count_row else 0

    solar_example_rows = conn.execute(
        SOLAR_EXAMPLES_SQL,
        (start_mjd, end_mjd, ASTEROID_CLASS, SOLAR_EXAMPLE_LIMIT),
    ).fetchall()
    solar_examples = tuple(_row_to_object(r) for r in solar_example_rows)

    class_rows = conn.execute(
        NEW_BY_CLASS_SQL,
        (start_mjd, end_mjd, ARTIFACT_CLASS),
    ).fetchall()
    counts_by_group: dict[ClassGroup, int] = {g.id: 0 for g in GROUPS}
    for cls_name, cnt in class_rows:
        grp = group_of(str(cls_name) if cls_name is not None else None)
        counts_by_group[grp] = counts_by_group.get(grp, 0) + int(cnt)

    new_by_group = tuple(
        GroupCount(group=g.id, label=g.label, count=counts_by_group[g.id]) for g in GROUPS
    )

    totals_row = conn.execute(
        TOTALS_SQL,
        (ARTIFACT_CLASS, ARTIFACT_CLASS),
    ).fetchone()
    total_objects = int(totals_row[0]) if totals_row else 0
    total_detections = int(totals_row[1]) if totals_row else 0

    return Digest(
        week_start=start_dt,
        week_end=end_dt,
        start_mjd=start_mjd,
        end_mjd=end_mjd,
        headliners=headliners,
        brightest=brightest,
        solar_system=SolarSystemSection(asteroid_count=solar_count, examples=solar_examples),
        stats=WeekStats(
            new_by_group=new_by_group,
            total_objects=total_objects,
            total_detections=total_detections,
        ),
    )
