import type { Metadata } from 'next'
import Link from 'next/link'

import { StatsChart } from '@/components/StatsChart'
import { classInfo } from '@/lib/classes'
import { getStats, timeBucket } from '@/lib/data'
import { formatCount } from '@/lib/format'
import { dailyBars, weeklyByClass } from '@/lib/stats'

export const metadata: Metadata = { title: 'Stats' }

export default async function StatsPage() {
  const { daily, totals, todayMjd } = await getStats(timeBucket())
  const bars = dailyBars(daily, todayMjd, 30)
  const { weeks, classes } = weeklyByClass(daily, todayMjd, 12)
  const sum = (cls: string, from: number, to: number) =>
    weeks.slice(from, to).reduce((s, w) => s + (w.byClass[cls] ?? 0), 0)

  return (
    <>
      <section className="hero">
        <h1>Stats</h1>
        <p className="lede">How many new objects the surveys turn up, by kind. These numbers grow as the archive does.</p>
      </section>

      <div className="tiles">
        <Tile label="Objects tracked" value={totals.objects} />
        <Tile label="New this week" value={totals.newThisWeek} />
        <Tile label="Explosions & outbursts this week" value={totals.transientsThisWeek} />
        <Tile label="Light-curve points stored" value={totals.detections} />
      </div>

      <section className="panel" aria-labelledby="daily-heading">
        <h2 id="daily-heading">New objects per day</h2>
        <StatsChart bars={bars} />
      </section>

      <section className="panel" aria-labelledby="weekly-heading">
        <h2 id="weekly-heading">By class</h2>
        <p className="muted small">New objects by first detection, in 7-day blocks ending today. Artifacts excluded.</p>
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th scope="col">Class</th>
                <th scope="col" className="num">This week</th>
                <th scope="col" className="num">Last week</th>
                <th scope="col" className="num">4 weeks</th>
                <th scope="col" className="num">12 weeks</th>
              </tr>
            </thead>
            <tbody>
              {classes.map((cls) => {
                const info = classInfo(cls === 'Unclassified' ? null : cls)
                return (
                  <tr key={cls}>
                    <th scope="row">
                      {info.name ? (
                        <Link href={`/?class=${encodeURIComponent(cls)}&window=30d`} className="row-link">
                          <span className="badge" data-group={info.group}>
                            <span className="badge-dot" aria-hidden="true" />
                            {info.label}
                          </span>
                        </Link>
                      ) : (
                        info.label
                      )}
                    </th>
                    <td className="num">{sum(cls, 0, 1)}</td>
                    <td className="num">{sum(cls, 1, 2)}</td>
                    <td className="num">{sum(cls, 0, 4)}</td>
                    <td className="num">{sum(cls, 0, 12)}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
        {classes.length === 0 ? <p className="muted">No objects first detected in the last 12 weeks yet.</p> : null}
      </section>
    </>
  )
}

function Tile({ label, value }: { label: string; value: number }) {
  return (
    <div className="tile">
      <p className="tile-label">{label}</p>
      <p className="tile-value" title={value.toLocaleString('en-US')}>
        {formatCount(value)}
      </p>
    </div>
  )
}
