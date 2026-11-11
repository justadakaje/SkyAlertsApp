import { describe, expect, it } from 'vitest'

import {
  dateToMjd,
  formatDec,
  formatRa,
  galacticLatitude,
  galacticToEquatorial,
  mjdToDate,
  skyRegion,
} from '@/lib/astro'

describe('time', () => {
  it('maps MJD 40587 to the Unix epoch and round-trips', () => {
    expect(mjdToDate(40587).toISOString()).toBe('1970-01-01T00:00:00.000Z')
    const d = new Date('2026-11-01T12:00:00Z')
    expect(dateToMjd(d)).toBeCloseTo(61345.5, 9)
    expect(mjdToDate(dateToMjd(d)).getTime()).toBe(d.getTime())
  })
})

describe('coordinates', () => {
  it('formats the Crab Nebula', () => {
    expect(formatRa(83.63308)).toBe('05:34:31.94')
    expect(formatDec(22.0145)).toBe('+22:00:52.2')
  })

  it('wraps and carries at the edges', () => {
    expect(formatRa(0)).toBe('00:00:00.00')
    expect(formatRa(359.9999999)).toBe('00:00:00.00')
    expect(formatRa(360)).toBe('00:00:00.00')
    expect(formatDec(-0.5)).toBe('-00:30:00.0')
    expect(formatDec(-89.99999999)).toBe('-90:00:00.0')
  })

  it('puts the galactic centre and pole in the right place', () => {
    const gc = galacticToEquatorial(0, 0)
    expect(gc.ra).toBeCloseTo(266.405, 2)
    expect(gc.dec).toBeCloseTo(-28.936, 2)
    const ngp = galacticToEquatorial(123, 90)
    expect(ngp.dec).toBeCloseTo(27.128, 2)
    expect(galacticLatitude(ngp.ra, ngp.dec)).toBeCloseTo(90, 1)
    expect(galacticLatitude(gc.ra, gc.dec)).toBeCloseTo(0, 1)
  })

  it('summarises hemisphere, ~40°N visibility, and galactic plane proximity', () => {
    const gc = galacticToEquatorial(0, 0)
    expect(skyRegion(gc.ra, gc.dec)).toContain('Southern sky')
    expect(skyRegion(gc.ra, gc.dec)).toContain('below ~40°N horizon')
    expect(skyRegion(gc.ra, gc.dec)).toContain('near Milky Way plane')

    const ngp = galacticToEquatorial(123, 90)
    expect(skyRegion(ngp.ra, ngp.dec)).toContain('Northern sky')
    expect(skyRegion(ngp.ra, ngp.dec)).toContain('reaches above the ~40°N horizon')
    expect(skyRegion(ngp.ra, ngp.dec)).toContain('away from galactic plane')
  })
})
