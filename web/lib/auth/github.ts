// Minimal GitHub OAuth (web application flow). No scopes are requested: we only
// need the numeric user id, and the access token is discarded after one call.

const TIMEOUT_MS = 8_000

export type Fetch = typeof fetch

export function authorizeUrl(clientId: string, redirectUri: string, state: string): string {
  const q = new URLSearchParams({ client_id: clientId, redirect_uri: redirectUri, state, allow_signup: 'false' })
  return `https://github.com/login/oauth/authorize?${q}`
}

export class GitHubAuthError extends Error {}

export async function exchangeCode(
  code: string,
  clientId: string,
  clientSecret: string,
  redirectUri: string,
  fetchImpl: Fetch = fetch,
): Promise<string> {
  const res = await fetchImpl('https://github.com/login/oauth/access_token', {
    method: 'POST',
    headers: { Accept: 'application/json', 'Content-Type': 'application/json' },
    body: JSON.stringify({ client_id: clientId, client_secret: clientSecret, code, redirect_uri: redirectUri }),
    signal: AbortSignal.timeout(TIMEOUT_MS),
    cache: 'no-store',
  })
  const body = (await res.json().catch(() => null)) as { access_token?: unknown; error?: unknown } | null
  if (!res.ok || !body || typeof body.access_token !== 'string' || !body.access_token) {
    // GitHub's error codes are safe to log; never log the code or token.
    throw new GitHubAuthError(`token exchange failed: ${res.status} ${typeof body?.error === 'string' ? body.error : ''}`.trim())
  }
  return body.access_token
}

export async function fetchUser(token: string, fetchImpl: Fetch = fetch): Promise<{ id: number; login: string }> {
  const res = await fetchImpl('https://api.github.com/user', {
    headers: {
      Accept: 'application/vnd.github+json',
      Authorization: `Bearer ${token}`,
      'X-GitHub-Api-Version': '2022-11-28',
      'User-Agent': 'skyalerts-admin',
    },
    signal: AbortSignal.timeout(TIMEOUT_MS),
    cache: 'no-store',
  })
  const body = (await res.json().catch(() => null)) as { id?: unknown; login?: unknown } | null
  if (!res.ok || !body || !Number.isSafeInteger(body.id) || (body.id as number) <= 0) {
    throw new GitHubAuthError(`user lookup failed: ${res.status}`)
  }
  const login = typeof body.login === 'string' ? body.login.slice(0, 64) : ''
  return { id: body.id as number, login }
}
