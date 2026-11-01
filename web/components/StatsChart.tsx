import { mjdToDate } from '@/lib/astro'
import { linear, niceTicks, roundedTopBar } from '@/lib/chart'
import { GROUPS } from '@/lib/classes'
import { formatDay } from '@/lib/format'
import type { DayBar } from '@/lib/stats'

const W = 720
const H = 260
const M = { top: 12, right: 12, bottom: 30, left: 44 }
const GAP = 2

export function StatsChart({ bars }: { bars: DayBar[] }) {
  const max = Math.max(1, ...bars.map((b) => b.total))
  const ticks = niceTicks(0, max, 4)
  const top = Math.max(max, ticks[ticks.length - 1] ?? max)
  const y = linear([0, top], [H - M.bottom, M.top])
  const slot = (W - M.left - M.right) / bars.length
  const barW = Math.min(24, slot * 0.7)
  const used = GROUPS.filter((g) => bars.some((b) => b.counts[g.id] > 0))

  return (
    <figure className="chart">
      <ul className="legend" aria-label="Class groups">
        {used.map((g) => (
          <li key={g.id}>
            <span className="swatch" data-group={g.id} aria-hidden="true" />
            {g.label}
          </li>
        ))}
      </ul>
      <svg
        className="chart-svg"
        viewBox={`0 0 ${W} ${H}`}
        role="img"
        aria-label={`New objects per day for the last ${bars.length} days, stacked by class group. Peak ${max} in one day.`}
      >
        {ticks.map((t) => (
          <g key={t}>
            <line className="grid" x1={M.left} x2={W - M.right} y1={y(t)} y2={y(t)} />
            <text className="tick" x={M.left - 8} y={y(t)} textAnchor="end" dominantBaseline="middle">
              {t}
            </text>
          </g>
        ))}
        {bars.map((b, i) => {
          const x = M.left + i * slot + (slot - barW) / 2
          const label = formatDay(mjdToDate(b.day))
          const segs = GROUPS.filter((g) => b.counts[g.id] > 0)
          let below = 0 // count already stacked under this segment
          return (
            <g key={b.day}>
              {segs.map((g, j) => {
                const n = b.counts[g.id]
                const bottomY = y(below)
                const topY = y(below + n)
                below += n
                // A 2px surface gap separates each segment from the one below it.
                const h = Math.max(1, bottomY - topY - (j > 0 ? GAP : 0))
                const tip = `${label} · ${g.label}: ${n} of ${b.total}`
                return j === segs.length - 1 ? (
                  <path key={g.id} className="seg" data-group={g.id} d={roundedTopBar(x, topY, barW, h)}>
                    <title>{tip}</title>
                  </path>
                ) : (
                  <rect key={g.id} className="seg" data-group={g.id} x={x} y={topY} width={barW} height={h}>
                    <title>{tip}</title>
                  </rect>
                )
              })}
              {i % 5 === (bars.length - 1) % 5 ? (
                <text className="tick" x={x + barW / 2} y={H - M.bottom + 18} textAnchor="middle">
                  {label}
                </text>
              ) : null}
            </g>
          )
        })}
        <line className="axis" x1={M.left} x2={W - M.right} y1={H - M.bottom} y2={H - M.bottom} />
      </svg>
      <figcaption className="muted small">
        Objects by the UTC day they were first detected. Artifacts excluded. Hover a bar segment for its count.
      </figcaption>
    </figure>
  )
}
