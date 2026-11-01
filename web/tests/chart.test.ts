import { describe, expect, it } from 'vitest'

import { linear, niceTicks, padDomain, roundedTopBar } from '@/lib/chart'

describe('chart helpers', () => {
  it('maps linearly, including inverted ranges', () => {
    const s = linear([0, 10], [100, 0])
    expect(s(0)).toBe(100)
    expect(s(5)).toBe(50)
    expect(linear([3, 3], [0, 10])(3)).toBe(0)
  })

  it('picks round ticks', () => {
    expect(niceTicks(0, 31, 4)).toEqual([0, 10, 20, 30])
    expect(niceTicks(17.2, 19.4, 5)).toEqual([17.5, 18, 18.5, 19])
    expect(niceTicks(5, 5)).toEqual([5])
    expect(niceTicks(Number.NaN, 1)).toEqual([])
  })

  it('pads domains', () => {
    expect(padDomain(0, 100, 0.1, 1)).toEqual([-10, 110])
    expect(padDomain(5, 5, 0.1, 1)).toEqual([4, 6])
  })

  it('draws a bar with a square base and clamped radius', () => {
    expect(roundedTopBar(0, 10, 20, 30)).toBe('M0,40 V14 Q0,10 4,10 H16 Q20,10 20,14 V40 Z')
    expect(roundedTopBar(0, 0, 20, 2)).toContain('V2')
  })
})
