import { formatDec, formatRa, galacticToEquatorial } from '@/lib/astro'

const W = 360
const H = 180
const PAD = 22

// Equirectangular all-sky map, RA increasing to the left as on a star chart.
function project(ra: number, dec: number): [number, number] {
  return [PAD + ((360 - ra) / 360) * W, PAD + ((90 - dec) / 180) * H]
}

function galacticPlane(): string[] {
  const segments: string[] = []
  let current: string[] = []
  let lastX: number | null = null
  for (let l = 0; l <= 360; l += 2) {
    const { ra, dec } = galacticToEquatorial(l, 0)
    const [x, y] = project(ra, dec)
    if (lastX !== null && Math.abs(x - lastX) > W / 2) {
      segments.push(current.join(' '))
      current = []
    }
    current.push(`${current.length ? 'L' : 'M'}${x.toFixed(1)},${y.toFixed(1)}`)
    lastX = x
  }
  if (current.length) segments.push(current.join(' '))
  return segments
}

const PLANE = galacticPlane()

export function SkyMap({ ra, dec }: { ra: number; dec: number }) {
  const [x, y] = project(ra, dec)
  return (
    <figure className="chart">
      <svg
        className="chart-svg sky"
        viewBox={`0 0 ${W + PAD * 2} ${H + PAD * 2}`}
        role="img"
        aria-label={`Sky position: right ascension ${formatRa(ra)}, declination ${formatDec(dec)}`}
      >
        <rect className="sky-bg" x={PAD} y={PAD} width={W} height={H} rx={6} />
        {[-60, -30, 0, 30, 60].map((d) => (
          <g key={`d${d}`}>
            <line className={d === 0 ? 'axis' : 'grid'} x1={PAD} x2={PAD + W} y1={project(0, d)[1]} y2={project(0, d)[1]} />
            <text className="tick" x={PAD - 4} y={project(0, d)[1]} textAnchor="end" dominantBaseline="middle">
              {d > 0 ? `+${d}` : d}°
            </text>
          </g>
        ))}
        {[0, 60, 120, 180, 240, 300, 360].map((r) => (
          <g key={`r${r}`}>
            <line className="grid" x1={project(r, 0)[0]} x2={project(r, 0)[0]} y1={PAD} y2={PAD + H} />
            <text className="tick" x={project(r, 0)[0]} y={PAD + H + 14} textAnchor="middle">
              {r / 15}h
            </text>
          </g>
        ))}
        {PLANE.map((d) => (
          <path key={d} className="galactic" d={d} />
        ))}
        <circle className="target-ring" cx={x} cy={y} r={9} />
        <circle className="target" cx={x} cy={y} r={4}>
          <title>{`RA ${formatRa(ra)}, Dec ${formatDec(dec)}`}</title>
        </circle>
      </svg>
      <figcaption className="muted small">
        Whole sky, right ascension (hours) across, declination (degrees) up. The dashed curve is the
        plane of the Milky Way.
      </figcaption>
    </figure>
  )
}
