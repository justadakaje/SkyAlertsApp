import type { Metadata } from 'next'
import Link from 'next/link'
import { Suspense } from 'react'

import { objectHref } from '@/components/EventTable'
import { SkyMap } from '@/components/SkyMap'
import { formatDec, formatRa, mjdToDate } from '@/lib/astro'
import { getClassCounts, getMatchedAsteroids, getSolarEphemerides, timeBucket } from '@/lib/data'
import { formatCount, formatUtc } from '@/lib/format'
import type { MatchedAsteroidRow } from '@/lib/queries'
import {
  CONSTELLATIONS,
  type Ephemeris,
  formatPeriod,
  formatRotation,
  formatSsoLabel,
  jplSbdbUrl,
  jplUrl,
  orbitviewerUrl,
  SOLAR_BODIES,
  type SolarBody,
  viewingHint,
} from '@/lib/solar'

export const metadata: Metadata = {
  title: 'Solar System',
  description:
    'The dwarf planets and the largest candidates: where they are today, how they orbit, and how to explore them in 3D.',
}

const EXT = { target: '_blank', rel: 'noopener noreferrer' } as const

export default function SolarSystemPage() {
  const day = new Date().toISOString().slice(0, 10)
  return (
    <>
      <section className="hero">
        <h1>Solar System</h1>
        <p className="lede">
          Beyond the planets, the Sun holds millions of smaller worlds. The International Astronomical Union recognises
          five <strong>dwarf planets</strong>: Ceres in the asteroid belt, and Pluto, Eris, Haumea and Makemake beyond
          Neptune. Several more icy bodies are probably large enough to qualify. Rubin Observatory is expected to find
          many more of them.
        </p>
      </section>

      <Suspense fallback={<TodaySkeleton />}>
        <Today day={day} />
      </Suspense>

      <section className="panel" aria-labelledby="roster-heading">
        <h2 id="roster-heading">The dwarf planets</h2>
        <div className="solar-grid">
          {SOLAR_BODIES.filter((b) => b.status === 'dwarf').map((b) => (
            <BodyCard key={b.id} body={b} />
          ))}
        </div>
      </section>

      <section className="panel" aria-labelledby="candidates-heading">
        <h2 id="candidates-heading">Likely dwarf planets</h2>
        <p className="muted small">
          Large enough to be round, but not yet officially recognised by the IAU.
        </p>
        <div className="solar-grid">
          {SOLAR_BODIES.filter((b) => b.status === 'candidate').map((b) => (
            <BodyCard key={b.id} body={b} />
          ))}
        </div>
      </section>

      <Suspense fallback={null}>
        <AsteroidAlerts />
      </Suspense>

      <section className="panel" aria-labelledby="sources-heading">
        <h2 id="sources-heading">Where this comes from</h2>
        <p className="muted small">
          Orbits, rotation and discovery details come from the{' '}
          <a href="https://ssd.jpl.nasa.gov/tools/sbdb_lookup.html" {...EXT}>
            JPL Small-Body Database
          </a>
          . Daily positions and brightness come from{' '}
          <a href="https://ssd.jpl.nasa.gov/horizons/" {...EXT}>
            JPL Horizons
          </a>
          . Sizes are published estimates. The 3D views are Rubin Observatory&rsquo;s{' '}
          <a href="https://orbitviewer.app/en/" {...EXT}>
            Orbitviewer
          </a>
          , which has pages for selected objects only; the others link to JPL&rsquo;s orbit diagram. Photos are from NASA
          missions. No spacecraft has visited Eris, Haumea, Makemake or the candidates, so no close-up photos of them
          exist.
        </p>
      </section>
    </>
  )
}

function TodaySkeleton() {
  return (
    <section className="panel" aria-busy="true">
      <h2>Where they are today</h2>
      <p className="muted small">Asking JPL Horizons…</p>
    </section>
  )
}

async function Today({ day }: { day: string }) {
  let eph: Record<string, Ephemeris | null>
  try {
    eph = await getSolarEphemerides(day)
  } catch {
    return (
      <section className="panel" aria-labelledby="today-heading">
        <h2 id="today-heading">Where they are today</h2>
        <p className="muted small">JPL Horizons did not answer just now. Positions will be back shortly.</p>
      </section>
    )
  }
  const points = SOLAR_BODIES.flatMap((b) => {
    const e = eph[b.id]
    return e ? [{ ra: e.ra, dec: e.dec, label: b.name }] : []
  })
  return (
    <section className="panel" aria-labelledby="today-heading">
      <h2 id="today-heading">Where they are today</h2>
      <p className="muted small">Positions for {day} 00:00 UTC, seen from Earth. Smaller magnitude means brighter.</p>
      <SkyMap points={points} />
      <div className="table-scroll">
        <table className="events">
          <thead>
            <tr>
              <th scope="col">Object</th>
              <th scope="col">Constellation</th>
              <th scope="col">RA / Dec</th>
              <th scope="col" className="num">
                Magnitude
              </th>
              <th scope="col" className="num">
                Distance
              </th>
              <th scope="col">To see it</th>
            </tr>
          </thead>
          <tbody>
            {SOLAR_BODIES.map((b) => {
              const e = eph[b.id]
              return (
                <tr key={b.id}>
                  <th scope="row">
                    <a href={`#${b.id}`}>{b.name}</a>
                  </th>
                  {e ? (
                    <>
                      <td>{CONSTELLATIONS[e.constellation] ?? e.constellation}</td>
                      <td className="mono small">
                        {formatRa(e.ra)} {formatDec(e.dec)}
                      </td>
                      <td className="num">{e.mag === null ? '—' : e.mag.toFixed(1)}</td>
                      <td className="num">{e.distanceAu.toFixed(e.distanceAu < 10 ? 2 : 1)} au</td>
                      <td>{viewingHint(e)}</td>
                    </>
                  ) : (
                    <td colSpan={5} className="muted">
                      Position unavailable
                    </td>
                  )}
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
      <p className="muted small">
        1 au is the Earth–Sun distance, about 150 million km. Viewing hints are a rough guide for a dark site.
      </p>
    </section>
  )
}

function BodyCard({ body: b }: { body: SolarBody }) {
  const ov = orbitviewerUrl(b)
  return (
    <article className="solar-card" id={b.id}>
      {b.image ? (
        <figure className="solar-photo">
          {/* eslint-disable-next-line @next/next/no-img-element -- small static file, no optimiser needed */}
          <img src={b.image.src} alt={b.image.alt} width={480} height={480} loading="lazy" />
          <figcaption className="muted small">
            <a href={b.image.source} {...EXT}>
              {b.image.credit}
            </a>
          </figcaption>
        </figure>
      ) : null}
      <h3>
        {b.name} <span className="muted small">({b.number.toLocaleString('en-US')})</span>
      </h3>
      <p className="muted small">{b.zone}</p>
      <p className="small">{b.blurb}</p>
      <dl className="solar-facts small">
        <dt>Diameter</dt>
        <dd>{b.approxDiameterKm} km</dd>
        <dt>Distance from Sun</dt>
        <dd>
          {b.q} – {b.Q} au
        </dd>
        <dt>One orbit</dt>
        <dd>{formatPeriod(b.periodDays)}</dd>
        <dt>One day</dt>
        <dd>{formatRotation(b.rotationH)}</dd>
        <dt>Orbit tilt</dt>
        <dd>{b.i}°</dd>
        <dt>Discovered</dt>
        <dd>
          {b.discovered.slice(0, 4)}, {b.discoveredAt}
          <span className="muted"> · {b.discoveredBy}</span>
        </dd>
        <dt>Designation</dt>
        <dd className="mono">{b.designation}</dd>
      </dl>
      <p className="solar-links small">
        {ov ? (
          <a href={ov} {...EXT}>
            3D orbit in Orbitviewer ↗
          </a>
        ) : null}
        <a href={jplUrl(b)} {...EXT}>
          {ov ? 'JPL data ↗' : 'Orbit diagram at JPL ↗'}
        </a>
      </p>
    </article>
  )
}

async function AsteroidAlerts() {
  let n = 0
  let matched: MatchedAsteroidRow[] = []
  try {
    const [counts, rows] = await Promise.all([
      getClassCounts(null, '7d', timeBucket()),
      getMatchedAsteroids(25),
    ])
    n = counts.find((c) => c.topClass === 'asteroid')?.n ?? 0
    matched = rows
  } catch {
    return null
  }
  return (
    <section className="panel" aria-labelledby="alerts-heading">
      <h2 id="alerts-heading">Asteroid alerts this week</h2>
      <p className="small">
        <Link href="/?class=asteroid&window=7d">{formatCount(n)} alerts</Link> in the last 7 days were classified as
        asteroids. Each is a machine-learning guess from a single image; Sky Alerts checks top candidates against{' '}
        <a href="https://ssp.imcce.fr/webservices/skybot/" {...EXT}>
          IMCCE SkyBoT
        </a>{' '}
        to identify which known asteroid was within 10″ of that spot at the moment of detection.
      </p>
      {matched.length > 0 ? (
        <div className="table-scroll">
          <table className="events">
            <thead>
              <tr>
                <th scope="col">Asteroid</th>
                <th scope="col">Alert</th>
                <th scope="col">Orbit class</th>
                <th scope="col" className="num">
                  Separation
                </th>
                <th scope="col" className="num">
                  Predicted mag
                </th>
                <th scope="col" className="num">
                  Earth / Sun dist.
                </th>
                <th scope="col">Observed</th>
              </tr>
            </thead>
            <tbody>
              {matched.map((m) => {
                const label = formatSsoLabel(m.ssoNumber, m.ssoName)
                const sbdb = jplSbdbUrl(m.ssoNumber, m.ssoName)
                const obsDate = Number.isFinite(m.obsMjd) ? mjdToDate(m.obsMjd) : null
                return (
                  <tr key={`${m.survey}/${m.oid}`}>
                    <th scope="row">
                      {sbdb ? (
                        <a href={sbdb} {...EXT}>
                          {label} ↗
                        </a>
                      ) : (
                        label
                      )}
                    </th>
                    <td>
                      <Link className="oid" href={objectHref(m.survey, m.oid)}>
                        {m.oid}
                      </Link>
                      <span className="survey-tag">{m.survey.toUpperCase()}</span>
                    </td>
                    <td>{m.ssoClass ?? '—'}</td>
                    <td className="num">{m.sepArcsec.toFixed(2)}″</td>
                    <td className="num">{m.predictedMag !== null ? m.predictedMag.toFixed(1) : '—'}</td>
                    <td className="num">
                      {m.geoDistAu !== null && m.helioDistAu !== null
                        ? `${m.geoDistAu.toFixed(2)} / ${m.helioDistAu.toFixed(2)} au`
                        : m.geoDistAu !== null
                          ? `${m.geoDistAu.toFixed(2)} au`
                          : m.helioDistAu !== null
                            ? `${m.helioDistAu.toFixed(2)} au`
                            : '—'}
                    </td>
                    <td className="small">
                      {obsDate ? <time dateTime={obsDate.toISOString()}>{formatUtc(obsDate)}</time> : '—'}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      ) : (
        <p className="muted small">No asteroid alerts have been matched to a catalogued object yet.</p>
      )}
    </section>
  )
}
