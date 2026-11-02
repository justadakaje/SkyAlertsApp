import { describe, expect, it } from 'vitest'

import {
  digestNotice,
  isValidWeekEnd,
  parseDigestPreview,
  parseDigestSendResponse,
  parseHeadliners,
  podcastFilename,
  sendDigestHref,
} from '@/lib/admin/digest'
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

describe('digest helpers', () => {
  it('validates week_end strictly before building the podcast filename', () => {
    expect(isValidWeekEnd('2026-11-01')).toBe(true)
    expect(podcastFilename('2026-11-01')).toBe('sky-this-week-2026-11-01.md')
    expect(podcastFilename('2026-11-1')).toBeNull()
    expect(podcastFilename('2026-11-01"; evil=1')).toBeNull()
    expect(podcastFilename('../2026-11-01')).toBeNull()
    expect(podcastFilename('2026-11-01\r\nX-Injected: 1')).toBeNull()
    expect(podcastFilename(null)).toBeNull()
  })

  it('builds allowlisted notices and enforces numeric-only headliner counts', () => {
    expect(parseHeadliners('5')).toBe(5)
    expect(parseHeadliners(['12'])).toBe(12)
    expect(parseHeadliners('5; drop')).toBeNull()
    expect(parseHeadliners('-1')).toBeNull()
    expect(parseHeadliners(undefined)).toBeNull()

    expect(sendDigestHref('digest_sent', 4)).toBe('/admin/digest?notice=digest_sent&headliners=4')
    expect(sendDigestHref('digest_sent', 'bad')).toBe('/admin/digest?notice=digest_sent')
    expect(sendDigestHref('digest_failed')).toBe('/admin/digest?notice=digest_failed')
    expect(sendDigestHref('digest_unconfigured')).toBe('/admin/digest?notice=digest_unconfigured')

    expect(digestNotice({ notice: 'digest_sent', headliners: '1' })).toEqual({
      level: 'good',
      text: 'Digest sent (1 headliner). Sends are idempotent: one send per UTC day.',
    })
    expect(digestNotice({ notice: 'digest_sent', headliners: '4' })?.text).toContain('(4 headliners)')
    expect(digestNotice({ notice: 'digest_sent', headliners: '<script>' })?.text).toBe(
      'Digest sent. Sends are idempotent: one send per UTC day.',
    )
    expect(digestNotice({ notice: 'digest_failed' })?.level).toBe('critical')
    expect(digestNotice({ notice: 'digest_unconfigured' })?.level).toBe('critical')
    expect(digestNotice({ notice: 'expired' })?.level).toBe('warning')
    expect(digestNotice({ notice: 'unknown' })).toBeNull()
  })

  it('validates preview and manual-send payloads against the shared contract', () => {
    const validPreview = {
      status: 'ok',
      week_end: '2026-11-01',
      subject: 'Sky Alerts · Week of 2026-11-01',
      headliners: 3,
      digest_markdown: '# Digest',
      podcast_markdown: '# Podcast',
    }
    expect(parseDigestPreview(validPreview)).toEqual({
      weekEnd: '2026-11-01',
      subject: 'Sky Alerts · Week of 2026-11-01',
      headliners: 3,
      digestMarkdown: '# Digest',
      podcastMarkdown: '# Podcast',
    })
    expect(parseDigestPreview({ ...validPreview, status: 'failed' })).toBeNull()
    expect(parseDigestPreview({ ...validPreview, week_end: 'bad' })).toBeNull()
    expect(parseDigestPreview({ ...validPreview, headliners: -1 })).toBeNull()

    expect(
      parseDigestSendResponse({ status: 'sent', week_end: '2026-11-01', headliners: 3, id: 're_123' }),
    ).toEqual({
      weekEnd: '2026-11-01',
      headliners: 3,
      id: 're_123',
    })
    expect(parseDigestSendResponse({ status: 'failed' })).toBeNull()
    expect(parseDigestSendResponse({ status: 'sent', week_end: '2026-11-01', headliners: 3, id: '' })).toBeNull()
  })
})
