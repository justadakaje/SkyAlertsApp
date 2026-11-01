// Display formatting. Everything renders in UTC so server output is deterministic.

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

export function formatUtc(date: Date): string {
  const iso = date.toISOString()
  return `${iso.slice(0, 10)} ${iso.slice(11, 16)} UTC`
}

export function formatDay(date: Date): string {
  return `${MONTHS[date.getUTCMonth()]} ${date.getUTCDate()}`
}

export function formatMonth(date: Date): string {
  return `${MONTHS[date.getUTCMonth()]} ${date.getUTCFullYear()}`
}

export function formatAgo(date: Date, now: Date): string {
  const minutes = Math.round((now.getTime() - date.getTime()) / 60_000)
  if (minutes < 1) return 'just now'
  if (minutes < 60) return `${minutes} min ago`
  const hours = Math.round(minutes / 60)
  if (hours < 48) return `${hours} h ago`
  const days = Math.round(hours / 24)
  if (days < 60) return `${days} days ago`
  const months = Math.round(days / 30.4)
  if (months < 24) return `${months} months ago`
  return `${Math.round(days / 365.25)} years ago`
}

export function formatProbability(p: number | null): string {
  if (p === null) return '—'
  if (p > 0 && p < 0.01) return '<1%'
  return `${Math.round(p * 100)}%`
}

export function formatCount(n: number): string {
  if (n < 1000) return String(n)
  if (n < 10_000) return `${(n / 1000).toFixed(1).replace(/\.0$/, '')}K`
  if (n < 1_000_000) return `${Math.round(n / 1000)}K`
  return `${(n / 1_000_000).toFixed(1).replace(/\.0$/, '')}M`
}
