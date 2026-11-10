import { isValidOid, type Survey } from './filters'
import type { Detection } from './lightcurve'

// ALeRCE explorer links. The ZTF form is long-standing; the LSST form is the one
// reported working on the Rubin community forum (not documented officially), so
// re-check it if ALeRCE moves its Rubin explorer.
export function alerceUrl(survey: Survey, oid: string): string {
  const id = encodeURIComponent(oid)
  return survey === 'ztf'
    ? `https://alerce.online/object/${id}`
    : `https://alerce.online/object/?oid=${id}&survey=lsst`
}

export const STAMP_TYPES = ['science', 'template', 'difference'] as const
export type StampType = (typeof STAMP_TYPES)[number]

const CANDID_RE = /^\d{1,32}$/

export function isValidCandid(candid: unknown): candid is string {
  return typeof candid === 'string' && CANDID_RE.test(candid)
}

export function ztfStampUrl(oid: string, candid: string, type: StampType): string | null {
  if (!isValidOid('ztf', oid) || !isValidCandid(candid)) return null
  const params = new URLSearchParams({
    oid,
    candid,
    type,
    format: 'png',
  })
  return `https://avro.alerce.online/get_stamp?${params.toString()}`
}

export interface StampSet {
  candid: string
  mjd: number
  band: string | null
  stamps: { type: StampType; label: string; description: string; url: string }[]
}

const STAMP_META: Record<StampType, { label: string; description: string }> = {
  science: { label: 'Science', description: 'Single-exposure alert image at detection' },
  template: { label: 'Template', description: 'Reference sky image stacked from earlier nights' },
  difference: { label: 'Difference', description: 'Science minus template, isolating what changed' },
}

export function buildZtfStamps(oid: string, detections: Detection[]): StampSet | null {
  if (!isValidOid('ztf', oid)) return null
  const eligible = detections.filter(
    (d): d is Detection & { candid: string } =>
      isValidCandid(d.candid) && d.hasStamp !== false && Number.isFinite(d.mjd),
  )
  if (eligible.length === 0) return null
  const confirmed = eligible.filter((d) => d.hasStamp === true)
  const pool = confirmed.length > 0 ? confirmed : eligible
  const chosen = pool.reduce((best, cur) => (cur.mjd >= best.mjd ? cur : best))
  return {
    candid: chosen.candid,
    mjd: chosen.mjd,
    band: chosen.band,
    stamps: STAMP_TYPES.map((type) => ({
      type,
      label: STAMP_META[type].label,
      description: STAMP_META[type].description,
      url: ztfStampUrl(oid, chosen.candid, type)!,
    })),
  }
}
