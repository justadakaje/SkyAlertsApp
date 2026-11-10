// Turn stored detections into a plot-ready light-curve model.
//
// ZTF reports difference magnitudes (smaller = brighter, so the axis is inverted).
// LSST reports difference flux in nJy, which can be negative when the source is
// fainter than in the reference image; it is plotted as flux in µJy with zero shown.

import { padDomain, type Domain } from './chart'
import type { Survey } from './filters'

export interface Detection {
  mjd: number
  band: string | null
  mag: number | null
  magErr: number | null
  fluxNjy: number | null
  fluxErrNjy: number | null
  /** ZTF: an uncorrected negative difference, which has no plottable magnitude. */
  negative: boolean
  /** ZTF candidate id (`candid`), when present. */
  candid?: string | null
  /** Whether ALeRCE reports an image cutout for this detection (`null` when unknown). */
  hasStamp?: boolean | null
}

export interface CurvePoint {
  mjd: number
  y: number
  err: number | null
  band: string
}

export interface CurveModel {
  kind: 'mag' | 'flux'
  yLabel: string
  invertY: boolean
  bands: string[]
  points: CurvePoint[]
  xDomain: Domain
  yDomain: Domain
  /** Overlay when every band has a validated colour slot; otherwise one panel per band. */
  layout: 'overlay' | 'panels'
  /** Negative-difference detections left off a magnitude plot. */
  skippedNegative: number
}

export const BAND_ORDER = ['u', 'g', 'r', 'i', 'z', 'y']
// The three overlay colours pass the all-pairs colour-blindness checks; more bands get panels.
export const OVERLAY_BANDS = ['g', 'r', 'i']
const MAX_ERR = 5 // mag, or 5x the value for flux; anything larger is noise, not an error bar

function finite(v: number | null): v is number {
  return v !== null && Number.isFinite(v)
}

export function buildCurve(survey: Survey, detections: Detection[]): CurveModel | null {
  const kind = survey === 'ztf' ? 'mag' : 'flux'
  const points: CurvePoint[] = []
  let skippedNegative = 0
  for (const d of detections) {
    if (!Number.isFinite(d.mjd)) continue
    const band = d.band ?? '?'
    if (kind === 'mag') {
      if (d.negative) {
        skippedNegative++
        continue
      }
      if (!finite(d.mag)) continue
      const err = finite(d.magErr) && d.magErr >= 0 && d.magErr <= MAX_ERR ? d.magErr : null
      points.push({ mjd: d.mjd, y: d.mag, err, band })
    } else {
      if (!finite(d.fluxNjy)) continue
      const y = d.fluxNjy / 1000
      const e = finite(d.fluxErrNjy) ? Math.abs(d.fluxErrNjy) / 1000 : null
      points.push({ mjd: d.mjd, y, err: e !== null && e <= Math.max(Math.abs(y) * MAX_ERR, 1) ? e : null, band })
    }
  }
  if (points.length === 0) return null
  points.sort((a, b) => a.mjd - b.mjd)

  const bands = [...new Set(points.map((p) => p.band))].sort(
    (a, b) => rank(a) - rank(b) || a.localeCompare(b),
  )
  const xs = points.map((p) => p.mjd)
  const lows = points.map((p) => p.y - (p.err ?? 0))
  const highs = points.map((p) => p.y + (p.err ?? 0))
  let yMin = Math.min(...lows)
  let yMax = Math.max(...highs)
  if (kind === 'flux') {
    yMin = Math.min(yMin, 0)
    yMax = Math.max(yMax, 0)
  }
  const xSpan = Math.max(...xs) - Math.min(...xs)
  return {
    kind,
    yLabel: kind === 'mag' ? 'Magnitude (brighter ↑)' : 'Difference flux (µJy)',
    invertY: kind === 'mag',
    bands,
    points,
    xDomain: padDomain(Math.min(...xs), Math.max(...xs), 0.03, Math.max(0.5, xSpan * 0.03)),
    yDomain: padDomain(yMin, yMax, 0.08, kind === 'mag' ? 0.2 : 0.5),
    layout: bands.every((b) => OVERLAY_BANDS.includes(b)) ? 'overlay' : 'panels',
    skippedNegative,
  }
}

function rank(band: string): number {
  const i = BAND_ORDER.indexOf(band)
  return i === -1 ? BAND_ORDER.length : i
}
