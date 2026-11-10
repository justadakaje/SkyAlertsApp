import { describe, expect, it } from 'vitest'

import { alerceUrl, buildZtfStamps, isValidCandid, STAMP_TYPES, ztfStampUrl } from '@/lib/alerce'
import type { Detection } from '@/lib/lightcurve'

const baseDet: Detection = {
  mjd: 61340.0,
  band: 'r',
  mag: 17.5,
  magErr: 0.08,
  fluxNjy: null,
  fluxErrNjy: null,
  negative: false,
}

describe('alerceUrl', () => {
  it('builds explorer URLs for ZTF and LSST', () => {
    expect(alerceUrl('ztf', 'ZTF18acwycia')).toBe('https://alerce.online/object/ZTF18acwycia')
    expect(alerceUrl('lsst', '313708285401235521')).toBe(
      'https://alerce.online/object/?oid=313708285401235521&survey=lsst',
    )
  })
})

describe('ztfStampUrl', () => {
  it('validates candid and oid before building stamp URLs', () => {
    expect(isValidCandid('3588554120915010009')).toBe(true)
    expect(isValidCandid('')).toBe(false)
    expect(isValidCandid('12345&type=evil')).toBe(false)

    expect(ztfStampUrl('ZTF18acwycia', '3588554120915010009', 'science')).toBe(
      'https://avro.alerce.online/get_stamp?oid=ZTF18acwycia&candid=3588554120915010009&type=science&format=png',
    )
    expect(ztfStampUrl('313708285401235521', '3588554120915010009', 'science')).toBeNull()
    expect(ztfStampUrl('ZTF18acwycia', 'not-a-number', 'science')).toBeNull()
  })
})

describe('buildZtfStamps', () => {
  it('prefers the newest detection with hasStamp === true', () => {
    const detections: Detection[] = [
      { ...baseDet, mjd: 58468.5, candid: '714503484115010001', hasStamp: false },
      { ...baseDet, mjd: 61219.1, band: 'i', candid: '3465194524115015005', hasStamp: true },
      { ...baseDet, mjd: 61342.55, band: 'r', candid: '3588554120915010009', hasStamp: true },
      { ...baseDet, mjd: 61343.0, band: 'g', candid: '3589000000000000001', hasStamp: null },
    ]
    const set = buildZtfStamps('ZTF18acwycia', detections)
    expect(set).not.toBeNull()
    expect(set!.candid).toBe('3588554120915010009')
    expect(set!.mjd).toBe(61342.55)
    expect(set!.band).toBe('r')
    expect(set!.stamps.map((s) => s.type)).toEqual([...STAMP_TYPES])
    expect(set!.stamps[2]!.url).toContain('type=difference&format=png')
  })

  it('falls back to the newest valid detection when hasStamp is unknown (null)', () => {
    const detections: Detection[] = [
      { ...baseDet, mjd: 61200.0, candid: '3400000000000000001', hasStamp: null },
      { ...baseDet, mjd: 61300.0, band: 'g', candid: '3500000000000000002', hasStamp: null },
    ]
    const set = buildZtfStamps('ZTF18acwycia', detections)
    expect(set?.candid).toBe('3500000000000000002')
  })

  it('returns null when all detections have hasStamp === false or no valid candid', () => {
    expect(
      buildZtfStamps('ZTF18acwycia', [
        { ...baseDet, mjd: 58468.5, candid: '714503484115010001', hasStamp: false },
      ]),
    ).toBeNull()
    expect(buildZtfStamps('ZTF18acwycia', [{ ...baseDet, candid: null }])).toBeNull()
    expect(buildZtfStamps('313708285401235521', [{ ...baseDet, candid: '123', hasStamp: true }])).toBeNull()
  })
})
