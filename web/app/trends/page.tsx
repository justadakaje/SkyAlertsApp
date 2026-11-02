import type { Metadata } from 'next'

import { DailyMultiplesChart, WeeklyMixChart } from '@/components/TrendsCharts'
import { getTrends, timeBucket } from '@/lib/data'
import { formatCount } from '@/lib/format'
import { dailyMultiples, formatChange, weeklyMix } from '@/lib/trends'

export const metadata: Metadata = { title: 'Trends' }

export default async function TrendsPage() {
  const { daily, comparison, todayMjd } = await getTrends(timeBucket())
  const multiples = dailyMultiples(daily, todayMjd, 90)
  const weeks = weeklyMix(daily, todayMjd, 12)

  return (
    <>
      <section className="hero">
        <h1>Trends</h1>
        <p className="lede">
          How discovery rates and the mix of sky events change over time. Seasonal patterns—from weather, survey cadence
          and where the Milky Way sits in the night sky—will appear here as data accumulates across months and years.
        </p>
      </section>

      <div className="tiles">
        <ComparisonTile
          label="New objects this week"
          current={comparison.newThisWeek}
          previous={comparison.newLastWeek}
        />
        <ComparisonTile
          label="Explosions & outbursts this week"
          current={comparison.transientsThisWeek}
          previous={comparison.transientsLastWeek}
        />
      </div>

      <section className="panel" aria-labelledby="multiples-heading">
        <h2 id="multiples-heading">New objects per day (last 90 days)</h2>
        <DailyMultiplesChart multiples={multiples} />
      </section>

      <section className="panel" aria-labelledby="mix-heading">
        <h2 id="mix-heading">Weekly class mix (last 12 weeks)</h2>
        <WeeklyMixChart weeks={weeks} />
      </section>
    </>
  )
}

function ComparisonTile({ label, current, previous }: { label: string; current: number; previous: number }) {
  const delta = formatChange(current, previous)
  return (
    <div className="tile">
      <p className="tile-label">{label}</p>
      <p className="tile-value num" title={current.toLocaleString('en-US')}>
        {formatCount(current)} <span className="tile-delta">{delta}</span>
      </p>
      <p className="tile-sub muted small num" title={previous.toLocaleString('en-US')}>
        vs {formatCount(previous)} last week
      </p>
    </div>
  )
}
