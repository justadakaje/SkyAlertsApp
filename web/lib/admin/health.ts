// Ingest health for the admin overview. Pure: takes recent runs (newest first).

import type { RunRow } from './queries'

export type HealthLevel = 'good' | 'warning' | 'critical'

export interface Health {
  level: HealthLevel
  label: string
  reasons: string[]
}

// Cron is daily with ±59 min jitter on Vercel Hobby; allow a little slack.
const STALE_AFTER_S = 26 * 3600

export function ingestHealth(runs: RunRow[], nowS: number): Health {
  if (runs.length === 0) return { level: 'critical', label: 'No runs yet', reasons: ['No ingest run has been recorded.'] }

  const reasons: string[] = []
  let level: HealthLevel = 'good'
  const raise = (l: HealthLevel, why: string) => {
    reasons.push(why)
    if (l === 'critical' || (l === 'warning' && level === 'good')) level = l
  }

  const latest = runs[0]!
  const finished = runs.find((r) => r.status !== 'running')
  const ageH = Math.round((nowS - latest.startedAt) / 3600)
  if (nowS - latest.startedAt > STALE_AFTER_S) raise('warning', `No run started in ${ageH} h (expected daily).`)
  if (finished?.status === 'failed') raise('critical', `Run #${finished.id} failed.`)
  else if (finished?.status === 'partial') raise('warning', `Run #${finished.id} was partial (catch-up window not advanced).`)

  const lastSuccess = runs.find((r) => r.status === 'success')
  if (!lastSuccess) raise('warning', `None of the last ${runs.length} runs fully succeeded.`)

  const label = level === 'good' ? 'Healthy' : level === 'warning' ? 'Needs attention' : 'Failing'
  return { level, label, reasons: reasons.length ? reasons : ['Last run succeeded on schedule.'] }
}
