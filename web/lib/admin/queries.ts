// Admin-only queries (run as skyalerts_web_admin: SELECT on data tables and
// ingest_runs, append-only INSERT on audit_log). Every value is a bind parameter.

import type { Db } from '../queries'

export type RunStatus = 'running' | 'success' | 'partial' | 'failed'

export interface RunRow {
  id: number
  startedAt: number // unix seconds
  finishedAt: number | null
  status: RunStatus
  trigger: string
  surveys: string[]
  objectsSeen: number
  objectsUpserted: number
  classificationsUpserted: number
  objectsEnriched: number
  detectionsUpserted: number
  requests: number
  errorCount: number
  durationMs: number | null
}

export interface RunDetail extends RunRow {
  errors: unknown
}

const RUN_COLUMNS = `id::float8 AS id,
  extract(epoch FROM started_at)::float8 AS "startedAt",
  extract(epoch FROM finished_at)::float8 AS "finishedAt",
  status, trigger, surveys,
  objects_seen AS "objectsSeen", objects_upserted AS "objectsUpserted",
  classifications_upserted AS "classificationsUpserted",
  objects_enriched AS "objectsEnriched", detections_upserted AS "detectionsUpserted",
  requests, error_count AS "errorCount", duration_ms AS "durationMs"`

export async function listRuns(db: Db, limit: number): Promise<RunRow[]> {
  const { rows } = await db.query<RunRow>(
    `SELECT ${RUN_COLUMNS} FROM ingest_runs ORDER BY id DESC LIMIT $1`,
    [Math.min(Math.max(1, Math.floor(limit)), 500)],
  )
  return rows
}

export async function getRun(db: Db, id: number): Promise<RunDetail | null> {
  const { rows } = await db.query<RunDetail>(`SELECT ${RUN_COLUMNS}, errors FROM ingest_runs WHERE id = $1`, [id])
  return rows[0] ?? null
}

/** A run holding the ingest lease right now (the ingest side expires leases after 10 min). */
export async function activeRun(db: Db): Promise<number | null> {
  const { rows } = await db.query<{ id: number }>(
    `SELECT id::float8 AS id FROM ingest_runs
      WHERE status = 'running' AND started_at > now() - interval '10 minutes'
      ORDER BY id DESC LIMIT 1`,
  )
  return rows[0]?.id ?? null
}

export interface AuditEntry {
  actor: number
  action: string
  target?: string | null
  details?: Record<string, unknown>
}

export async function insertAudit(db: Db, e: AuditEntry): Promise<void> {
  await db.query(
    `INSERT INTO audit_log (actor_github_id, action, target, details) VALUES ($1, $2, $3, $4::jsonb)`,
    [e.actor, e.action, e.target ?? null, JSON.stringify(e.details ?? {})],
  )
}

export interface AuditRow {
  id: number
  at: number
  actor: number
  action: string
  target: string | null
  details: Record<string, unknown>
}

export async function listAudit(db: Db, limit: number): Promise<AuditRow[]> {
  const { rows } = await db.query<AuditRow>(
    `SELECT id::float8 AS id, extract(epoch FROM at)::float8 AS at, actor_github_id::float8 AS actor,
            action, target, details
       FROM audit_log ORDER BY id DESC LIMIT $1`,
    [Math.min(Math.max(1, Math.floor(limit)), 500)],
  )
  return rows
}

export const NEON_FREE_LIMIT_BYTES = 512 * 1024 * 1024

export interface DataTotals {
  objects: number
  classifications: number
  detections: number
  enrichedObjects: number
  dbSizeBytes: number
  ssoMatched: number
  ssoNoMatch: number
  ssoError: number
  ssoPending: number
}

export async function dataTotals(db: Db): Promise<DataTotals> {
  const { rows } = await db.query<DataTotals>(
    `SELECT (SELECT count(*) FROM objects)::int AS objects,
            (SELECT count(*) FROM classifications)::int AS classifications,
            (SELECT count(*) FROM detections)::int AS detections,
            (SELECT count(*) FROM objects WHERE enriched_at IS NOT NULL)::int AS "enrichedObjects",
            pg_database_size(current_database())::float8 AS "dbSizeBytes",
            (SELECT count(*) FROM sso_identifications WHERE status = 'matched')::int AS "ssoMatched",
            (SELECT count(*) FROM sso_identifications WHERE status = 'no_match')::int AS "ssoNoMatch",
            (SELECT count(*) FROM sso_identifications WHERE status = 'error')::int AS "ssoError",
            (SELECT count(*) FROM objects o
              WHERE o.top_class = 'asteroid'
                AND o.meanra IS NOT NULL AND o.meandec IS NOT NULL AND o.firstmjd IS NOT NULL
                AND NOT EXISTS (
                  SELECT 1 FROM sso_identifications s
                   WHERE s.survey = o.survey AND s.oid = o.oid AND s.status IN ('matched', 'no_match')
                ))::int AS "ssoPending"`,
  )
  return (
    rows[0] ?? {
      objects: 0,
      classifications: 0,
      detections: 0,
      enrichedObjects: 0,
      dbSizeBytes: 0,
      ssoMatched: 0,
      ssoNoMatch: 0,
      ssoError: 0,
      ssoPending: 0,
    }
  )
}
