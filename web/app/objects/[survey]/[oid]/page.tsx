import type { Metadata } from 'next'
import { notFound } from 'next/navigation'

import { ClassBadge } from '@/components/ClassBadge'
import { LightCurve } from '@/components/LightCurve'
import { Probabilities } from '@/components/Probabilities'
import { SkyMap } from '@/components/SkyMap'
import { alerceUrl, buildZtfStamps } from '@/lib/alerce'
import { formatDec, formatRa, mjdToDate, skyRegion } from '@/lib/astro'
import { classInfo } from '@/lib/classes'
import { getObjectPage } from '@/lib/data'
import { isSurvey, isValidOid } from '@/lib/filters'
import { formatAgo, formatObjectDescription, formatProbability, formatUtc, humanBrightness } from '@/lib/format'
import { buildCurve } from '@/lib/lightcurve'
import { formatSsoLabel, jplSbdbUrl } from '@/lib/solar'

type Params = Promise<{ survey: string; oid: string }>

export async function generateMetadata({ params }: { params: Params }): Promise<Metadata> {
  const { survey, oid } = await params
  if (!isSurvey(survey) || !isValidOid(survey, oid)) return {}
  try {
    const data = await getObjectPage(survey, oid)
    if (!data) return { title: oid }
    const { object, sso } = data
    const ssoLabel = sso?.status === 'matched' && sso.ssoName ? formatSsoLabel(sso.ssoNumber, sso.ssoName) : null
    const title = ssoLabel
      ? `${ssoLabel} · ${classInfo(object.topClass).label} · ${object.oid}`
      : `${classInfo(object.topClass).label} · ${object.oid}`
    const description = formatObjectDescription(object)
    return {
      title,
      description,
      openGraph: { title, description },
    }
  } catch {
    return { title: oid }
  }
}

export default async function ObjectPage({ params }: { params: Params }) {
  const { survey, oid } = await params
  // Ids are validated before they reach the database or the page.
  if (!isSurvey(survey) || !isValidOid(survey, oid)) notFound()
  const data = await getObjectPage(survey, oid)
  if (!data) notFound()

  const { object: o, classifications, detections, sso } = data
  const info = classInfo(o.topClass)
  const curve = buildCurve(survey, detections)
  const stamps = survey === 'ztf' ? buildZtfStamps(o.oid, detections) : null
  const matchedSso = sso?.status === 'matched' && sso.ssoName ? sso : null
  const ssoLabel = matchedSso && matchedSso.ssoName ? formatSsoLabel(matchedSso.ssoNumber, matchedSso.ssoName) : null
  const sbdbUrl = matchedSso ? jplSbdbUrl(matchedSso.ssoNumber, matchedSso.ssoName) : null
  const now = new Date()
  const first = o.firstmjd === null ? null : mjdToDate(o.firstmjd)
  const last = o.lastmjd === null ? null : mjdToDate(o.lastmjd)
  const peakMag = detections.reduce<number | null>(
    (best, d) => (d.mag !== null && !d.negative && (best === null || d.mag < best) ? d.mag : best),
    null,
  )
  const peakFlux = detections.reduce<number | null>(
    (best, d) => (d.fluxNjy !== null && d.fluxNjy > 0 && (best === null || d.fluxNjy > best) ? d.fluxNjy : best),
    null,
  )
  const brightnessNote = humanBrightness(peakMag, peakFlux)
  const regionNote = o.ra !== null && o.dec !== null ? skyRegion(o.ra, o.dec) : null

  return (
    <article className="object">
      <header className="object-head">
        <p className="eyebrow">{survey === 'lsst' ? 'Rubin Observatory (LSST)' : 'Zwicky Transient Facility'}</p>
        <h1 className="oid-title">{o.oid}</h1>
        <p className="object-class">
          <ClassBadge name={o.topClass} />
          {o.probability !== null ? <span className="muted"> {formatProbability(o.probability)} confidence</span> : null}
          {ssoLabel ? <span className="sso-tag">{ssoLabel}</span> : null}
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
          {regionNote ? <dd className="muted small">{regionNote}</dd> : null}
        </div>
        {brightnessNote ? (
          <div>
            <dt>Peak brightness</dt>
            <dd>{brightnessNote.split(' · ')[0]}</dd>
            <dd className="muted small">{brightnessNote.split(' · ').slice(1).join(' · ')}</dd>
          </div>
        ) : null}
      </dl>

      {matchedSso && ssoLabel ? (
        <section aria-labelledby="sso-heading" className="panel sso-callout">
          <h2 id="sso-heading">Solar System identification</h2>
          <p className="small">
            Matched to known asteroid <strong>{ssoLabel}</strong> via{' '}
            <a href="https://ssp.imcce.fr/webservices/skybot/" target="_blank" rel="noopener noreferrer">
              IMCCE SkyBoT
            </a>
            .
          </p>
          <dl className="facts sso-facts">
            <div>
              <dt>Identified object</dt>
              <dd>{ssoLabel}</dd>
              {matchedSso.ssoClass ? <dd className="muted small">Orbit class: {matchedSso.ssoClass}</dd> : null}
            </div>
            <div>
              <dt>Angular separation</dt>
              <dd className="num">
                {matchedSso.sepArcsec !== null ? `${matchedSso.sepArcsec.toFixed(2)}″` : '—'}
              </dd>
              <dd className="muted small num">at MJD {matchedSso.obsMjd.toFixed(5)}</dd>
            </div>
            <div>
              <dt>Predicted magnitude</dt>
              <dd className="num">
                {matchedSso.predictedMag !== null ? `V ≈ ${matchedSso.predictedMag.toFixed(1)}` : '—'}
              </dd>
            </div>
            <div>
              <dt>Distance (Earth / Sun)</dt>
              <dd className="num">
                {matchedSso.geoDistAu !== null && matchedSso.helioDistAu !== null
                  ? `${matchedSso.geoDistAu.toFixed(3)} / ${matchedSso.helioDistAu.toFixed(3)} au`
                  : matchedSso.geoDistAu !== null
                    ? `${matchedSso.geoDistAu.toFixed(3)} au (Earth)`
                    : matchedSso.helioDistAu !== null
                      ? `${matchedSso.helioDistAu.toFixed(3)} au (Sun)`
                      : '—'}
              </dd>
            </div>
          </dl>
          {sbdbUrl ? (
            <p className="sso-links small">
              <a className="external" href={sbdbUrl} target="_blank" rel="noopener noreferrer">
                Open {ssoLabel} in the JPL Small-Body Database ↗
              </a>
            </p>
          ) : null}
        </section>
      ) : sso?.status === 'no_match' ? (
        <section aria-labelledby="sso-heading" className="panel">
          <h2 id="sso-heading">Solar System identification</h2>
          <p className="muted small">
            Checked against IMCCE SkyBoT within 10″ at MJD {sso.obsMjd.toFixed(5)}; no catalogued Solar System object
            matched.
          </p>
        </section>
      ) : null}

      {stamps ? (
        <section aria-labelledby="stamps-heading" className="panel">
          <h2 id="stamps-heading">Alert cutouts</h2>
          <p className="muted small">
            ZTF image stamps for detection <span className="mono">{stamps.candid}</span> (
            <time dateTime={mjdToDate(stamps.mjd).toISOString()}>{formatUtc(mjdToDate(stamps.mjd))}</time>
            {stamps.band ? `, ${stamps.band} band` : ''}), served by ALeRCE.
          </p>
          <div className="stamp-grid">
            {stamps.stamps.map((s) => (
              <figure key={s.type} className="stamp-card">
                {/* eslint-disable-next-line @next/next/no-img-element -- external scientific cutout served by ALeRCE */}
                <img
                  src={s.url}
                  alt={`${s.label} cutout for ${o.oid} (${s.description})`}
                  width={180}
                  height={180}
                  loading="lazy"
                  decoding="async"
                  referrerPolicy="no-referrer"
                />
                <figcaption>
                  <strong>{s.label}</strong>
                  <span className="muted small">{s.description}</span>
                </figcaption>
              </figure>
            ))}
          </div>
        </section>
      ) : null}

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
