import { describe, expect, it } from 'vitest'

import { dailyBars, weeklyByClass } from '@/lib/stats'

const today = 61345

describe('dailyBars', () => {
  it('groups by class group and ignores days outside the range', () => {
    const bars = dailyBars(
      [
        { day: today, topClass: 'SNIa', n: 2 },
        { day: today, topClass: 'AGN', n: 5 },
        { day: today, topClass: null, n: 1 },
        { day: today - 29, topClass: 'RRL', n: 3 },
        { day: today - 30, topClass: 'SN', n: 9 },
        { day: today + 1, topClass: 'SN', n: 9 },
      ],
      today,
      30,
    )
    expect(bars).toHaveLength(30)
    expect(bars[0]).toMatchObject({ day: today - 29, total: 3 })
    expect(bars[0]!.counts.variable).toBe(3)
    expect(bars[29]!.counts).toMatchObject({ transient: 2, stochastic: 5, other: 1 })
    expect(bars.reduce((s, b) => s + b.total, 0)).toBe(11)
  })
})

describe('weeklyByClass', () => {
  it('buckets into 7-day blocks ending today, classes by volume', () => {
    const { weeks, classes } = weeklyByClass(
      [
        { day: today, topClass: 'SN', n: 1 },
        { day: today - 6, topClass: 'SN', n: 1 },
        { day: today - 7, topClass: 'AGN', n: 4 },
        { day: today - 83, topClass: null, n: 2 },
        { day: today - 84, topClass: 'SN', n: 50 },
      ],
      today,
      12,
    )
    expect(weeks[0]).toMatchObject({ start: today - 6, end: today, total: 2 })
    expect(weeks[1]!.byClass).toEqual({ AGN: 4 })
    expect(weeks[11]!.byClass).toEqual({ Unclassified: 2 })
    expect(classes).toEqual(['AGN', 'SN', 'Unclassified'])
  })
})
