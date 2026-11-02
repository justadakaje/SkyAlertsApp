import { describe, expect, it } from 'vitest'

import { DEFAULT_FILTERS, PAGE_SIZE } from '@/lib/filters'
import { classCounts, dailyCounts, getObject, listEvents, ORDER_BY, weekComparison, type Db } from '@/lib/queries'

function fakeDb(rows: unknown[] = []) {
  const calls: { text: string; params: unknown[] }[] = []
  const db: Db = {
    async query<R>(text: string, params: unknown[] = []) {
      calls.push({ text, params })
      return { rows: rows as R[] }
    },
  }
  return { db, calls }
}

describe('listEvents', () => {
  it('binds every filter value as a parameter', async () => {
    const { db, calls } = fakeDb()
    const f = { ...DEFAULT_FILTERS, survey: 'lsst' as const, cls: "SN'--", page: 3 }
    await listEvents(db, f, 61338.5)
    const { text, params } = calls[0]!
    expect(text).not.toContain("SN'--")
    expect(text).toContain(ORDER_BY.notable)
    expect(params).toEqual([
      61338.5,
      'lsst',
      "SN'--",
      false,
      expect.arrayContaining(['SN', 'SNIa']),
      ['AGN', 'QSO', 'Blazar'],
      PAGE_SIZE + 1,
      2 * PAGE_SIZE,
    ])
  })

  it('shows artifacts when asked for them by class', async () => {
    const { db, calls } = fakeDb()
    await listEvents(db, { ...DEFAULT_FILTERS, cls: 'bogus', sort: 'newest' }, 0)
    expect(calls[0]!.params[3]).toBe(true)
    expect(calls[0]!.text).toContain(ORDER_BY.newest)
  })

  it('detects another page and strips the tier column', async () => {
    const rows = Array.from({ length: PAGE_SIZE + 1 }, (_, i) => ({ survey: 'ztf', oid: `o${i}`, tier: 1 }))
    const { db } = fakeDb(rows)
    const res = await listEvents(db, DEFAULT_FILTERS, 0)
    expect(res.hasMore).toBe(true)
    expect(res.rows).toHaveLength(PAGE_SIZE)
    expect(res.rows[0]).not.toHaveProperty('tier')
  })
})

describe('other queries', () => {
  it('binds survey and window for class counts', async () => {
    const { db, calls } = fakeDb([{ topClass: 'SN', n: 3 }])
    expect(await classCounts(db, null, 61300)).toEqual([{ topClass: 'SN', n: 3 }])
    expect(calls[0]!.params).toEqual([61300, null])
  })

  it('returns null for a missing object', async () => {
    const { db, calls } = fakeDb([])
    expect(await getObject(db, 'ztf', 'ZTF18acwycia')).toBeNull()
    expect(calls[0]!.params).toEqual(['ztf', 'ZTF18acwycia'])
  })

  it('binds sinceMjd for dailyCounts and excludes artifacts', async () => {
    const { db, calls } = fakeDb([{ day: 61255, topClass: 'SN', n: 4 }])
    expect(await dailyCounts(db, 61255)).toEqual([{ day: 61255, topClass: 'SN', n: 4 }])
    expect(calls[0]!.params).toEqual([61255])
    expect(calls[0]!.text).toContain("IS DISTINCT FROM 'bogus'")
  })

  it('binds week boundaries and transient classes for weekComparison', async () => {
    const row = { newThisWeek: 12, newLastWeek: 10, transientsThisWeek: 4, transientsLastWeek: 2 }
    const { db, calls } = fakeDb([row])
    expect(await weekComparison(db, 61338, 61331)).toEqual(row)
    expect(calls[0]!.params).toEqual([61338, 61331, expect.arrayContaining(['SN', 'SNIa', 'TDE'])])
    expect(calls[0]!.text).toContain("IS DISTINCT FROM 'bogus'")

    const empty = fakeDb([])
    expect(await weekComparison(empty.db, 61338, 61331)).toEqual({
      newThisWeek: 0,
      newLastWeek: 0,
      transientsThisWeek: 0,
      transientsLastWeek: 0,
    })
  })
})
