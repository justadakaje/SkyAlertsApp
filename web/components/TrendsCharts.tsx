import { mjdToDate } from '@/lib/astro'
import { linear, niceTicks, roundedTopBar } from '@/lib/chart'
import { GROUPS } from '@/lib/classes'
import { formatCount, formatDay } from '@/lib/format'
import type { DailyMultiples, SurveyWeekColumn, WeekMixColumn } from '@/lib/trends'

const W = 720
const M = { top: 12, right: 12, bottom: 30, left: 48 }
const GAP = 2

export function DailyMultiplesChart({ multiples }: { multiples: DailyMultiples }) {
  const yTicks = niceTicks(0, multiples.maxCount, 2)
  const topVal = Math.max(multiples.maxCount, yTicks[yTicks.length - 1] ?? multiples.maxCount)
  const numDays = multiples.bars.length || 1
  const slot = (W - M.left - M.right) / numDays
  const barW = Math.max(2, Math.min(8, slot * 0.78))

  return (
    <figure className="chart">
      <ul className="legend" aria-label="Class groups">
        {GROUPS.map((g) => (
          <li key={g.id}>
            <span className="swatch" data-group={g.id} aria-hidden="true" />
            {g.label}
          </li>
        ))}
      </ul>
      {multiples.panels.map((panel, pIdx) => {
        const isLast = pIdx === multiples.panels.length - 1
        const panelH = isLast ? 116 : 92
        const top = 10
        const bottom = isLast ? panelH - 28 : panelH - 8
        const y = linear([0, topVal], [bottom, top])
        return (
          <svg
            key={panel.group}
            className="chart-svg"
            viewBox={`0 0 ${W} ${panelH}`}
            role="img"
            aria-label={`${panel.label}: new objects per day for the last ${panel.days.length} days. Total ${panel.total}, peak ${panel.peak} in one day (shared scale up to ${topVal}).`}
          >
            {yTicks.map((t) => (
              <g key={t}>
                <line className="grid" x1={M.left} x2={W - M.right} y1={y(t)} y2={y(t)} />
                <text className="tick" x={M.left - 8} y={y(t)} textAnchor="end" dominantBaseline="middle">
                  {t}
                </text>
              </g>
            ))}
            {panel.days.map((d, i) => {
              const x = M.left + i * slot + (slot - barW) / 2
              const label = formatDay(mjdToDate(d.day))
              const showTick = i % 15 === (panel.days.length - 1) % 15
              const topY = y(d.count)
              const h = Math.max(1, bottom - topY)
              return (
                <g key={d.day}>
                  {d.count > 0 ? (
                    <rect className="seg" data-group={panel.group} x={x} y={topY} width={barW} height={h}>
                      <title>{`${label} · ${panel.label}: ${d.count}`}</title>
                    </rect>
                  ) : null}
                  {showTick ? (
                    <line className="axis" x1={x + barW / 2} x2={x + barW / 2} y1={bottom} y2={bottom + 4} />
                  ) : null}
                  {isLast && showTick ? (
                    <text className="tick" x={x + barW / 2} y={bottom + 18} textAnchor="middle">
                      {label}
                    </text>
                  ) : null}
                </g>
              )
            })}
            <line className="axis" x1={M.left} x2={W - M.right} y1={bottom} y2={bottom} />
            <text className="panel-label" x={M.left + 6} y={top + 12}>
              {panel.label} · {formatCount(panel.total)}
            </text>
          </svg>
        )
      })}
      <figcaption className="muted small">
        Objects by the UTC day they were first detected over the last {multiples.bars.length} days. One panel per class
        group on a shared y-scale; artifacts excluded. Hover a bar for its daily count.
      </figcaption>
      <details className="table-view">
        <summary>Data table ({multiples.bars.length} days)</summary>
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th scope="col">Day (UTC)</th>
                {GROUPS.map((g) => (
                  <th key={g.id} scope="col" className="num">
                    {g.label}
                  </th>
                ))}
                <th scope="col" className="num">
                  Total
                </th>
              </tr>
            </thead>
            <tbody>
              {[...multiples.bars].reverse().map((b) => (
                <tr key={b.day}>
                  <th scope="row">{mjdToDate(b.day).toISOString().slice(0, 10)}</th>
                  {GROUPS.map((g) => (
                    <td key={g.id} className="num">
                      {b.counts[g.id]}
                    </td>
                  ))}
                  <td className="num">{b.total}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </figure>
  )
}

const MIX_H = 260
const PCT_TICKS = [0, 25, 50, 75, 100]

export function WeeklyMixChart({ weeks }: { weeks: WeekMixColumn[] }) {
  const y = linear([0, 100], [MIX_H - M.bottom, M.top])
  const slot = (W - M.left - M.right) / Math.max(1, weeks.length)
  const barW = Math.min(36, slot * 0.72)

  return (
    <figure className="chart">
      <ul className="legend" aria-label="Class groups">
        {GROUPS.map((g) => (
          <li key={g.id}>
            <span className="swatch" data-group={g.id} aria-hidden="true" />
            {g.label}
          </li>
        ))}
      </ul>
      <svg
        className="chart-svg"
        viewBox={`0 0 ${W} ${MIX_H}`}
        role="img"
        aria-label={`Weekly class mix for the last ${weeks.length} full weeks, 100%-stacked by class group.`}
      >
        {PCT_TICKS.map((t) => (
          <g key={t}>
            <line className="grid" x1={M.left} x2={W - M.right} y1={y(t)} y2={y(t)} />
            <text className="tick" x={M.left - 8} y={y(t)} textAnchor="end" dominantBaseline="middle">
              {t}%
            </text>
          </g>
        ))}
        {weeks.map((w, i) => {
          const x = M.left + i * slot + (slot - barW) / 2
          const startLabel = formatDay(mjdToDate(w.start))
          const endLabel = formatDay(mjdToDate(w.end))
          const rangeLabel = `${startLabel}–${endLabel}`
          const segs = GROUPS.filter((g) => w.counts[g.id] > 0)
          let below = 0
          return (
            <g key={w.start}>
              {segs.map((g, j) => {
                const n = w.counts[g.id]
                const pct = w.pcts[g.id]
                const bottomY = y(below)
                const topY = y(below + pct)
                below += pct
                // A 2px surface gap separates each segment from the one below it.
                const h = Math.max(1, bottomY - topY - (j > 0 ? GAP : 0))
                const tip = `${rangeLabel} · ${g.label}: ${Math.round(pct)}% (${n} of ${w.total})`
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
              <text className="tick" x={x + barW / 2} y={MIX_H - M.bottom + 18} textAnchor="middle">
                {endLabel}
              </text>
            </g>
          )
        })}
        <line className="axis" x1={M.left} x2={W - M.right} y1={MIX_H - M.bottom} y2={MIX_H - M.bottom} />
      </svg>
      <figcaption className="muted small">
        100%-stacked share of new objects by class group across the last {weeks.length} full 7-day weeks. Artifacts
        excluded. Hover a segment for its percentage and count.
      </figcaption>
      <details className="table-view">
        <summary>Data table ({weeks.length} weeks)</summary>
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th scope="col">Week (UTC)</th>
                {GROUPS.map((g) => (
                  <th key={g.id} scope="col" className="num">
                    {g.label}
                  </th>
                ))}
                <th scope="col" className="num">
                  Total
                </th>
              </tr>
            </thead>
            <tbody>
              {[...weeks].reverse().map((w) => (
                <tr key={w.start}>
                  <th scope="row">
                    {mjdToDate(w.start).toISOString().slice(0, 10)} – {mjdToDate(w.end).toISOString().slice(0, 10)}
                  </th>
                  {GROUPS.map((g) => (
                    <td key={g.id} className="num">
                      {w.counts[g.id]} ({Math.round(w.pcts[g.id])}%)
                    </td>
                  ))}
                  <td className="num">{w.total}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </figure>
  )
}

const SURVEYS = [
  { id: 'lsst' as const, label: 'Rubin (LSST)', group: 'transient' as const },
  { id: 'ztf' as const, label: 'ZTF', group: 'variable' as const },
]

export function WeeklySurveyMixChart({ weeks }: { weeks: SurveyWeekColumn[] }) {
  const y = linear([0, 100], [MIX_H - M.bottom, M.top])
  const slot = (W - M.left - M.right) / Math.max(1, weeks.length)
  const barW = Math.min(36, slot * 0.72)

  return (
    <figure className="chart">
      <ul className="legend" aria-label="Surveys">
        {SURVEYS.map((s) => (
          <li key={s.id}>
            <span className="swatch" data-group={s.group} aria-hidden="true" />
            {s.label}
          </li>
        ))}
      </ul>
      <svg
        className="chart-svg"
        viewBox={`0 0 ${W} ${MIX_H}`}
        role="img"
        aria-label={`Weekly survey mix comparing Rubin (LSST) and ZTF across the last ${weeks.length} full weeks.`}
      >
        {PCT_TICKS.map((t) => (
          <g key={t}>
            <line className="grid" x1={M.left} x2={W - M.right} y1={y(t)} y2={y(t)} />
            <text className="tick" x={M.left - 8} y={y(t)} textAnchor="end" dominantBaseline="middle">
              {t}%
            </text>
          </g>
        ))}
        {weeks.map((w, i) => {
          const x = M.left + i * slot + (slot - barW) / 2
          const startLabel = formatDay(mjdToDate(w.start))
          const endLabel = formatDay(mjdToDate(w.end))
          const rangeLabel = `${startLabel}–${endLabel}`
          const segs = SURVEYS.filter((s) => (s.id === 'lsst' ? w.lsst : w.ztf) > 0)
          let below = 0
          return (
            <g key={w.start}>
              {segs.map((s, j) => {
                const n = s.id === 'lsst' ? w.lsst : w.ztf
                const pct = s.id === 'lsst' ? w.lsstPct : w.ztfPct
                const bottomY = y(below)
                const topY = y(below + pct)
                below += pct
                const h = Math.max(1, bottomY - topY - (j > 0 ? GAP : 0))
                const tip = `${rangeLabel} · ${s.label}: ${Math.round(pct)}% (${n} of ${w.total})`
                return j === segs.length - 1 ? (
                  <path key={s.id} className="seg" data-group={s.group} d={roundedTopBar(x, topY, barW, h)}>
                    <title>{tip}</title>
                  </path>
                ) : (
                  <rect key={s.id} className="seg" data-group={s.group} x={x} y={topY} width={barW} height={h}>
                    <title>{tip}</title>
                  </rect>
                )
              })}
              <text className="tick" x={x + barW / 2} y={MIX_H - M.bottom + 18} textAnchor="middle">
                {endLabel}
              </text>
            </g>
          )
        })}
        <line className="axis" x1={M.left} x2={W - M.right} y1={MIX_H - M.bottom} y2={MIX_H - M.bottom} />
      </svg>
      <figcaption className="muted small">
        100%-stacked share of new objects from Rubin Observatory (LSST, southern hemisphere) vs. ZTF (Palomar, northern
        hemisphere) over the last {weeks.length} full 7-day weeks.
      </figcaption>
      <details className="table-view">
        <summary>Data table ({weeks.length} weeks)</summary>
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th scope="col">Week (UTC)</th>
                <th scope="col" className="num">
                  Rubin (LSST)
                </th>
                <th scope="col" className="num">
                  ZTF
                </th>
                <th scope="col" className="num">
                  Total
                </th>
              </tr>
            </thead>
            <tbody>
              {[...weeks].reverse().map((w) => (
                <tr key={w.start}>
                  <th scope="row">
                    {mjdToDate(w.start).toISOString().slice(0, 10)} – {mjdToDate(w.end).toISOString().slice(0, 10)}
                  </th>
                  <td className="num">
                    {w.lsst} ({Math.round(w.lsstPct)}%)
                  </td>
                  <td className="num">
                    {w.ztf} ({Math.round(w.ztfPct)}%)
                  </td>
                  <td className="num">{w.total}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </figure>
  )
}
