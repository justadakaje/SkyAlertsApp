import { describe, expect, it } from 'vitest'

import { dateToMjd } from '@/lib/astro'
import { classesByGroup, GROUPS } from '@/lib/classes'
import {
  formatAgo,
  formatCount,
  formatDay,
  formatObjectDescription,
  formatProbability,
  formatUtc,
} from '@/lib/format'

const now = new Date('2026-11-01T12:00:00Z')

describe('format', () => {
  it('renders UTC timestamps and days', () => {
    expect(formatUtc(new Date('2026-06-27T10:02:59Z'))).toBe('2026-06-27 10:02 UTC')
    expect(formatDay(new Date('2026-06-27T23:59:00Z'))).toBe('Jun 27')
  })

  it('describes elapsed time', () => {
    expect(formatAgo(new Date('2026-11-01T11:59:40Z'), now)).toBe('just now')
    expect(formatAgo(new Date('2026-11-01T11:15:00Z'), now)).toBe('45 min ago')
    expect(formatAgo(new Date('2026-10-31T12:00:00Z'), now)).toBe('24 h ago')
    expect(formatAgo(new Date('2026-10-20T12:00:00Z'), now)).toBe('12 days ago')
    expect(formatAgo(new Date('2018-12-15T12:00:00Z'), now)).toBe('8 years ago')
  })

  it('formats probabilities and counts', () => {
    expect(formatProbability(null)).toBe('—')
    expect(formatProbability(0.004)).toBe('<1%')
    expect(formatProbability(0.8547)).toBe('85%')
    expect(formatCount(999)).toBe('999')
    expect(formatCount(1284)).toBe('1.3K')
    expect(formatCount(12_900)).toBe('13K')
    expect(formatCount(4_200_000)).toBe('4.2M')
  })

  it('builds per-object share descriptions with fallbacks for missing fields', () => {
    const firstmjd = dateToMjd(new Date('2026-10-31T06:00:00Z'))
    expect(
      formatObjectDescription({
        survey: 'lsst',
        topClass: 'SN',
        probability: 0.85,
        firstmjd,
      }),
    ).toBe('Supernova · 85% confidence · Rubin (LSST) · first seen 2026-10-31')

    expect(
      formatObjectDescription({
        survey: 'ztf',
        topClass: null,
        probability: null,
        firstmjd: null,
      }),
    ).toBe('Unclassified · ZTF')
  })

  it('groups known classes by display group without duplicating labels', () => {
    for (const g of GROUPS) {
      const items = classesByGroup(g.id)
      expect(items.length).toBeGreaterThan(0)
      const labels = items.map((c) => c.label)
      expect(new Set(labels).size).toBe(labels.length)
    }
  })
})
