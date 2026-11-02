import 'server-only'

import { unstable_cache } from 'next/cache'

import { dateToMjd } from './astro'
import { getPool } from './db'
import { WINDOWS, type HomeFilters, type Survey } from './filters'
import * as q from './queries'

// Ingest runs once a day, so query results are cached for 10 minutes. Windows
// are computed from a 10-minute time bucket so the cache key is stable within it.
const REVALIDATE_S = 600
const opts = { revalidate: REVALIDATE_S, tags: ['skyalerts-data'] }

export function timeBucket(now = Date.now()): number {
  return Math.floor(now / (REVALIDATE_S * 1000))
}

function bucketMjd(bucket: number): number {
  return dateToMjd(new Date(bucket * REVALIDATE_S * 1000))
}

export const getEvents = unstable_cache(
  async (f: HomeFilters, bucket: number) =>
    q.listEvents(getPool(), f, bucketMjd(bucket) - WINDOWS[f.window]),
  ['events-v1'],
  opts,
)

export const getClassCounts = unstable_cache(
  async (survey: Survey | null, window: HomeFilters['window'], bucket: number) =>
    q.classCounts(getPool(), survey, bucketMjd(bucket) - WINDOWS[window]),
  ['class-counts-v1'],
  opts,
)

export const getObjectPage = unstable_cache(
  async (survey: Survey, oid: string) => {
    const pool = getPool()
    const object = await q.getObject(pool, survey, oid)
    if (!object) return null
    const [classifications, detections] = await Promise.all([
      q.getClassifications(pool, survey, oid),
      q.getDetections(pool, survey, oid),
    ])
    return { object, classifications, detections }
  },
  ['object-page-v1'],
  opts,
)

export const getStats = unstable_cache(
  async (bucket: number) => {
    const pool = getPool()
    const now = bucketMjd(bucket)
    const [daily, totals] = await Promise.all([
      q.dailyCounts(pool, Math.floor(now) - 84),
      q.totals(pool, now - 7),
    ])
    return { daily, totals, todayMjd: Math.floor(now) }
  },
  ['stats-v1'],
  opts,
)

export const getTrends = unstable_cache(
  async (bucket: number) => {
    const pool = getPool()
    const now = bucketMjd(bucket)
    const todayMjd = Math.floor(now)
    const [daily, comparison] = await Promise.all([
      q.dailyCounts(pool, todayMjd - 90),
      q.weekComparison(pool, now - 7, now - 14),
    ])
    return { daily, comparison, todayMjd }
  },
  ['trends-v1'],
  opts,
)

export const getLastUpdated = unstable_cache(async () => q.lastUpdated(getPool()), ['last-updated-v1'], opts)
