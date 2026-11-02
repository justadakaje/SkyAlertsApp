// Read-only queries for the public site (runs as skyalerts_ro). Every value is a
// bind parameter; the only SQL chosen in code is the ORDER BY, from a fixed map.

import { ARTIFACT_CLASS, LOW_PRIORITY_CLASSES, TRANSIENT_CLASSES } from './classes'
import { PAGE_SIZE, type HomeFilters, type Sort, type Survey } from './filters'
import type { Detection } from './lightcurve'

export interface Db {
  query<R>(text: string, params?: unknown[]): Promise<{ rows: R[] }>
}

export interface EventRow {
  survey: Survey
  oid: string
  topClass: string | null
  probability: number | null
  classifier: string | null
  firstmjd: number | null
  lastmjd: number | null
  ndet: number | null
  ra: number | null
  dec: number | null
}

export interface ObjectRow extends EventRow {
  nForced: number | null
  classifierVersion: string | null
}

export interface ClassificationRow {
  classifier: string
  version: string
  className: string
  probability: number
  ranking: number | null
}

const EVENT_COLUMNS = `survey, oid, top_class AS "topClass", top_probability AS probability,
  top_classifier AS classifier, firstmjd, lastmjd, ndet, meanra AS ra, meandec AS dec`

// Tier 0: explosions & outbursts, 1: everything else, 2: active galaxies, 3: unclassified.
const TIER = `CASE WHEN top_class = ANY($5::text[]) THEN 0
  WHEN top_class = ANY($6::text[]) THEN 2
  WHEN top_class IS NULL THEN 3 ELSE 1 END`

export const ORDER_BY: Record<Sort, string> = {
  notable: 'tier, top_probability DESC NULLS LAST, lastmjd DESC NULLS LAST, survey, oid',
  newest: 'lastmjd DESC NULLS LAST, survey, oid',
}

export async function listEvents(
  db: Db,
  f: HomeFilters,
  sinceMjd: number,
): Promise<{ rows: EventRow[]; hasMore: boolean }> {
  const showArtifacts = f.artifacts || f.cls === ARTIFACT_CLASS
  const { rows } = await db.query<EventRow & { tier: number }>(
    `SELECT ${EVENT_COLUMNS}, ${TIER} AS tier
       FROM objects
      WHERE lastmjd >= $1
        AND ($2::text IS NULL OR survey = $2)
        AND ($3::text IS NULL OR top_class = $3)
        AND ($4::boolean OR top_class IS DISTINCT FROM '${ARTIFACT_CLASS}')
      ORDER BY ${ORDER_BY[f.sort]}
      LIMIT $7 OFFSET $8`,
    [
      sinceMjd,
      f.survey,
      f.cls,
      showArtifacts,
      TRANSIENT_CLASSES,
      LOW_PRIORITY_CLASSES,
      PAGE_SIZE + 1,
      (f.page - 1) * PAGE_SIZE,
    ],
  )
  const page = rows.slice(0, PAGE_SIZE).map(({ tier, ...r }) => r)
  return { rows: page, hasMore: rows.length > PAGE_SIZE }
}

export async function classCounts(
  db: Db,
  survey: Survey | null,
  sinceMjd: number,
): Promise<{ topClass: string | null; n: number }[]> {
  const { rows } = await db.query<{ topClass: string | null; n: number }>(
    `SELECT top_class AS "topClass", count(*)::int AS n
       FROM objects
      WHERE lastmjd >= $1 AND ($2::text IS NULL OR survey = $2)
      GROUP BY top_class
      ORDER BY n DESC, top_class`,
    [sinceMjd, survey],
  )
  return rows
}

export async function getObject(db: Db, survey: Survey, oid: string): Promise<ObjectRow | null> {
  const { rows } = await db.query<ObjectRow>(
    `SELECT ${EVENT_COLUMNS}, n_forced AS "nForced", top_classifier_version AS "classifierVersion"
       FROM objects WHERE survey = $1 AND oid = $2`,
    [survey, oid],
  )
  return rows[0] ?? null
}

export async function getClassifications(
  db: Db,
  survey: Survey,
  oid: string,
): Promise<ClassificationRow[]> {
  const { rows } = await db.query<ClassificationRow>(
    `SELECT classifier_name AS classifier, classifier_version AS version, class_name AS "className",
            probability, ranking
       FROM classifications
      WHERE survey = $1 AND oid = $2
      ORDER BY classifier_name, classifier_version, probability DESC`,
    [survey, oid],
  )
  return rows
}

// ZTF magpsf is a difference magnitude. When ALeRCE has corrected it to an apparent
// magnitude (variable stars), plot that; an uncorrected negative difference
// (isdiffpos -1) has no meaningful magnitude and is flagged so the chart can skip it.
// jsonb comparisons only, so odd upstream values can't make a cast fail.
const CORRECTED = `raw->'corrected' = 'true'::jsonb`

export async function getDetections(db: Db, survey: Survey, oid: string): Promise<Detection[]> {
  const { rows } = await db.query<Detection>(
    `SELECT mjd, band,
            CASE WHEN ${CORRECTED} AND jsonb_typeof(raw->'magpsf_corr') = 'number'
                 THEN (raw->>'magpsf_corr')::float8 ELSE mag END AS mag,
            CASE WHEN ${CORRECTED} AND jsonb_typeof(raw->'sigmapsf_corr') = 'number'
                 THEN (raw->>'sigmapsf_corr')::float8 ELSE mag_err END AS "magErr",
            flux_njy AS "fluxNjy", flux_err_njy AS "fluxErrNjy",
            (raw->'isdiffpos' IN ('-1'::jsonb, '"-1"'::jsonb, '"f"'::jsonb)
              AND raw->'corrected' IS DISTINCT FROM 'true'::jsonb) AS negative
       FROM detections
      WHERE survey = $1 AND oid = $2
      ORDER BY mjd
      LIMIT 2000`,
    [survey, oid],
  )
  return rows
}

export interface DailyCount {
  day: number // integer MJD
  topClass: string | null
  n: number
}

/** New (first-detected) objects per UTC day and class, artifacts excluded. */
export async function dailyCounts(db: Db, sinceMjd: number): Promise<DailyCount[]> {
  const { rows } = await db.query<DailyCount>(
    `SELECT floor(firstmjd)::int AS day, top_class AS "topClass", count(*)::int AS n
       FROM objects
      WHERE firstmjd >= $1 AND top_class IS DISTINCT FROM '${ARTIFACT_CLASS}'
      GROUP BY 1, 2
      ORDER BY 1, 2`,
    [sinceMjd],
  )
  return rows
}

export interface Totals {
  objects: number
  newThisWeek: number
  transientsThisWeek: number
  detections: number
}

export async function totals(db: Db, weekAgoMjd: number): Promise<Totals> {
  const { rows } = await db.query<Totals>(
    `SELECT count(*)::int AS objects,
            (count(*) FILTER (WHERE firstmjd >= $1))::int AS "newThisWeek",
            (count(*) FILTER (WHERE firstmjd >= $1 AND top_class = ANY($2::text[])))::int
              AS "transientsThisWeek",
            (SELECT count(*)::int FROM detections) AS detections
       FROM objects
      WHERE top_class IS DISTINCT FROM '${ARTIFACT_CLASS}'`,
    [weekAgoMjd, TRANSIENT_CLASSES],
  )
  return rows[0] ?? { objects: 0, newThisWeek: 0, transientsThisWeek: 0, detections: 0 }
}

export interface WeekComparison {
  newThisWeek: number
  newLastWeek: number
  transientsThisWeek: number
  transientsLastWeek: number
}

/** This week vs last week counts (new objects, explosions & outbursts), artifacts excluded. */
export async function weekComparison(
  db: Db,
  weekAgoMjd: number,
  twoWeeksAgoMjd: number,
): Promise<WeekComparison> {
  const { rows } = await db.query<WeekComparison>(
    `SELECT (count(*) FILTER (WHERE firstmjd >= $1))::int AS "newThisWeek",
            (count(*) FILTER (WHERE firstmjd >= $2 AND firstmjd < $1))::int AS "newLastWeek",
            (count(*) FILTER (WHERE firstmjd >= $1 AND top_class = ANY($3::text[])))::int
              AS "transientsThisWeek",
            (count(*) FILTER (WHERE firstmjd >= $2 AND firstmjd < $1 AND top_class = ANY($3::text[])))::int
              AS "transientsLastWeek"
       FROM objects
      WHERE firstmjd >= $2 AND top_class IS DISTINCT FROM '${ARTIFACT_CLASS}'`,
    [weekAgoMjd, twoWeeksAgoMjd, TRANSIENT_CLASSES],
  )
  return (
    rows[0] ?? {
      newThisWeek: 0,
      newLastWeek: 0,
      transientsThisWeek: 0,
      transientsLastWeek: 0,
    }
  )
}

/** Unix seconds of the last ingest run that stored data, or null. Errors stay admin-only. */
export async function lastUpdated(db: Db): Promise<number | null> {
  const { rows } = await db.query<{ finished: number | null }>(
    `SELECT extract(epoch FROM max(finished_at))::float8 AS finished
       FROM ingest_runs WHERE status IN ('success', 'partial')`,
  )
  return rows[0]?.finished ?? null
}
