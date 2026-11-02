import { digestConfig, type DigestConfig } from '@/lib/auth/config'
import type { SearchParams } from '@/lib/filters'

import type { HealthLevel } from './health'

export const WEEK_END_RE = /^\d{4}-\d{2}-\d{2}$/
export const PREVIEW_TIMEOUT_MS = 15_000
export const SEND_TIMEOUT_MS = 30_000

export function isValidWeekEnd(v: unknown): v is string {
  return typeof v === 'string' && WEEK_END_RE.test(v)
}

/**
 * Validate `week_end` against `^\d{4}-\d{2}-\d{2}$` before building the
 * Content-Disposition filename. Returns null on any unexpected value.
 */
export function podcastFilename(weekEnd: unknown): string | null {
  return isValidWeekEnd(weekEnd) ? `sky-this-week-${weekEnd}.md` : null
}

/** Parse a numeric-only headliner count query parameter (`^\d{1,6}$`). */
export function parseHeadliners(raw: unknown): number | null {
  const s = Array.isArray(raw) ? raw[0] : raw
  if (typeof s !== 'string' || !/^\d{1,6}$/.test(s)) return null
  const n = Number(s)
  return Number.isSafeInteger(n) ? n : null
}

export type DigestNoticeCode = 'digest_sent' | 'digest_failed' | 'digest_unconfigured'

export interface AdminNotice {
  level: HealthLevel
  text: string
}

/** Build the redirect URL after a manual digest send attempt. */
export function sendDigestHref(code: DigestNoticeCode, headliners?: unknown): string {
  if (code === 'digest_sent' && typeof headliners === 'number' && Number.isInteger(headliners) && headliners >= 0) {
    return `/admin/digest?notice=digest_sent&headliners=${headliners}`
  }
  return `/admin/digest?notice=${code}`
}

/** Allowlisted notice banner for `/admin/digest`, with numeric-only headliner count on `digest_sent`. */
export function digestNotice(sp: SearchParams): AdminNotice | null {
  const code = Array.isArray(sp.notice) ? sp.notice[0] : sp.notice
  if (code === 'digest_sent') {
    const n = parseHeadliners(sp.headliners)
    const countText = n !== null ? ` (${n} ${n === 1 ? 'headliner' : 'headliners'})` : ''
    return {
      level: 'good',
      text: `Digest sent${countText}. Sends are idempotent: one send per UTC day.`,
    }
  }
  if (code === 'digest_failed') {
    return {
      level: 'critical',
      text: 'Digest send failed. Sends are limited to one send per UTC day; if the content changed after an earlier send today, Resend rejects the repeat.',
    }
  }
  if (code === 'digest_unconfigured') {
    return {
      level: 'critical',
      text: 'Digest is not configured (DIGEST_URL / DIGEST_TRIGGER_SECRET).',
    }
  }
  if (code === 'expired') {
    return {
      level: 'warning',
      text: 'That form had expired. Please try again.',
    }
  }
  return null
}

export interface DigestPreview {
  weekEnd: string
  subject: string
  headliners: number
  digestMarkdown: string
  podcastMarkdown: string
}

export function parseDigestPreview(raw: unknown): DigestPreview | null {
  if (!raw || typeof raw !== 'object') return null
  const o = raw as Record<string, unknown>
  if (o.status !== 'ok') return null
  if (!isValidWeekEnd(o.week_end)) return null
  if (typeof o.subject !== 'string') return null
  if (typeof o.headliners !== 'number' || !Number.isInteger(o.headliners) || o.headliners < 0) return null
  if (typeof o.digest_markdown !== 'string') return null
  if (typeof o.podcast_markdown !== 'string') return null
  return {
    weekEnd: o.week_end,
    subject: o.subject,
    headliners: o.headliners,
    digestMarkdown: o.digest_markdown,
    podcastMarkdown: o.podcast_markdown,
  }
}

export interface DigestSendResponse {
  weekEnd: string
  headliners: number
  id: string
}

export function parseDigestSendResponse(raw: unknown): DigestSendResponse | null {
  if (!raw || typeof raw !== 'object') return null
  const o = raw as Record<string, unknown>
  if (o.status !== 'sent') return null
  if (!isValidWeekEnd(o.week_end)) return null
  if (typeof o.headliners !== 'number' || !Number.isInteger(o.headliners) || o.headliners < 0) return null
  if (typeof o.id !== 'string' || !o.id) return null
  return {
    weekEnd: o.week_end,
    headliners: o.headliners,
    id: o.id,
  }
}

export type PreviewFetchResult =
  | { ok: true; data: DigestPreview }
  | { ok: false; reason: 'unconfigured' | 'failed'; status?: number }

/** POST `{DIGEST_URL}/api/preview/digest` with the bearer secret (15 s timeout, no-store). */
export async function fetchDigestPreview(cfg: DigestConfig | null = digestConfig()): Promise<PreviewFetchResult> {
  if (!cfg) return { ok: false, reason: 'unconfigured' }
  try {
    const res = await fetch(`${cfg.url}/api/preview/digest`, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${cfg.secret}`,
      },
      signal: AbortSignal.timeout(PREVIEW_TIMEOUT_MS),
      cache: 'no-store',
    })
    if (!res.ok) return { ok: false, reason: 'failed', status: res.status }
    const data = parseDigestPreview(await res.json())
    if (!data) return { ok: false, reason: 'failed', status: res.status }
    return { ok: true, data }
  } catch {
    return { ok: false, reason: 'failed' }
  }
}
