import { describe, expect, it } from 'vitest'

import { buildCurve, type Detection } from '@/lib/lightcurve'

const det = (o: Partial<Detection>): Detection => ({
  mjd: 61000,
  band: 'g',
  mag: null,
  magErr: null,
  fluxNjy: null,
  fluxErrNjy: null,
  negative: false,
  ...o,
})

describe('buildCurve (ZTF magnitudes)', () => {
  const model = buildCurve('ztf', [
    det({ mjd: 61002, band: 'r', mag: 18.4, magErr: 0.05 }),
    det({ mjd: 61001, band: 'g', mag: 18.9, magErr: 0.07 }),
    det({ mjd: 61003, band: 'g', mag: 19.1, magErr: 12 }), // absurd error dropped, point kept
    det({ mjd: 61004, band: 'g', mag: null }), // no magnitude: skipped
    det({ mjd: Number.NaN, band: 'g', mag: 18 }),
  ])!

  it('plots magnitude with the axis inverted', () => {
    expect(model.kind).toBe('mag')
    expect(model.invertY).toBe(true)
    expect(model.points.map((p) => p.mjd)).toEqual([61001, 61002, 61003])
    expect(model.points[2]!.err).toBeNull()
  })

  it('orders bands and overlays g/r', () => {
    expect(model.bands).toEqual(['g', 'r'])
    expect(model.layout).toBe('overlay')
  })

  it('pads the domains around the data', () => {
    expect(model.xDomain[0]).toBeLessThan(61001)
    expect(model.xDomain[1]).toBeGreaterThan(61003)
    expect(model.yDomain[0]).toBeLessThan(18.35)
    expect(model.yDomain[1]).toBeGreaterThan(19.1)
  })
})

describe('buildCurve (LSST flux)', () => {
  const model = buildCurve('lsst', [
    det({ mjd: 61219.4, band: 'i', fluxNjy: 26841.4, fluxErrNjy: 623.7 }),
    det({ mjd: 61220.4, band: 'u', fluxNjy: -1200, fluxErrNjy: 300 }),
    det({ mjd: 61221.4, band: 'z', fluxNjy: 5000, fluxErrNjy: -100 }),
  ])!

  it('plots difference flux in µJy, keeping negative points', () => {
    expect(model.kind).toBe('flux')
    expect(model.invertY).toBe(false)
    expect(model.points.map((p) => p.y)).toEqual([26.8414, -1.2, 5])
    expect(model.points[2]!.err).toBe(0.1)
  })

  it('always shows zero and uses panels beyond g/r/i', () => {
    expect(model.yDomain[0]).toBeLessThan(-1.2)
    expect(model.yDomain[1]).toBeGreaterThan(26.84)
    expect(model.bands).toEqual(['u', 'i', 'z'])
    expect(model.layout).toBe('panels')
  })
})

describe('buildCurve negative differences', () => {
  it('leaves uncorrected negative ZTF differences off the magnitude plot and counts them', () => {
    const m = buildCurve('ztf', [
      det({ mjd: 61001, mag: 17.5, negative: true }),
      det({ mjd: 61002, mag: 16.4 }),
    ])!
    expect(m.points.map((p) => p.mjd)).toEqual([61002])
    expect(m.skippedNegative).toBe(1)
  })

  it('keeps negative LSST flux, which is a real measurement', () => {
    const m = buildCurve('lsst', [det({ fluxNjy: -500, negative: true })])!
    expect(m.points).toHaveLength(1)
    expect(m.skippedNegative).toBe(0)
  })
})

describe('buildCurve edge cases', () => {
  it('returns null when nothing is plottable', () => {
    expect(buildCurve('ztf', [])).toBeNull()
    expect(buildCurve('lsst', [det({ fluxNjy: null })])).toBeNull()
  })

  it('handles a single point', () => {
    const m = buildCurve('ztf', [det({ mag: 17 })])!
    expect(m.xDomain[1] - m.xDomain[0]).toBeGreaterThan(0)
    expect(m.yDomain[1] - m.yDomain[0]).toBeGreaterThan(0)
  })
})
