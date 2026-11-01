import { describe, expect, it } from 'vitest'

import { ingestHealth } from '@/lib/admin/health'
import { insertAudit, listRuns, type RunRow } from '@/lib/admin/queries'
import type { Db } from '@/lib/queries'

const NOW = 1_793_000_000
const run = (o: Partial<RunRow>): RunRow => ({
  id: 1,
  startedAt: NOW - 3600,
  finishedAt: NOW - 3500,
  status: 'success',
  trigger: 'cron',
  surveys: ['lsst', 'ztf'],
  objectsSeen: 0,
  objectsUpserted: 0,
  classificationsUpserted: 0,
  objectsEnriched: 0,
  detectionsUpserted: 0,
  requests: 0,
  errorCount: 0,
  durationMs: 1000,
  ...o,
})

describe('ingestHealth', () => {
  it('is critical with no runs', () => {
    expect(ingestHealth([], NOW).level).toBe('critical')
  })

  it('is good after a recent success', () => {
    expect(ingestHealth([run({})], NOW)).toMatchObject({ level: 'good', label: 'Healthy' })
  })

  it('warns on partial runs and staleness, fails on failure', () => {
    expect(ingestHealth([run({ status: 'partial' })], NOW).level).toBe('warning')
    expect(ingestHealth([run({ startedAt: NOW - 30 * 3600 })], NOW).level).toBe('warning')
    const h = ingestHealth([run({ id: 3, status: 'failed' }), run({ id: 2 })], NOW)
    expect(h.level).toBe('critical')
    expect(h.reasons.join(' ')).toContain('#3')
  })

  it('looks past a run still in progress', () => {
    expect(ingestHealth([run({ id: 2, status: 'running' }), run({ id: 1, status: 'failed' })], NOW).level).toBe(
      'critical',
    )
  })
})

describe('admin queries', () => {
  function fakeDb() {
    const calls: { text: string; params: unknown[] }[] = []
    const db: Db = {
      async query<R>(text: string, params: unknown[] = []) {
        calls.push({ text, params })
        return { rows: [] as R[] }
      },
    }
    return { db, calls }
  }

  it('writes audit rows with bound values only', async () => {
    const { db, calls } = fakeDb()
    await insertAudit(db, { actor: 16056018, action: 'ingest.rerun', target: "x'); DROP", details: { login: 'a' } })
    expect(calls[0]!.text).not.toContain('DROP')
    expect(calls[0]!.text).not.toMatch(/\bat\b|\bid\b/) // never sets id or timestamp
    expect(calls[0]!.params).toEqual([16056018, 'ingest.rerun', "x'); DROP", '{"login":"a"}'])
  })

  it('clamps list limits', async () => {
    const { db, calls } = fakeDb()
    await listRuns(db, 10_000)
    await listRuns(db, -3)
    expect(calls.map((c) => c.params[0])).toEqual([500, 1])
  })
})
