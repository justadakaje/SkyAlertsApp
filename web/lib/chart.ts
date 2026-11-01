// Small chart math shared by the SVG components. Pure functions.

export type Domain = [number, number]

export function linear(domain: Domain, range: [number, number]): (v: number) => number {
  const [d0, d1] = domain
  const [r0, r1] = range
  const span = d1 - d0 || 1
  return (v) => r0 + ((v - d0) / span) * (r1 - r0)
}

/** "Nice" round tick values covering the domain (1, 2, 5 x 10^n steps). */
export function niceTicks(min: number, max: number, count = 5): number[] {
  if (!Number.isFinite(min) || !Number.isFinite(max)) return []
  if (min === max) return [min]
  const lo = Math.min(min, max)
  const hi = Math.max(min, max)
  const raw = (hi - lo) / Math.max(1, count)
  const mag = 10 ** Math.floor(Math.log10(raw))
  const step = [1, 2, 5, 10].map((m) => m * mag).find((s) => s >= raw) ?? 10 * mag
  const ticks: number[] = []
  for (let t = Math.ceil(lo / step) * step; t <= hi + step * 1e-9; t += step) {
    ticks.push(Number(t.toFixed(10)))
  }
  return ticks
}

/** Pad a domain by a fraction of its span (or a fixed minimum when the span is ~0). */
export function padDomain(min: number, max: number, frac = 0.05, minPad = 0.1): Domain {
  const pad = Math.max((max - min) * frac, minPad)
  return [min - pad, max + pad]
}

/** SVG path for a bar with rounded top corners and a square base. */
export function roundedTopBar(x: number, y: number, w: number, h: number, r = 4): string {
  const rr = Math.max(0, Math.min(r, w / 2, h))
  return [
    `M${x},${y + h}`,
    `V${y + rr}`,
    `Q${x},${y} ${x + rr},${y}`,
    `H${x + w - rr}`,
    `Q${x + w},${y} ${x + w},${y + rr}`,
    `V${y + h}`,
    'Z',
  ].join(' ')
}
