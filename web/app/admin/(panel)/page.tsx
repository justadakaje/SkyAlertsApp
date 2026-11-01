import Link from 'next/link'

import { CsrfInput, RunsTable, StatusPill, When } from '@/components/admin/AdminBits'
import { getAdminPool } from '@/lib/admin/db'
import { ingestHealth } from '@/lib/admin/health'
import { activeRun, dataTotals, listAudit, listRuns } from '@/lib/admin/queries'
import { triggerConfig } from '@/lib/auth/config'
import { requireAdmin } from '@/lib/auth/server'
import type { SearchParams } from '@/lib/filters'
import { formatCount } from '@/lib/format'

import { runIngestNow } from '../actions'

const NOTICES: Record<string, { level: 'good' | 'warning' | 'critical'; text: string }> = {
  requested: { level: 'good', text: 'Ingest run requested. It takes a few minutes; refresh to see it below.' },
  busy: { level: 'warning', text: 'A run is already in progress. Try again when it finishes.' },
  unconfigured: { level: 'critical', text: 'Manual re-run is not configured (MANUAL_TRIGGER_URL / MANUAL_TRIGGER_SECRET).' },
  expired: { level: 'warning', text: 'That form had expired. Please try again.' },
}

export default async function AdminOverview({ searchParams }: { searchParams: Promise<SearchParams> }) {
  const { csrf } = await requireAdmin()
  const sp = await searchParams
  const notice = typeof sp.notice === 'string' ? NOTICES[sp.notice] : undefined

  const db = getAdminPool()
  const [runs, totals, audit, running] = await Promise.all([
    listRuns(db, 20),
    dataTotals(db),
    listAudit(db, 5),
    activeRun(db),
  ])
  const now = new Date()
  const health = ingestHealth(runs, now.getTime() / 1000)
  const lastSuccess = runs.find((r) => r.status === 'success')

  return (
    <>
      <h1>Overview</h1>
      {notice ? (
        <p className="notice" data-level={notice.level} role="status">
          {notice.text}
        </p>
      ) : null}

      <section className="panel" aria-labelledby="health-heading">
        <h2 id="health-heading">
          Ingest health <StatusPill level={health.level} label={health.label} />
        </h2>
        <ul className="reasons">
          {health.reasons.map((r) => (
            <li key={r}>{r}</li>
          ))}
        </ul>
        <div className="tiles">
          <div className="tile">
            <p className="tile-label">Last run</p>
            <p className="tile-value small-value">
              <When unix={runs[0]?.startedAt ?? null} now={now} />
            </p>
          </div>
          <div className="tile">
            <p className="tile-label">Last full success</p>
            <p className="tile-value small-value">
              <When unix={lastSuccess?.startedAt ?? null} now={now} />
            </p>
          </div>
          <div className="tile">
            <p className="tile-label">Objects / light-curve points</p>
            <p className="tile-value small-value">
              {formatCount(totals.objects)} / {formatCount(totals.detections)}
            </p>
          </div>
          <div className="tile">
            <p className="tile-label">Objects enriched</p>
            <p className="tile-value small-value">{formatCount(totals.enrichedObjects)}</p>
          </div>
        </div>
        <form action={runIngestNow} className="rerun">
          <CsrfInput token={csrf} />
          <button type="submit" disabled={running !== null || !triggerConfig()}>
            {running !== null ? `Run #${running} in progress` : 'Run ingest now'}
          </button>
          <span className="muted small">
            Starts a manual run on the ingest project. It is logged in the audit log and takes a few minutes.
          </span>
        </form>
      </section>

      <section className="panel" aria-labelledby="runs-heading">
        <h2 id="runs-heading">Recent runs</h2>
        {runs.length ? <RunsTable runs={runs.slice(0, 10)} now={now} /> : <p className="muted">No runs yet.</p>}
        <p className="small">
          <Link href="/admin/runs">All runs →</Link>
        </p>
      </section>

      <section className="panel" aria-labelledby="audit-heading">
        <h2 id="audit-heading">Recent admin activity</h2>
        {audit.length ? (
          <ul className="audit-list">
            {audit.map((a) => (
              <li key={a.id}>
                <When unix={a.at} now={now} /> · <code>{a.action}</code> by #{a.actor}
              </li>
            ))}
          </ul>
        ) : (
          <p className="muted">Nothing yet.</p>
        )}
        <p className="small">
          <Link href="/admin/audit">Full audit log →</Link>
        </p>
      </section>
    </>
  )
}
