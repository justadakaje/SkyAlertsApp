// Astronomy helpers: time (MJD) and sky coordinates. Pure functions, no I/O.

export const MJD_UNIX_EPOCH = 40587
const DAY_MS = 86_400_000
const RAD = Math.PI / 180

export function mjdToDate(mjd: number): Date {
  return new Date((mjd - MJD_UNIX_EPOCH) * DAY_MS)
}

export function dateToMjd(date: Date): number {
  return date.getTime() / DAY_MS + MJD_UNIX_EPOCH
}

/** Right ascension in degrees -> "hh:mm:ss.ss". */
export function formatRa(deg: number): string {
  const total = Math.round((((deg % 360) + 360) % 360) * 24_000) % 8_640_000 // centiseconds of time
  const h = Math.floor(total / 360_000)
  const m = Math.floor((total % 360_000) / 6_000)
  const s = (total % 6_000) / 100
  return `${pad(h)}:${pad(m)}:${s.toFixed(2).padStart(5, '0')}`
}

/** Declination in degrees -> "+dd:mm:ss.s". */
export function formatDec(deg: number): string {
  const sign = deg < 0 ? '-' : '+'
  const total = Math.round(Math.abs(deg) * 36_000) // deciseconds of arc
  const d = Math.floor(total / 36_000)
  const m = Math.floor((total % 36_000) / 600)
  const s = (total % 600) / 10
  return `${sign}${pad(d)}:${pad(m)}:${s.toFixed(1).padStart(4, '0')}`
}

// J2000 north galactic pole and the galactic longitude of the north celestial pole.
const NGP_RA = 192.85948
const NGP_DEC = 27.12825
const NCP_L = 122.93192

/** Galactic (l, b) -> equatorial J2000 (ra, dec), all in degrees. */
export function galacticToEquatorial(l: number, b: number): { ra: number; dec: number } {
  const sinDecNgp = Math.sin(NGP_DEC * RAD)
  const cosDecNgp = Math.cos(NGP_DEC * RAD)
  const dl = (NCP_L - l) * RAD
  const sinB = Math.sin(b * RAD)
  const cosB = Math.cos(b * RAD)
  const dec = Math.asin(sinDecNgp * sinB + cosDecNgp * cosB * Math.cos(dl)) / RAD
  const ra = NGP_RA + Math.atan2(cosB * Math.sin(dl), cosDecNgp * sinB - sinDecNgp * cosB * Math.cos(dl)) / RAD
  return { ra: ((ra % 360) + 360) % 360, dec }
}

function pad(n: number): string {
  return String(n).padStart(2, '0')
}
