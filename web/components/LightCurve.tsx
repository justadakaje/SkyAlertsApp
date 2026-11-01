import { mjdToDate } from '@/lib/astro'
import { linear, niceTicks } from '@/lib/chart'
import { formatDay, formatMonth, formatUtc } from '@/lib/format'
import type { CurveModel, CurvePoint } from '@/lib/lightcurve'

const W = 720
const M = { top: 14, right: 16, bottom: 34, left: 56 }
const OVERLAY_H = 300
const PANEL_H = 120

const SHAPES: Record<string, 'circle' | 'square' | 'triangle'> = { g: 'circle', r: 'square', i: 'triangle' }

export function LightCurve({ model, label }: { model: CurveModel; label: string }) {
  const panels = model.layout === 'overlay' ? [model.bands] : model.bands.map((b) => [b])
  const panelH = model.layout === 'overlay' ? OVERLAY_H : PANEL_H
  const x = linear(model.xDomain, [M.left, W - M.right])
  const xTicks = timeTicks(model.xDomain)
  const yTicks = niceTicks(model.yDomain[0], model.yDomain[1], model.layout === 'overlay' ? 5 : 3)
  const counts = new Map(model.bands.map((b) => [b, model.points.filter((p) => p.band === b).length]))

  return (
    <figure className="chart">
      {model.layout === 'overlay' && model.bands.length > 1 ? (
        <ul className="legend" aria-label="Bands">
          {model.bands.map((b) => (
            <li key={b}>
              <svg width="14" height="14" viewBox="-7 -7 14 14" aria-hidden="true">
                <Marker band={b} cx={0} cy={0} shape={SHAPES[b] ?? 'circle'} />
              </svg>
              {b} band <span className="muted">({counts.get(b)})</span>
            </li>
          ))}
        </ul>
      ) : null}
      {panels.map((bands, i) => {
        const top = M.top
        const bottom = panelH - M.bottom
        const y = linear(model.yDomain, model.invertY ? [top, bottom] : [bottom, top])
        const pts = model.points.filter((p) => bands.includes(p.band))
        const isLast = i === panels.length - 1
        const name = bands.length === 1 ? `${bands[0]} band` : 'all bands'
        return (
          <svg
            key={bands.join()}
            className="chart-svg"
            viewBox={`0 0 ${W} ${panelH}`}
            role="img"
            aria-label={`${label}: ${name}, ${pts.length} points. ${model.yLabel}.`}
          >
            {yTicks.map((t) => (
              <g key={t}>
                <line className="grid" x1={M.left} x2={W - M.right} y1={y(t)} y2={y(t)} />
                <text className="tick" x={M.left - 8} y={y(t)} textAnchor="end" dominantBaseline="middle">
                  {fmtY(t, model.kind)}
                </text>
              </g>
            ))}
            {model.kind === 'flux' ? (
              <line className="baseline" x1={M.left} x2={W - M.right} y1={y(0)} y2={y(0)} />
            ) : null}
            {xTicks.map(({ mjd, label: tl }) => (
              <g key={mjd}>
                <line className="axis" x1={x(mjd)} x2={x(mjd)} y1={bottom} y2={bottom + 4} />
                {isLast ? (
                  <text className="tick" x={x(mjd)} y={bottom + 18} textAnchor="middle">
                    {tl}
                  </text>
                ) : null}
              </g>
            ))}
            <line className="axis" x1={M.left} x2={W - M.right} y1={bottom} y2={bottom} />
            {model.layout === 'panels' ? (
              <text className="panel-label" x={M.left + 6} y={top + 12}>
                {bands[0]} band · {pts.length}
              </text>
            ) : null}
            {pts.map((p) =>
              p.err ? (
                <line
                  key={`e${p.mjd}${p.band}`}
                  className={`errbar band-${safeBand(p.band)}`}
                  x1={x(p.mjd)}
                  x2={x(p.mjd)}
                  y1={y(p.y - p.err)}
                  y2={y(p.y + p.err)}
                />
              ) : null,
            )}
            {pts.map((p) => (
              <g key={`p${p.mjd}${p.band}`} className="hit">
                <Marker
                  band={p.band}
                  cx={x(p.mjd)}
                  cy={y(p.y)}
                  shape={model.layout === 'overlay' ? (SHAPES[p.band] ?? 'circle') : 'circle'}
                />
                <circle className="hit-target" cx={x(p.mjd)} cy={y(p.y)} r={9}>
                  <title>{pointTitle(p, model.kind)}</title>
                </circle>
              </g>
            ))}
          </svg>
        )
      })}
      <figcaption className="muted small">
        {model.yLabel}. Times in UTC. Hover a point for its value.
        {model.skippedNegative
          ? ` ${model.skippedNegative} fainter-than-reference detections have no magnitude and are not shown.`
          : ''}
      </figcaption>
      <details className="table-view">
        <summary>Data table ({model.points.length} points)</summary>
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th scope="col">Time (UTC)</th>
                <th scope="col">MJD</th>
                <th scope="col">Band</th>
                <th scope="col">{model.kind === 'mag' ? 'Magnitude' : 'Flux (µJy)'}</th>
                <th scope="col">Error</th>
              </tr>
            </thead>
            <tbody>
              {model.points.map((p) => (
                <tr key={`${p.mjd}${p.band}`}>
                  <td>{formatUtc(mjdToDate(p.mjd))}</td>
                  <td className="num">{p.mjd.toFixed(4)}</td>
                  <td>{p.band}</td>
                  <td className="num">{fmtY(p.y, model.kind)}</td>
                  <td className="num">{p.err === null ? '—' : fmtY(p.err, model.kind)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </figure>
  )
}

function Marker({ band, cx, cy, shape }: { band: string; cx: number; cy: number; shape: string }) {
  const cls = `marker band-${safeBand(band)}`
  if (shape === 'square') return <rect className={cls} x={cx - 4} y={cy - 4} width={8} height={8} />
  if (shape === 'triangle') return <path className={cls} d={`M${cx},${cy - 5} L${cx + 5},${cy + 4} L${cx - 5},${cy + 4} Z`} />
  return <circle className={cls} cx={cx} cy={cy} r={4} />
}

// Band names come from upstream data: only known single letters become class names.
function safeBand(band: string): string {
  return /^[ugrizy]$/.test(band) ? band : 'x'
}

function fmtY(v: number, kind: CurveModel['kind']): string {
  return kind === 'mag' ? v.toFixed(2) : v.toFixed(Math.abs(v) >= 100 ? 0 : 1)
}

function pointTitle(p: CurvePoint, kind: CurveModel['kind']): string {
  const unit = kind === 'mag' ? 'mag' : 'µJy'
  const err = p.err === null ? '' : ` ± ${fmtY(p.err, kind)}`
  return `${formatUtc(mjdToDate(p.mjd))} · ${p.band} band · ${fmtY(p.y, kind)}${err} ${unit}`
}

function timeTicks(domain: [number, number]): { mjd: number; label: string }[] {
  const span = domain[1] - domain[0]
  const fmt = span > 540 ? formatMonth : formatDay
  const seen = new Set<string>()
  return niceTicks(domain[0], domain[1], 6)
    .map((mjd) => ({ mjd, label: fmt(mjdToDate(mjd)) }))
    .filter(({ label }) => (seen.has(label) ? false : (seen.add(label), true)))
}
