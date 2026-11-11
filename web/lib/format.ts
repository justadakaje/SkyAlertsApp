// Display formatting. Everything renders in UTC so server output is deterministic.

import { mjdToDate } from './astro'
import { ARTIFACT_CLASS, classInfo, groupOf } from './classes'
import type { Survey } from './filters'
import type { EventRow, MatchedAsteroidRow } from './queries'
import { formatSsoLabel } from './solar'

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

export function formatUtc(date: Date): string {
  const iso = date.toISOString()
  return `${iso.slice(0, 10)} ${iso.slice(11, 16)} UTC`
}

export function formatDay(date: Date): string {
  return `${MONTHS[date.getUTCMonth()]} ${date.getUTCDate()}`
}

export function formatMonth(date: Date): string {
  return `${MONTHS[date.getUTCMonth()]} ${date.getUTCFullYear()}`
}

export function formatAgo(date: Date, now: Date): string {
  const minutes = Math.round((now.getTime() - date.getTime()) / 60_000)
  if (minutes < 1) return 'just now'
  if (minutes < 60) return `${minutes} min ago`
  const hours = Math.round(minutes / 60)
  if (hours < 48) return `${hours} h ago`
  const days = Math.round(hours / 24)
  if (days < 60) return `${days} days ago`
  const months = Math.round(days / 30.4)
  if (months < 24) return `${months} months ago`
  return `${Math.round(days / 365.25)} years ago`
}

export function formatProbability(p: number | null): string {
  if (p === null) return '—'
  if (p > 0 && p < 0.01) return '<1%'
  return `${Math.round(p * 100)}%`
}

export function formatCount(n: number): string {
  if (n < 1000) return String(n)
  if (n < 10_000) return `${(n / 1000).toFixed(1).replace(/\.0$/, '')}K`
  if (n < 1_000_000) return `${Math.round(n / 1000)}K`
  return `${(n / 1_000_000).toFixed(1).replace(/\.0$/, '')}M`
}

/**
 * Convert an apparent/difference magnitude or positive difference flux (nJy) into
 * a plain-English brightness comparison relative to naked eye, binoculars, and Pluto (~14.4).
 */
export function humanBrightness(mag: number | null, fluxNjy?: number | null): string | null {
  let effMag: number | null = null
  if (mag !== null && Number.isFinite(mag)) {
    effMag = mag
  } else if (fluxNjy !== null && fluxNjy !== undefined && Number.isFinite(fluxNjy) && fluxNjy > 0) {
    effMag = -2.5 * Math.log10(fluxNjy) + 31.4
  }
  if (effMag === null) return null

  const label = `mag ${effMag.toFixed(1)}`
  if (effMag <= 6.5) return `${label} · Naked-eye range under dark skies`
  if (effMag <= 10.0) return `${label} · Binocular range`
  if (effMag <= 14.4) return `${label} · Backyard telescope range (brighter than Pluto)`
  if (effMag <= 18.0) return `${label} · Amateur CCD telescope range`
  return `${label} · Deep-sky survey camera range (fainter than Pluto)`
}

export interface ObjectShareInput {
  survey: Survey
  topClass: string | null
  probability: number | null
  firstmjd: number | null
}

/** Concise share/meta summary, e.g. "Supernova · 85% confidence · Rubin (LSST) · first seen 2026-10-31". */
export function formatObjectDescription(o: ObjectShareInput): string {
  const parts = [classInfo(o.topClass).label]
  if (o.probability !== null && Number.isFinite(o.probability)) {
    parts.push(`${formatProbability(o.probability)} confidence`)
  }
  parts.push(o.survey === 'lsst' ? 'Rubin (LSST)' : 'ZTF')
  if (o.firstmjd !== null && Number.isFinite(o.firstmjd)) {
    parts.push(`first seen ${mjdToDate(o.firstmjd).toISOString().slice(0, 10)}`)
  }
  return parts.join(' · ')
}

export interface HomeHighlight {
  kind: 'transient' | 'solar' | 'active'
  eyebrow: string
  survey: Survey
  oid: string
  topClass: string | null
  probability: number | null
  ndet: number | null
  ra: number | null
  dec: number | null
  ssoLabel: string | null
}

/**
 * Pick up to 3 story highlight cards from a window's event list (and optional matched asteroids):
 * 1. Top explosion / outburst (highest-confidence transient)
 * 2. Solar System catch (preferring a named SkyBoT match)
 * 3. Most active object (highest detection count, excluding artifacts and already-picked cards)
 */
export function pickHomeHighlights(
  rows: EventRow[],
  matchedAsteroids: MatchedAsteroidRow[] = [],
): HomeHighlight[] {
  const picked = new Set<string>()
  const out: HomeHighlight[] = []

  const transients = rows
    .filter((r) => groupOf(r.topClass) === 'transient')
    .sort((a, b) => (b.probability ?? 0) - (a.probability ?? 0) || (b.lastmjd ?? 0) - (a.lastmjd ?? 0))
  const topTransient = transients[0]
  if (topTransient) {
    picked.add(`${topTransient.survey}:${topTransient.oid}`)
    out.push({
      kind: 'transient',
      eyebrow: 'Top explosion / outburst',
      survey: topTransient.survey,
      oid: topTransient.oid,
      topClass: topTransient.topClass,
      probability: topTransient.probability,
      ndet: topTransient.ndet,
      ra: topTransient.ra,
      dec: topTransient.dec,
      ssoLabel: null,
    })
  }

  const rowAsteroids = rows
    .filter((r) => r.topClass === 'asteroid' && !picked.has(`${r.survey}:${r.oid}`))
    .sort(
      (a, b) =>
        Number(Boolean(b.ssoName)) - Number(Boolean(a.ssoName)) ||
        (b.probability ?? 0) - (a.probability ?? 0),
    )
  const topRowAst = rowAsteroids[0]
  const fallbackMatched = matchedAsteroids.find((m) => !picked.has(`${m.survey}:${m.oid}`))
  if (topRowAst && (topRowAst.ssoName || !fallbackMatched)) {
    picked.add(`${topRowAst.survey}:${topRowAst.oid}`)
    out.push({
      kind: 'solar',
      eyebrow: 'Solar System catch',
      survey: topRowAst.survey,
      oid: topRowAst.oid,
      topClass: 'asteroid',
      probability: topRowAst.probability,
      ndet: topRowAst.ndet,
      ra: topRowAst.ra,
      dec: topRowAst.dec,
      ssoLabel: topRowAst.ssoName ? formatSsoLabel(topRowAst.ssoNumber ?? null, topRowAst.ssoName) : null,
    })
  } else if (fallbackMatched) {
    picked.add(`${fallbackMatched.survey}:${fallbackMatched.oid}`)
    out.push({
      kind: 'solar',
      eyebrow: 'Solar System catch',
      survey: fallbackMatched.survey,
      oid: fallbackMatched.oid,
      topClass: 'asteroid',
      probability: null,
      ndet: null,
      ra: null,
      dec: null,
      ssoLabel: formatSsoLabel(fallbackMatched.ssoNumber, fallbackMatched.ssoName),
    })
  }

  const active = rows
    .filter((r) => r.topClass !== ARTIFACT_CLASS && !picked.has(`${r.survey}:${r.oid}`) && (r.ndet ?? 0) >= 2)
    .sort((a, b) => (b.ndet ?? 0) - (a.ndet ?? 0) || (b.probability ?? 0) - (a.probability ?? 0))[0]
  if (active) {
    picked.add(`${active.survey}:${active.oid}`)
    out.push({
      kind: 'active',
      eyebrow: 'Most active light curve',
      survey: active.survey,
      oid: active.oid,
      topClass: active.topClass,
      probability: active.probability,
      ndet: active.ndet,
      ra: active.ra,
      dec: active.dec,
      ssoLabel: active.ssoName ? formatSsoLabel(active.ssoNumber ?? null, active.ssoName) : null,
    })
  }

  return out
}
