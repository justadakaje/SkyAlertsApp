import type { Metadata } from 'next'
import { notFound } from 'next/navigation'

import { ClassBadge } from '@/components/ClassBadge'
import { LightCurve } from '@/components/LightCurve'
import { Probabilities } from '@/components/Probabilities'
import { SkyMap } from '@/components/SkyMap'
import { alerceUrl } from '@/lib/alerce'
import { formatDec, formatRa, mjdToDate } from '@/lib/astro'
import { classInfo } from '@/lib/classes'
import { getObjectPage } from '@/lib/data'
import { isSurvey, isValidOid } from '@/lib/filters'
import { formatAgo, formatProbability, formatUtc } from '@/lib/format'
import { buildCurve } from '@/lib/lightcurve'

type Params = Promise<{ survey: string; oid: string }>

export async function generateMetadata({ params }: { params: Params }): Promise<Metadata> {
  const { survey, oid } = await params
  return isSurvey(survey) && isValidOid(survey, oid) ? { title: oid } : {}
}

export default async function ObjectPage({ params }: { params: Params }) {
  const { survey, oid } = await params
  // Ids are validated before they reach the database or the page.
  if (!isSurvey(survey) || !isValidOid(survey, oid)) notFound()
  const data = await getObjectPage(survey, oid)
  if (!data) notFound()

  const { object: o, classifications, detections } = data
  const info = classInfo(o.topClass)
  const curve = buildCurve(survey, detections)
  const now = new Date()
  const first = o.firstmjd === null ? null : mjdToDate(o.firstmjd)
  const last = o.lastmjd === null ? null : mjdToDate(o.lastmjd)

  return (
    <article className="object">
      <header className="object-head">
        <p className="eyebrow">{survey === 'lsst' ? 'Rubin Observatory (LSST)' : 'Zwicky Transient Facility'}</p>
        <h1 className="oid-title">{o.oid}</h1>
        <p className="object-class">
          <ClassBadge name={o.topClass} />
          {o.probability !== null ? <span className="muted"> {formatProbability(o.probability)} confidence</span> : null}
        </p>
        {info.blurb ? <p className="lede">{info.blurb}</p> : null}
        <p>
          <a className="external" href={alerceUrl(survey, o.oid)} target="_blank" rel="noopener noreferrer">
            Open in the ALeRCE explorer ↗
          </a>
        </p>
      </header>

      <dl className="facts">
        <div>
          <dt>First detected</dt>
          <dd>{first ? <time dateTime={first.toISOString()}>{formatUtc(first)}</time> : '—'}</dd>
          {first ? <dd className="muted small">{formatAgo(first, now)}</dd> : null}
        </div>
        <div>
          <dt>Last detected</dt>
          <dd>{last ? <time dateTime={last.toISOString()}>{formatUtc(last)}</time> : '—'}</dd>
          {last ? <dd className="muted small">{formatAgo(last, now)}</dd> : null}
        </div>
        <div>
          <dt>Detections</dt>
          <dd className="num">{o.ndet ?? '—'}</dd>
          {o.nForced ? <dd className="muted small">plus {o.nForced} forced measurements</dd> : null}
        </div>
        <div>
          <dt>Position (J2000)</dt>
          <dd className="num">
            {o.ra !== null && o.dec !== null ? `${formatRa(o.ra)} ${formatDec(o.dec)}` : '—'}
          </dd>
          {o.ra !== null && o.dec !== null ? (
            <dd className="muted small num">
              {o.ra.toFixed(5)}°, {o.dec.toFixed(5)}°
            </dd>
          ) : null}
        </div>
      </dl>

      <section aria-labelledby="lc-heading" className="panel">
        <h2 id="lc-heading">Light curve</h2>
        {curve ? (
          <LightCurve model={curve} label={`Light curve of ${o.oid}`} />
        ) : (
          <div className="empty">
            <p>No light-curve points stored yet.</p>
            <p className="muted">
              Sky Alerts fetches light curves for the most notable objects after each nightly update, so this one may
              fill in tomorrow. The ALeRCE explorer has the full history now.
            </p>
          </div>
        )}
      </section>

      <section aria-labelledby="prob-heading" className="panel">
        <h2 id="prob-heading">Classification</h2>
        {classifications.length ? (
          <Probabilities rows={classifications} preferred={o.classifier} />
        ) : (
          <p className="muted">No classifier output stored for this object.</p>
        )}
      </section>

      {o.ra !== null && o.dec !== null ? (
        <section aria-labelledby="sky-heading" className="panel">
          <h2 id="sky-heading">Where in the sky</h2>
          <SkyMap ra={o.ra} dec={o.dec} />
        </section>
      ) : null}
    </article>
  )
}
