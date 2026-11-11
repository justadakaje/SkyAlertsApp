import Link from 'next/link'

import { ClassBadge } from '@/components/ClassBadge'
import { EventTable } from '@/components/EventTable'
import { skyRegion } from '@/lib/astro'
import { ARTIFACT_CLASS, classInfo } from '@/lib/classes'
import { getClassCounts, getEvents, getMatchedAsteroids, timeBucket } from '@/lib/data'
import { DEFAULT_FILTERS, homeHref, parseHomeFilters, WINDOWS, type SearchParams } from '@/lib/filters'
import { formatProbability, pickHomeHighlights } from '@/lib/format'

const WINDOW_LABEL = { '1d': 'last day', '3d': 'last 3 days', '7d': 'last 7 days', '30d': 'last 30 days' }

export default async function Home({ searchParams }: { searchParams: Promise<SearchParams> }) {
  const f = parseHomeFilters(await searchParams)
  const bucket = timeBucket()
  const showHighlights = f.page === 1 && !f.cls && !f.artifacts
  const [events, counts, matchedAsteroids] = await Promise.all([
    getEvents(f, bucket),
    getClassCounts(f.survey, f.window, bucket),
    showHighlights ? getMatchedAsteroids(3) : Promise.resolve([]),
  ])
  const now = new Date()

  const artifacts = counts.find((c) => c.topClass === ARTIFACT_CLASS)?.n ?? 0
  const visible = counts.filter((c) => f.artifacts || c.topClass !== ARTIFACT_CLASS)
  const total = visible.reduce((s, c) => s + c.n, 0)
  const selected = f.cls ? classInfo(f.cls).label : null
  const highlights = showHighlights ? pickHomeHighlights(events.rows, matchedAsteroids) : []

  return (
    <>
      <section className="hero">
        <h1>Last night&rsquo;s sky</h1>
        <p className="lede">
          {total.toLocaleString('en-US')} objects changed in the {WINDOW_LABEL[f.window]}
          {f.survey ? ` (${f.survey.toUpperCase()} only)` : ''}. Rubin data arrives as a nightly batch about a day
          after the telescope observes.
        </p>
      </section>

      {highlights.length > 0 ? (
        <section aria-labelledby="highlights-heading" className="highlights-section">
          <h2 id="highlights-heading" className="section-title">
            What stood out <span className="muted">· {WINDOW_LABEL[f.window]}</span>
          </h2>
          <div className="highlights-grid">
            {highlights.map((h) => {
              const info = classInfo(h.topClass)
              const region = h.ra !== null && h.dec !== null ? skyRegion(h.ra, h.dec) : null
              return (
                <article key={`${h.survey}:${h.oid}`} className="highlight-card">
                  <p className="eyebrow">{h.eyebrow}</p>
                  <h3>
                    <Link href={`/objects/${h.survey}/${h.oid}`} className="row-link">
                      {h.ssoLabel ? (
                        <>
                          <strong>{h.ssoLabel}</strong> <span className="muted oid">({h.oid})</span>
                        </>
                      ) : (
                        <span className="oid">{h.oid}</span>
                      )}
                    </Link>
                    <span className="survey-tag">{h.survey.toUpperCase()}</span>
                  </h3>
                  <p className="highlight-meta">
                    <ClassBadge name={h.topClass} />
                    {h.probability !== null ? (
                      <span className="muted small"> {formatProbability(h.probability)} confidence</span>
                    ) : null}
                    {h.ndet !== null ? <span className="muted small"> · {h.ndet} detections</span> : null}
                  </p>
                  {info.blurb ? <p className="small muted">{info.blurb}</p> : null}
                  {region ? <p className="small muted">{region}</p> : null}
                </article>
              )
            })}
          </div>
        </section>
      ) : null}

      <nav className="chips" aria-label="Filter by class">
        <Link href={homeHref(f, { cls: null })} className="chip" aria-current={f.cls ? undefined : 'page'}>
          All <span className="chip-n">{total}</span>
        </Link>
        {visible.map((c) => {
          const info = classInfo(c.topClass)
          if (!c.topClass) return null
          return (
            <Link
              key={c.topClass}
              href={homeHref(f, { cls: c.topClass })}
              className="chip"
              data-group={info.group}
              aria-current={f.cls === c.topClass ? 'page' : undefined}
              title={info.blurb || undefined}
            >
              <span className="badge-dot" aria-hidden="true" />
              {info.label} <span className="chip-n">{c.n}</span>
            </Link>
          )
        })}
      </nav>

      <form className="filters" method="get" action="/">
        {f.cls ? <input type="hidden" name="class" value={f.cls} /> : null}
        <label>
          Survey
          <select name="survey" defaultValue={f.survey ?? ''}>
            <option value="">Both</option>
            <option value="lsst">Rubin (LSST)</option>
            <option value="ztf">ZTF</option>
          </select>
        </label>
        <label>
          Time window
          <select name="window" defaultValue={f.window}>
            {Object.keys(WINDOWS).map((w) => (
              <option key={w} value={w}>
                {WINDOW_LABEL[w as keyof typeof WINDOW_LABEL]}
              </option>
            ))}
          </select>
        </label>
        <label>
          Order
          <select name="sort" defaultValue={f.sort}>
            <option value="notable">Most notable first</option>
            <option value="newest">Newest first</option>
          </select>
        </label>
        <label className="check">
          <input type="checkbox" name="artifacts" value="1" defaultChecked={f.artifacts} />
          Show artifacts{artifacts ? ` (${artifacts})` : ''}
        </label>
        <button type="submit">Apply</button>
      </form>

      <section aria-labelledby="events-heading">
        <h2 id="events-heading" className="section-title">
          {selected ?? 'All classes'}
          {f.sort === 'notable' ? <span className="muted"> · most notable first</span> : <span className="muted"> · newest first</span>}
        </h2>
        {events.rows.length ? (
          <EventTable rows={events.rows} now={now} />
        ) : (
          <div className="empty">
            <p>No objects match these filters in the {WINDOW_LABEL[f.window]}.</p>
            <p>
              <Link href={homeHref(DEFAULT_FILTERS, { window: '30d' })}>Try the last 30 days</Link>
            </p>
          </div>
        )}
        {f.page > 1 || events.hasMore ? (
          <nav className="pager" aria-label="Pages">
            {f.page > 1 ? <Link href={homeHref(f, { page: f.page - 1 })}>← Previous</Link> : <span />}
            <span className="muted">Page {f.page}</span>
            {events.hasMore ? <Link href={homeHref(f, { page: f.page + 1 })}>Next →</Link> : <span />}
          </nav>
        ) : null}
      </section>
    </>
  )
}
