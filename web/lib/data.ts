import 'server-only'

import { unstable_cache } from 'next/cache'

import { dateToMjd } from './astro'
import { getPool } from './db'
import { WINDOWS, type HomeFilters, type Survey } from './filters'
import * as q from './queries'
import { type Ephemeris, horizonsUrl, loadEphemerides, parseHorizons } from './solar'

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
    const [classifications, detections, sso] = await Promise.all([
      q.getClassifications(pool, survey, oid),
      q.getDetections(pool, survey, oid),
      q.getSsoIdentification(pool, survey, oid),
    ])
    return { object, classifications, detections, sso }
  },
  ['object-page-v2'],
  opts,
)

export const getMatchedAsteroids = unstable_cache(
  async (limit = 25) => q.listMatchedAsteroids(getPool(), limit),
  ['matched-asteroids-v1'],
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
    const [daily, surveyDaily, comparison] = await Promise.all([
      q.dailyCounts(pool, todayMjd - 90),
      q.dailySurveyCounts(pool, todayMjd - 90),
      q.weekComparison(pool, now - 7, now - 14),
    ])
    return { daily, surveyDaily, comparison, todayMjd }
  },
  ['trends-v2'],
  opts,
)

export const getLastUpdated = unstable_cache(async () => q.lastUpdated(getPool()), ['last-updated-v1'], opts)

// Today's positions for the Solar System roster from JPL Horizons. Positions of these
// distant bodies barely move in a day, so one fetch per UTC day (cached 6 h) is plenty.
// A body whose lookup fails is null. If JPL looks down (the first two lookups fail, at
// most 2 × 8 s) the call throws, so the failure is not cached and the next view retries.
export const getSolarEphemerides = unstable_cache(
  async (day: string): Promise<Record<string, Ephemeris | null>> =>
    loadEphemerides(async (b) => {
      const res = await fetch(horizonsUrl(b.number, day), {
        headers: { 'User-Agent': 'skyalerts-web (+https://github.com/justadakaje/SkyAlertsApp)' },
        signal: AbortSignal.timeout(8000),
        cache: 'no-store',
      })
      if (!res.ok) return null
      const body = (await res.json()) as { result?: unknown }
      return typeof body.result === 'string' ? parseHorizons(body.result) : null
    }),
  ['solar-ephemerides-v1'],
  { revalidate: 6 * 3600, tags: ['solar'] },
)
