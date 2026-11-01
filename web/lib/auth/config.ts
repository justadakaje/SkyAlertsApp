// Admin configuration from env. Anything missing or malformed disables admin
// entirely (fail closed): /admin then explains it isn't configured.

export interface AdminConfig {
  clientId: string
  clientSecret: string
  sessionSecret: string
  allowedIds: ReadonlySet<number>
}

type Env = Record<string, string | undefined>

export const SESSION_COOKIE = '__Host-skyalerts_admin'
export const STATE_COOKIE = '__Host-skyalerts_oauth'
export const STATE_TTL_S = 600

/** "16056018, 42" -> {16056018, 42}. Usernames are rejected: ids only (SPEC §Security). */
export function parseAllowlist(raw: string | undefined): Set<number> {
  const ids = new Set<number>()
  for (const part of (raw ?? '').split(',')) {
    const t = part.trim()
    if (/^[1-9]\d{0,15}$/.test(t) && Number.isSafeInteger(Number(t))) ids.add(Number(t))
  }
  return ids
}

export function adminConfig(env: Env = process.env): AdminConfig | null {
  const clientId = env.GITHUB_CLIENT_ID?.trim()
  const clientSecret = env.GITHUB_CLIENT_SECRET?.trim()
  const sessionSecret = env.ADMIN_SESSION_SECRET ?? ''
  const allowedIds = parseAllowlist(env.ADMIN_GITHUB_IDS)
  if (!clientId || !clientSecret || sessionSecret.length < 32 || allowedIds.size === 0) return null
  return { clientId, clientSecret, sessionSecret, allowedIds }
}

export interface TriggerConfig {
  url: string
  secret: string
}

/** Where /admin sends manual ingest re-runs (the ingest project's /api/manual/ingest). */
export function triggerConfig(env: Env = process.env): TriggerConfig | null {
  const url = env.MANUAL_TRIGGER_URL?.trim()
  const secret = env.MANUAL_TRIGGER_SECRET ?? ''
  if (!url || secret.length < 32) return null
  try {
    const u = new URL(url)
    if (u.protocol !== 'https:' && u.hostname !== 'localhost' && u.hostname !== '127.0.0.1') return null
  } catch {
    return null
  }
  return { url, secret }
}
