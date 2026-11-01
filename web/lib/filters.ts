// Parse and validate the home page's query string. Everything is allowlisted or
// pattern-checked; anything unexpected falls back to the default.

export type Survey = 'lsst' | 'ztf'
export type SearchParams = Record<string, string | string[] | undefined>

export const WINDOWS = { '1d': 1, '3d': 3, '7d': 7, '30d': 30 } as const
export type WindowKey = keyof typeof WINDOWS
export const SORTS = ['notable', 'newest'] as const
export type Sort = (typeof SORTS)[number]
export const PAGE_SIZE = 50
const MAX_PAGE = 200

export interface HomeFilters {
  survey: Survey | null
  cls: string | null
  window: WindowKey
  sort: Sort
  artifacts: boolean
  page: number
}

export const DEFAULT_FILTERS: HomeFilters = {
  survey: null,
  cls: null,
  window: '7d',
  sort: 'notable',
  artifacts: false,
  page: 1,
}

const CLASS_RE = /^[A-Za-z0-9/_-]{1,32}$/

function first(v: string | string[] | undefined): string | undefined {
  return Array.isArray(v) ? v[0] : v
}

export function isSurvey(v: unknown): v is Survey {
  return v === 'lsst' || v === 'ztf'
}

export function parseHomeFilters(sp: SearchParams): HomeFilters {
  const survey = first(sp.survey)
  const cls = first(sp.class)
  const window = first(sp.window)
  const sort = first(sp.sort)
  const page = Number.parseInt(first(sp.page) ?? '', 10)
  return {
    survey: isSurvey(survey) ? survey : null,
    cls: cls && CLASS_RE.test(cls) ? cls : null,
    window: window && window in WINDOWS ? (window as WindowKey) : DEFAULT_FILTERS.window,
    sort: (SORTS as readonly string[]).includes(sort ?? '') ? (sort as Sort) : DEFAULT_FILTERS.sort,
    artifacts: first(sp.artifacts) === '1',
    page: Number.isFinite(page) && page >= 1 ? Math.min(page, MAX_PAGE) : 1,
  }
}

/** Build a home-page href from filters, leaving defaults out of the URL. */
export function homeHref(f: HomeFilters, overrides: Partial<HomeFilters> = {}): string {
  const merged = { ...f, page: 1, ...overrides }
  const q = new URLSearchParams()
  if (merged.survey) q.set('survey', merged.survey)
  if (merged.cls) q.set('class', merged.cls)
  if (merged.window !== DEFAULT_FILTERS.window) q.set('window', merged.window)
  if (merged.sort !== DEFAULT_FILTERS.sort) q.set('sort', merged.sort)
  if (merged.artifacts) q.set('artifacts', '1')
  if (merged.page > 1) q.set('page', String(merged.page))
  const s = q.toString()
  return s ? `/?${s}` : '/'
}

// ZTF ids look like ZTF18acwycia; LSST ids are int64s.
const OID_RE: Record<Survey, RegExp> = {
  ztf: /^ZTF\d{2}[a-z]{7}$/,
  lsst: /^\d{1,20}$/,
}

export function isValidOid(survey: Survey, oid: string): boolean {
  return OID_RE[survey].test(oid)
}
