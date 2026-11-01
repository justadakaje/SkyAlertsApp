import Link from 'next/link'

import type { HealthLevel } from '@/lib/admin/health'
import type { RunRow, RunStatus } from '@/lib/admin/queries'
import { formatAgo, formatUtc } from '@/lib/format'

export function CsrfInput({ token }: { token: string }) {
  return <input type="hidden" name="csrf" value={token} />
}

const STATUS_LEVEL: Record<RunStatus, HealthLevel | 'neutral'> = {
  success: 'good',
  partial: 'warning',
  failed: 'critical',
  running: 'neutral',
}
const ICON: Record<HealthLevel | 'neutral', string> = { good: '✓', warning: '!', critical: '✕', neutral: '…' }

/** Status is never colour alone: icon + label, with the colour on the icon. */
export function StatusPill({ level, label }: { level: HealthLevel | 'neutral'; label: string }) {
  return (
    <span className="status" data-level={level}>
      <span className="status-icon" aria-hidden="true">
        {ICON[level]}
      </span>
      {label}
    </span>
  )
}

export function RunStatusPill({ status }: { status: RunStatus }) {
  return <StatusPill level={STATUS_LEVEL[status]} label={status} />
}

export function formatDuration(ms: number | null): string {
  if (ms === null) return '—'
  return ms < 60_000 ? `${(ms / 1000).toFixed(1)} s` : `${Math.floor(ms / 60_000)} min ${Math.round((ms % 60_000) / 1000)} s`
}

export function When({ unix, now }: { unix: number | null; now: Date }) {
  if (unix === null) return <>—</>
  const d = new Date(unix * 1000)
  return (
    <time dateTime={d.toISOString()} title={formatUtc(d)}>
      {formatAgo(d, now)}
    </time>
  )
}

export function RunsTable({ runs, now }: { runs: RunRow[]; now: Date }) {
  return (
    <div className="table-scroll">
      <table>
        <thead>
          <tr>
            <th scope="col">Run</th>
            <th scope="col">Started</th>
            <th scope="col">Trigger</th>
            <th scope="col">Status</th>
            <th scope="col" className="num">
              Objects
            </th>
            <th scope="col" className="num hide-sm">
              Enriched
            </th>
            <th scope="col" className="num hide-sm">
              Points
            </th>
            <th scope="col" className="num hide-sm">
              Requests
            </th>
            <th scope="col" className="num">
              Duration
            </th>
            <th scope="col" className="num">
              Errors
            </th>
          </tr>
        </thead>
        <tbody>
          {runs.map((r) => (
            <tr key={r.id}>
              <td>
                <Link href={`/admin/runs/${r.id}`}>#{r.id}</Link>
              </td>
              <td>
                <When unix={r.startedAt} now={now} />
              </td>
              <td>{r.trigger}</td>
              <td>
                <RunStatusPill status={r.status} />
              </td>
              <td className="num">{r.objectsUpserted}</td>
              <td className="num hide-sm">{r.objectsEnriched}</td>
              <td className="num hide-sm">{r.detectionsUpserted}</td>
              <td className="num hide-sm">{r.requests}</td>
              <td className="num">{formatDuration(r.durationMs)}</td>
              <td className="num">{r.errorCount}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
