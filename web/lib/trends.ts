import { ARTIFACT_CLASS, GROUPS, groupOf, type ClassGroup } from './classes'
import type { DailyCount, DailySurveyCount } from './queries'
import type { DayBar } from './stats'

export interface GroupPanel {
  group: ClassGroup
  label: string
  days: { day: number; count: number }[]
  total: number
  peak: number
}

export interface DailyMultiples {
  firstDay: number
  lastDay: number
  maxCount: number
  panels: GroupPanel[]
  bars: DayBar[]
}

function emptyCounts(): Record<ClassGroup, number> {
  return Object.fromEntries(GROUPS.map((g) => [g.id, 0])) as Record<ClassGroup, number>
}

/**
 * Small-multiples series for the last `days` UTC days (today included):
 * one panel per class group in `GROUPS` order, sharing the x-axis and `maxCount` y-scale.
 * Artifacts are excluded.
 */
export function dailyMultiples(rows: DailyCount[], todayMjd: number, days = 90): DailyMultiples {
  const firstDay = todayMjd - days + 1
  const bars: DayBar[] = Array.from({ length: days }, (_, i) => ({
    day: firstDay + i,
    counts: emptyCounts(),
    total: 0,
  }))

  for (const r of rows) {
    if (r.topClass === ARTIFACT_CLASS) continue
    const bar = bars[r.day - firstDay]
    if (!bar) continue
    bar.counts[groupOf(r.topClass)] += r.n
    bar.total += r.n
  }

  const panels: GroupPanel[] = GROUPS.map((g) => {
    const series = bars.map((b) => ({ day: b.day, count: b.counts[g.id] }))
    const total = series.reduce((sum, d) => sum + d.count, 0)
    const peak = series.reduce((m, d) => Math.max(m, d.count), 0)
    return {
      group: g.id,
      label: g.label,
      days: series,
      total,
      peak,
    }
  })

  const maxCount = Math.max(1, ...panels.map((p) => p.peak))
  return { firstDay, lastDay: todayMjd, maxCount, panels, bars }
}

export interface WeekMixColumn {
  start: number // integer MJD of the first day in the 7-day week
  end: number // integer MJD of the last day in the 7-day week
  counts: Record<ClassGroup, number>
  pcts: Record<ClassGroup, number> // 0..100 share per class group
  total: number
}

/**
 * 100%-stacked weekly class mix for the last `weeks` full 7-day weeks ending `todayMjd`,
 * ordered oldest to newest (left to right). Artifacts are excluded.
 */
export function weeklyMix(rows: DailyCount[], todayMjd: number, weeks = 12): WeekMixColumn[] {
  const firstDay = todayMjd - weeks * 7 + 1
  const cols: WeekMixColumn[] = Array.from({ length: weeks }, (_, i) => {
    const start = firstDay + i * 7
    return {
      start,
      end: start + 6,
      counts: emptyCounts(),
      pcts: emptyCounts(),
      total: 0,
    }
  })

  for (const r of rows) {
    if (r.topClass === ARTIFACT_CLASS) continue
    if (r.day < firstDay || r.day > todayMjd) continue
    const idx = Math.floor((r.day - firstDay) / 7)
    const col = cols[idx]
    if (!col) continue
    col.counts[groupOf(r.topClass)] += r.n
    col.total += r.n
  }

  for (const col of cols) {
    if (col.total <= 0) continue
    for (const g of GROUPS) {
      col.pcts[g.id] = (col.counts[g.id] / col.total) * 100
    }
  }

  return cols
}

/**
 * Format week-over-week change as signed percentage text (e.g. "+12%", "-8%", "0%"),
 * or "—" when the prior period had zero events and the current period is non-zero.
 */
export function formatChange(current: number, previous: number): string {
  if (previous <= 0) return current === 0 ? '0%' : '—'
  const pct = Math.round(((current - previous) / previous) * 100)
  return pct > 0 ? `+${pct}%` : `${pct}%`
}

export interface SurveyWeekColumn {
  start: number
  end: number
  lsst: number
  ztf: number
  lsstPct: number
  ztfPct: number
  total: number
}

/**
 * Weekly Rubin (LSST) vs. ZTF volume and percentage share over the last `weeks` full 7-day weeks.
 */
export function weeklySurveyMix(rows: DailySurveyCount[], todayMjd: number, weeks = 12): SurveyWeekColumn[] {
  const firstDay = todayMjd - weeks * 7 + 1
  const cols: SurveyWeekColumn[] = Array.from({ length: weeks }, (_, i) => {
    const start = firstDay + i * 7
    return {
      start,
      end: start + 6,
      lsst: 0,
      ztf: 0,
      lsstPct: 0,
      ztfPct: 0,
      total: 0,
    }
  })

  for (const r of rows) {
    if (r.day < firstDay || r.day > todayMjd) continue
    const idx = Math.floor((r.day - firstDay) / 7)
    const col = cols[idx]
    if (!col) continue
    if (r.survey === 'lsst') col.lsst += r.n
    else if (r.survey === 'ztf') col.ztf += r.n
    col.total += r.n
  }

  for (const col of cols) {
    if (col.total <= 0) continue
    col.lsstPct = (col.lsst / col.total) * 100
    col.ztfPct = (col.ztf / col.total) * 100
  }

  return cols
}
