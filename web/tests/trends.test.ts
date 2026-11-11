import { describe, expect, it } from 'vitest'

import { GROUPS } from '@/lib/classes'
import { dailyMultiples, formatChange, weeklyMix, weeklySurveyMix } from '@/lib/trends'

const today = 61345

describe('dailyMultiples', () => {
  it('builds one 90-day panel per class group on a shared y-scale and excludes artifacts', () => {
    const res = dailyMultiples(
      [
        { day: today, topClass: 'SNIa', n: 4 },
        { day: today, topClass: 'SNII', n: 3 },
        { day: today - 89, topClass: 'AGN', n: 12 },
        { day: today - 90, topClass: 'AGN', n: 99 }, // outside 90-day window
        { day: today, topClass: 'bogus', n: 50 }, // artifact excluded
        { day: today - 10, topClass: null, n: 2 },
      ],
      today,
      90,
    )

    expect(res.firstDay).toBe(today - 89)
    expect(res.lastDay).toBe(today)
    expect(res.bars).toHaveLength(90)
    expect(res.panels.map((p) => p.group)).toEqual(GROUPS.map((g) => g.id))
    expect(res.maxCount).toBe(12)

    const stochastic = res.panels.find((p) => p.group === 'stochastic')!
    expect(stochastic.total).toBe(12)
    expect(stochastic.peak).toBe(12)
    expect(stochastic.days[0]).toEqual({ day: today - 89, count: 12 })

    const transient = res.panels.find((p) => p.group === 'transient')!
    expect(transient.total).toBe(7)
    expect(transient.days[89]).toEqual({ day: today, count: 7 })

    const other = res.panels.find((p) => p.group === 'other')!
    expect(other.total).toBe(2)
  })
})

describe('weeklyMix', () => {
  it('computes 100%-stacked shares for 12 full 7-day weeks in chronological order', () => {
    const weeks = weeklyMix(
      [
        { day: today - 83, topClass: 'AGN', n: 3 },
        { day: today - 77, topClass: 'SN', n: 1 },
        { day: today - 84, topClass: 'SN', n: 40 }, // before week 0
        { day: today, topClass: 'RRL', n: 6 },
        { day: today - 6, topClass: 'asteroid', n: 2 },
        { day: today, topClass: 'bogus', n: 20 }, // artifact excluded
      ],
      today,
      12,
    )

    expect(weeks).toHaveLength(12)
    expect(weeks[0]).toMatchObject({ start: today - 83, end: today - 77, total: 4 })
    expect(weeks[0]!.pcts.stochastic).toBe(75)
    expect(weeks[0]!.pcts.transient).toBe(25)

    expect(weeks[11]).toMatchObject({ start: today - 6, end: today, total: 8 })
    expect(weeks[11]!.pcts.variable).toBe(75)
    expect(weeks[11]!.pcts.solar).toBe(25)

    // Empty weeks have 0% across all groups
    expect(weeks[5]!.total).toBe(0)
    expect(Object.values(weeks[5]!.pcts).every((v) => v === 0)).toBe(true)
  })
})

describe('formatChange', () => {
  it('formats signed percentage changes and handles zero baselines', () => {
    expect(formatChange(112, 100)).toBe('+12%')
    expect(formatChange(88, 100)).toBe('-12%')
    expect(formatChange(50, 50)).toBe('0%')
    expect(formatChange(0, 0)).toBe('0%')
    expect(formatChange(5, 0)).toBe('—')
  })
})

describe('weeklySurveyMix', () => {
  it('computes Rubin (LSST) vs ZTF weekly shares across 12 weeks', () => {
    const weeks = weeklySurveyMix(
      [
        { day: today, survey: 'lsst', n: 30 },
        { day: today - 2, survey: 'ztf', n: 10 },
      ],
      today,
      12,
    )
    expect(weeks).toHaveLength(12)
    expect(weeks[11]).toMatchObject({
      start: today - 6,
      end: today,
      lsst: 30,
      ztf: 10,
      lsstPct: 75,
      ztfPct: 25,
      total: 40,
    })
  })
})
