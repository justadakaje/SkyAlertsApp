import type { Metadata } from 'next'
import Link from 'next/link'

import { ClassBadge } from '@/components/ClassBadge'
import { classesByGroup, GROUPS } from '@/lib/classes'

export const metadata: Metadata = {
  title: 'About',
  description:
    'How Sky Alerts works, how to read light curves and machine-learning classifications, and what each astronomical class means.',
}

export default function AboutPage() {
  return (
    <>
      <section className="hero">
        <h1>About Sky Alerts</h1>
        <p className="lede">
          Every clear night, the <strong>Vera C. Rubin Observatory (LSST)</strong> in Chile and the{' '}
          <strong>Zwicky Transient Facility (ZTF)</strong> in California scan the sky and subtract a deep reference map
          from each fresh exposure. Whenever something brightens, dims, or moves, the telescope emits an alert.
        </p>
        <p className="lede">
          The <strong>ALeRCE broker</strong> classifies those alerts with machine-learning models, and Sky Alerts
          refreshes its database once a day so you can browse notable cosmic events without querying the live broker on
          page load. Rubin alerts arrive as a nightly batch roughly a day after observation.
        </p>
        <p className="lede">
          Want the full architecture and pipeline walkthrough? Read{' '}
          <a href="/skyalerts-explainer.html">How It Works</a>.
        </p>
      </section>

      <section className="panel" aria-labelledby="reading-heading">
        <h2 id="reading-heading">How to read a page</h2>
        <div className="facts about-facts">
          <div>
            <h3>Class &amp; confidence</h3>
            <p className="muted small">
              Every class badge and confidence percentage is a <strong>machine-learning prediction, not a confirmed
              identification</strong>. A stamp classifier makes an initial guess from the first image cutout; once
              several nights of measurements accumulate, a light-curve classifier refines the subtype. Confirming a
              supernova for certain still requires a spectrum from a follow-up telescope.
            </p>
          </div>
          <div>
            <h3>Light curve</h3>
            <p className="muted small">
              A light curve plots brightness over time, coloured by optical filter band (<code>u, g, r, i, z, y</code>).
              For <strong>ZTF</strong>, brightness is plotted in astronomical <strong>magnitudes</strong>, where smaller
              numbers are brighter—so <strong>brighter is up (↑)</strong>. For <strong>Rubin (LSST)</strong>, the chart
              plots <strong>difference flux in microjanskys (µJy)</strong> compared with the reference image: positive
              flux means brighter than the reference, and negative flux is a real measurement when a variable source has
              dimmed below its reference level.
            </p>
          </div>
          <div>
            <h3>Sky position</h3>
            <p className="muted small">
              Coordinates are given as right ascension (RA) and declination (Dec, J2000). The all-sky map places the
              object on the celestial sphere alongside the dashed curve of the Milky Way&rsquo;s galactic plane. Distant
              supernovae and active galaxies appear mostly away from the dusty plane, while variable stars cluster along
              it.
            </p>
          </div>
        </div>
      </section>

      <section className="panel" aria-labelledby="groups-heading">
        <h2 id="groups-heading">What the class groups mean</h2>
        <p className="muted small">
          Click any class to browse recent objects of that type across the last 30 days.
        </p>
        <div className="group-grid">
          {GROUPS.map((g) => {
            const items = classesByGroup(g.id)
            return (
              <div key={g.id} className="group-card">
                <h3 className="group-head">
                  <span className="swatch" data-group={g.id} aria-hidden="true" />
                  {g.label}
                </h3>
                <p className="muted small">{g.blurb}</p>
                <dl className="class-dl">
                  {items.map((c) => (
                    <div key={c.name} className="class-item">
                      <dt>
                        {c.name ? (
                          <Link href={`/?class=${encodeURIComponent(c.name)}&window=30d`} className="row-link">
                            <ClassBadge name={c.name} />
                          </Link>
                        ) : (
                          <ClassBadge name={c.name} />
                        )}
                      </dt>
                      <dd className="muted small">{c.blurb}</dd>
                    </div>
                  ))}
                </dl>
              </div>
            )
          })}
        </div>
      </section>

      <section className="panel" aria-labelledby="credits-heading">
        <h2 id="credits-heading">Credits &amp; data sources</h2>
        <ul className="credits-list">
          <li>
            <a href="https://alerce.science" target="_blank" rel="noopener noreferrer">
              ALeRCE (Automatic Learning for the Rapid Classification of Events) ↗
            </a>{' '}
            — community astronomical alert broker that ingests, cross-matches, and classifies the survey streams, and
            hosts the{' '}
            <a href="https://alerce.online" target="_blank" rel="noopener noreferrer">
              ALeRCE Explorer ↗
            </a>
            .
          </li>
          <li>
            <a href="https://rubinobservatory.org" target="_blank" rel="noopener noreferrer">
              Vera C. Rubin Observatory (Legacy Survey of Space and Time / LSST) ↗
            </a>{' '}
            — 8.4-metre Simonyi Survey Telescope and 3,200-megapixel LSST Camera on Cerro Pachón, Chile.
          </li>
          <li>
            <a href="https://www.ztf.caltech.edu" target="_blank" rel="noopener noreferrer">
              Zwicky Transient Facility (ZTF) ↗
            </a>{' '}
            — wide-field optical sky survey on the Samuel Oschin 48-inch Schmidt telescope at Palomar Observatory.
          </li>
        </ul>
        <p className="muted small">
          For the technical design of Sky Alerts—difference imaging, database schema, least-privilege roles, and daily
          enrichment—see <a href="/skyalerts-explainer.html">How It Works</a>.
        </p>
      </section>
    </>
  )
}
