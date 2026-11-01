import { describe, expect, it } from 'vitest'

import { DEFAULT_FILTERS, homeHref, isValidOid, parseHomeFilters } from '@/lib/filters'

describe('parseHomeFilters', () => {
  it('returns defaults for an empty query', () => {
    expect(parseHomeFilters({})).toEqual(DEFAULT_FILTERS)
  })

  it('accepts valid values', () => {
    expect(
      parseHomeFilters({ survey: 'ztf', class: 'CV/Nova', window: '30d', sort: 'newest', artifacts: '1', page: '3' }),
    ).toEqual({ survey: 'ztf', cls: 'CV/Nova', window: '30d', sort: 'newest', artifacts: true, page: 3 })
  })

  it('falls back on anything unexpected', () => {
    const f = parseHomeFilters({
      survey: 'hst',
      class: "SN'; DROP TABLE objects;--",
      window: '365d',
      sort: 'random',
      artifacts: 'yes',
      page: '-4',
    })
    expect(f).toEqual(DEFAULT_FILTERS)
  })

  it('uses the first of repeated params and clamps the page', () => {
    expect(parseHomeFilters({ survey: ['lsst', 'ztf'], page: '99999' })).toMatchObject({ survey: 'lsst', page: 200 })
  })
})

describe('homeHref', () => {
  it('omits defaults and resets the page', () => {
    expect(homeHref(DEFAULT_FILTERS)).toBe('/')
    const f = { ...DEFAULT_FILTERS, page: 4, survey: 'lsst' as const }
    expect(homeHref(f, { cls: 'SN' })).toBe('/?survey=lsst&class=SN')
    expect(homeHref(f, { page: 5 })).toBe('/?survey=lsst&page=5')
  })

  it('encodes class names', () => {
    expect(homeHref(DEFAULT_FILTERS, { cls: 'CV/Nova' })).toBe('/?class=CV%2FNova')
  })
})

describe('isValidOid', () => {
  it('matches each survey id format', () => {
    expect(isValidOid('ztf', 'ZTF18acwycia')).toBe(true)
    expect(isValidOid('lsst', '313708285401235521')).toBe(true)
    expect(isValidOid('ztf', '313708285401235521')).toBe(false)
    expect(isValidOid('lsst', 'ZTF18acwycia')).toBe(false)
    expect(isValidOid('lsst', '1 OR 1=1')).toBe(false)
    expect(isValidOid('ztf', 'ZTF18acwycia/../x')).toBe(false)
  })
})
