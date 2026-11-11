import { describe, expect, it } from 'vitest'

import { dateToMjd } from '@/lib/astro'
import { classesByGroup, GROUPS } from '@/lib/classes'
import {
  formatAgo,
  formatCount,
  formatDay,
  formatObjectDescription,
  formatProbability,
  formatUtc,
  humanBrightness,
  pickHomeHighlights,
} from '@/lib/format'

const now = new Date('2026-11-01T12:00:00Z')

describe('format', () => {
  it('renders UTC timestamps and days', () => {
    expect(formatUtc(new Date('2026-06-27T10:02:59Z'))).toBe('2026-06-27 10:02 UTC')
    expect(formatDay(new Date('2026-06-27T23:59:00Z'))).toBe('Jun 27')
  })

  it('describes elapsed time', () => {
    expect(formatAgo(new Date('2026-11-01T11:59:40Z'), now)).toBe('just now')
    expect(formatAgo(new Date('2026-11-01T11:15:00Z'), now)).toBe('45 min ago')
    expect(formatAgo(new Date('2026-10-31T12:00:00Z'), now)).toBe('24 h ago')
    expect(formatAgo(new Date('2026-10-20T12:00:00Z'), now)).toBe('12 days ago')
    expect(formatAgo(new Date('2018-12-15T12:00:00Z'), now)).toBe('8 years ago')
  })

  it('formats probabilities and counts', () => {
    expect(formatProbability(null)).toBe('—')
    expect(formatProbability(0.004)).toBe('<1%')
    expect(formatProbability(0.8547)).toBe('85%')
    expect(formatCount(999)).toBe('999')
    expect(formatCount(1284)).toBe('1.3K')
    expect(formatCount(12_900)).toBe('13K')
    expect(formatCount(4_200_000)).toBe('4.2M')
  })

  it('builds per-object share descriptions with fallbacks for missing fields', () => {
    const firstmjd = dateToMjd(new Date('2026-10-31T06:00:00Z'))
    expect(
      formatObjectDescription({
        survey: 'lsst',
        topClass: 'SN',
        probability: 0.85,
        firstmjd,
      }),
    ).toBe('Supernova · 85% confidence · Rubin (LSST) · first seen 2026-10-31')

    expect(
      formatObjectDescription({
        survey: 'ztf',
        topClass: null,
        probability: null,
        firstmjd: null,
      }),
    ).toBe('Unclassified · ZTF')
  })

  it('groups known classes by display group without duplicating labels', () => {
    for (const g of GROUPS) {
      const items = classesByGroup(g.id)
      expect(items.length).toBeGreaterThan(0)
      const labels = items.map((c) => c.label)
      expect(new Set(labels).size).toBe(labels.length)
    }
  })

  it('translates apparent/difference magnitudes and LSST flux into human brightness scale', () => {
    expect(humanBrightness(5.8)).toContain('Naked-eye range')
    expect(humanBrightness(9.2)).toContain('Binocular range')
    expect(humanBrightness(13.9)).toContain('brighter than Pluto')
    expect(humanBrightness(16.4)).toContain('Amateur CCD telescope range')
    expect(humanBrightness(19.5)).toContain('Deep-sky survey camera range')
    // LSST positive flux 1_000_000 nJy -> AB mag 16.4
    expect(humanBrightness(null, 1_000_000)).toContain('mag 16.4')
    expect(humanBrightness(null, -500)).toBeNull()
    expect(humanBrightness(null, null)).toBeNull()
  })

  it('picks distinct home highlight cards for transient, solar system, and most active', () => {
    const cards = pickHomeHighlights(
      [
        {
          survey: 'ztf',
          oid: 'ZTF26sn1',
          topClass: 'SNIa',
          probability: 0.96,
          classifier: 'lc_classifier',
          firstmjd: 61340,
          lastmjd: 61344,
          ndet: 5,
          ra: 120,
          dec: 30,
        },
        {
          survey: 'lsst',
          oid: '313708285401235521',
          topClass: 'RRL',
          probability: 0.91,
          classifier: 'stamp',
          firstmjd: 61339,
          lastmjd: 61344,
          ndet: 24,
          ra: 45,
          dec: -35,
        },
      ],
      [
        {
          survey: 'ztf',
          oid: 'ZTF26nolan',
          obsMjd: 61342,
          ssoNumber: 9537,
          ssoName: 'Nolan',
          ssoClass: 'MB>Middle',
          predictedMag: 18.6,
          sepArcsec: 3.1,
          geoDistAu: 2.98,
          helioDistAu: 2.31,
        },
      ],
    )
    expect(cards.map((c) => [c.kind, c.oid, c.ssoLabel])).toEqual([
      ['transient', 'ZTF26sn1', null],
      ['solar', 'ZTF26nolan', '(9537) Nolan'],
      ['active', '313708285401235521', null],
    ])
  })
})
