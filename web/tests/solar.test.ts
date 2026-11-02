import { describe, expect, it, vi } from 'vitest'

import {
  CONSTELLATIONS,
  formatPeriod,
  formatRotation,
  HORIZONS_GIVE_UP_AFTER,
  horizonsUrl,
  jplUrl,
  loadEphemerides,
  orbitviewerUrl,
  parseHorizons,
  SOLAR_BODIES,
  viewingHint,
} from '@/lib/solar'

// Trimmed from a real Horizons response for Eris (2026-11-02).
const ERIS = `*******
 Date__(UT)__HR:MN, , , R.A._(ICRF), DEC_(ICRF),    APmag,  S-brt,             delta,     deldot,     S-O-T,/r,  Cnst,
*******
$$SOE
 2026-Nov-02 00:00, , ,    26.87320,   -0.14669,   18.569,   n.a.,  94.5041383499479,  7.2762718,  162.3178,/T,   Cet,
 2026-Nov-03 00:00, , ,    26.86393,   -0.14913,   18.570,   n.a.,  94.5084852994633,  7.7765713,  161.5000,/T,   Cet,
$$EOE
*******`

describe('parseHorizons', () => {
  it('reads the first row', () => {
    expect(parseHorizons(ERIS)).toEqual({
      ra: 26.8732,
      dec: -0.14669,
      mag: 18.569,
      distanceAu: 94.5041383499479,
      elongation: 162.3178,
      constellation: 'Cet',
    })
  })

  it('returns null for errors and malformed rows', () => {
    expect(parseHorizons('No matches found.')).toBeNull()
    expect(parseHorizons('$$SOE\n$$EOE')).toBeNull()
    expect(parseHorizons(ERIS.replace('26.87320', '400.0'))).toBeNull()
    expect(parseHorizons(ERIS.replace('Cet,\n 2026-Nov-03', '<b>,\n 2026-Nov-03'))).toBeNull()
  })

  it('accepts a missing magnitude', () => {
    expect(parseHorizons(ERIS.replace('18.569', 'n.a.'))?.mag).toBeNull()
  })
})

describe('loadEphemerides', () => {
  const eph = parseHorizons(ERIS)

  it('gives up early when JPL looks down, and throws so nothing is cached', async () => {
    const lookup = vi.fn(async () => {
      throw new Error('timeout')
    })
    await expect(loadEphemerides(lookup)).rejects.toThrow('Horizons unavailable')
    expect(lookup).toHaveBeenCalledTimes(HORIZONS_GIVE_UP_AFTER)
  })

  it('counts null results as failures too', async () => {
    const lookup = vi.fn(async () => null)
    await expect(loadEphemerides(lookup)).rejects.toThrow('Horizons unavailable')
    expect(lookup).toHaveBeenCalledTimes(HORIZONS_GIVE_UP_AFTER)
  })

  it('keeps going past failures once a lookup has succeeded', async () => {
    const failing = new Set(['pluto', 'eris', 'gonggong'])
    const lookup = vi.fn(async (b: (typeof SOLAR_BODIES)[number]) => {
      if (failing.has(b.id)) throw new Error('timeout')
      return eph
    })
    const out = await loadEphemerides(lookup)
    expect(lookup).toHaveBeenCalledTimes(SOLAR_BODIES.length)
    for (const b of SOLAR_BODIES) expect(out[b.id]).toEqual(failing.has(b.id) ? null : eph)
  })

  it('recovers when only the first lookup fails', async () => {
    const lookup = vi.fn(async (b: (typeof SOLAR_BODIES)[number]) => (b.id === 'ceres' ? null : eph))
    const out = await loadEphemerides(lookup)
    expect(lookup).toHaveBeenCalledTimes(SOLAR_BODIES.length)
    expect(out.ceres).toBeNull()
    expect(out.pluto).toEqual(eph)
  })
})

describe('roster', () => {
  it('has unique ids and numbers, five dwarf planets, and known constellations', () => {
    expect(new Set(SOLAR_BODIES.map((b) => b.id)).size).toBe(SOLAR_BODIES.length)
    expect(new Set(SOLAR_BODIES.map((b) => b.number)).size).toBe(SOLAR_BODIES.length)
    expect(SOLAR_BODIES.filter((b) => b.status === 'dwarf').map((b) => b.name)).toEqual([
      'Ceres',
      'Pluto',
      'Eris',
      'Haumea',
      'Makemake',
    ])
    expect(CONSTELLATIONS.Cet).toBe('Cetus')
    expect(Object.keys(CONSTELLATIONS)).toHaveLength(88)
  })

  it('builds links', () => {
    const pluto = SOLAR_BODIES.find((b) => b.id === 'pluto')!
    const quaoar = SOLAR_BODIES.find((b) => b.id === 'quaoar')!
    expect(orbitviewerUrl(pluto)).toBe('https://orbitviewer.app/en/solar-items/pluto/')
    expect(orbitviewerUrl(quaoar)).toBeNull()
    expect(jplUrl(quaoar)).toBe('https://ssd.jpl.nasa.gov/tools/sbdb_lookup.html#/?sstr=50000')
  })

  it('builds a one-day Horizons query', () => {
    const u = new URL(horizonsUrl(136199, '2026-12-31'))
    expect(u.searchParams.get('COMMAND')).toBe("'136199;'")
    expect(u.searchParams.get('START_TIME')).toBe("'2026-12-31'")
    expect(u.searchParams.get('STOP_TIME')).toBe("'2027-01-01'")
  })
})

describe('formatting', () => {
  it('formats periods and rotation', () => {
    expect(formatPeriod(1680)).toBe('4.6 years')
    expect(formatPeriod(91000)).toBe('249 years')
    expect(formatPeriod(4630000)).toBe('12,700 years')
    expect(formatRotation(9.07417)).toBe('9.1 hours')
    expect(formatRotation(153.2935)).toBe('6.4 days')
  })

  it('gives viewing hints', () => {
    const e = { ra: 0, dec: 0, distanceAu: 1, elongation: 90, constellation: 'Cet' }
    expect(viewingHint({ ...e, mag: 8.2 })).toBe('Binoculars')
    expect(viewingHint({ ...e, mag: 14.4 })).toBe('Large amateur telescope')
    expect(viewingHint({ ...e, mag: 18.6 })).toBe('Research telescopes and long exposures')
    expect(viewingHint({ ...e, mag: 8.2, elongation: 12 })).toBe('Too close to the Sun to observe')
  })
})
