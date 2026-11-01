import { GROUPS, groupOf, type ClassGroup } from './classes'
import type { DailyCount } from './queries'

export interface DayBar {
  day: number // integer MJD
  counts: Record<ClassGroup, number>
  total: number
}

function emptyCounts(): Record<ClassGroup, number> {
  return Object.fromEntries(GROUPS.map((g) => [g.id, 0])) as Record<ClassGroup, number>
}

/** One bar per UTC day for the last `days` days (today included), grouped by class group. */
export function dailyBars(rows: DailyCount[], todayMjd: number, days = 30): DayBar[] {
  const first = todayMjd - days + 1
  const bars: DayBar[] = Array.from({ length: days }, (_, i) => ({
    day: first + i,
    counts: emptyCounts(),
    total: 0,
  }))
  for (const r of rows) {
    const bar = bars[r.day - first]
    if (!bar) continue
    bar.counts[groupOf(r.topClass)] += r.n
    bar.total += r.n
  }
  return bars
}

export interface WeekColumn {
  start: number // integer MJD of the first day
  end: number // integer MJD of the last day
  total: number
  byClass: Record<string, number>
}

/** Rolling 7-day buckets ending today, newest first, with per-class counts. */
export function weeklyByClass(
  rows: DailyCount[],
  todayMjd: number,
  weeks = 12,
): { weeks: WeekColumn[]; classes: string[] } {
  const cols: WeekColumn[] = Array.from({ length: weeks }, (_, i) => ({
    start: todayMjd - 7 * (i + 1) + 1,
    end: todayMjd - 7 * i,
    total: 0,
    byClass: {},
  }))
  const totals = new Map<string, number>()
  for (const r of rows) {
    const idx = Math.floor((todayMjd - r.day) / 7)
    const col = cols[idx]
    if (!col || r.day > todayMjd) continue
    const key = r.topClass ?? 'Unclassified'
    col.byClass[key] = (col.byClass[key] ?? 0) + r.n
    col.total += r.n
    totals.set(key, (totals.get(key) ?? 0) + r.n)
  }
  const classes = [...totals.entries()].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0])).map(([k]) => k)
  return { weeks: cols, classes }
}
