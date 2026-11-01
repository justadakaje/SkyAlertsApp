import { describe, expect, it } from 'vitest'

import { formatAgo, formatCount, formatDay, formatProbability, formatUtc } from '@/lib/format'

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
})
