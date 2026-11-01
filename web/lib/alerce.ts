import type { Survey } from './filters'

// ALeRCE explorer links. The ZTF form is long-standing; the LSST form is the one
// reported working on the Rubin community forum (not documented officially), so
// re-check it if ALeRCE moves its Rubin explorer.
export function alerceUrl(survey: Survey, oid: string): string {
  const id = encodeURIComponent(oid)
  return survey === 'ztf'
    ? `https://alerce.online/object/${id}`
    : `https://alerce.online/object/?oid=${id}&survey=lsst`
}
