// Stateless admin sessions: an HMAC-SHA256-signed cookie value. Pure Web Crypto,
// no dependencies. Revoke every session by rotating ADMIN_SESSION_SECRET, or a
// single user by removing their id from ADMIN_GITHUB_IDS (checked per request).

export const SESSION_TTL_S = 8 * 60 * 60
const CLOCK_SKEW_S = 60

export interface Session {
  uid: number // GitHub numeric user id
  login: string
  sid: string // random per sign-in; binds the CSRF token
  iat: number // unix seconds
  exp: number
}

const enc = new TextEncoder()

function b64url(bytes: ArrayBuffer | Uint8Array): string {
  return Buffer.from(bytes instanceof Uint8Array ? bytes : new Uint8Array(bytes)).toString('base64url')
}

function fromB64url(s: string): Uint8Array<ArrayBuffer> | null {
  if (!/^[A-Za-z0-9_-]*$/.test(s)) return null
  return Uint8Array.from(Buffer.from(s, 'base64url'))
}

async function key(secret: string): Promise<CryptoKey> {
  return crypto.subtle.importKey('raw', enc.encode(secret), { name: 'HMAC', hash: 'SHA-256' }, false, [
    'sign',
    'verify',
  ])
}

// Every signature carries a purpose label, so a token minted for one use can't be replayed as another.
async function sign(secret: string, purpose: string, data: string): Promise<string> {
  return b64url(await crypto.subtle.sign('HMAC', await key(secret), enc.encode(`${purpose}\u0000${data}`)))
}

/** Constant-time check (crypto.subtle.verify) of a base64url signature. */
async function verify(secret: string, purpose: string, data: string, sig: string): Promise<boolean> {
  const bytes = fromB64url(sig)
  if (!bytes || bytes.length !== 32) return false
  return crypto.subtle.verify('HMAC', await key(secret), bytes, enc.encode(`${purpose}\u0000${data}`))
}

export function randomToken(bytes = 32): string {
  return b64url(crypto.getRandomValues(new Uint8Array(bytes)))
}

export function newSession(uid: number, login: string, now = Math.floor(Date.now() / 1000)): Session {
  return { uid, login, sid: randomToken(16), iat: now, exp: now + SESSION_TTL_S }
}

export async function encodeSession(s: Session, secret: string): Promise<string> {
  const payload = b64url(enc.encode(JSON.stringify(s)))
  return `${payload}.${await sign(secret, 'session.v1', payload)}`
}

export async function decodeSession(
  token: string | undefined,
  secret: string,
  now = Math.floor(Date.now() / 1000),
): Promise<Session | null> {
  if (!token || token.length > 1024) return null
  const [payload, sig, extra] = token.split('.')
  if (!payload || !sig || extra !== undefined) return null
  if (!(await verify(secret, 'session.v1', payload, sig))) return null
  let s: unknown
  try {
    s = JSON.parse(Buffer.from(payload, 'base64url').toString('utf8'))
  } catch {
    return null
  }
  if (!isSession(s)) return null
  if (s.exp <= now || s.iat > now + CLOCK_SKEW_S || s.exp - s.iat > SESSION_TTL_S) return null
  return s
}

function isSession(v: unknown): v is Session {
  if (typeof v !== 'object' || v === null) return false
  const s = v as Record<string, unknown>
  return (
    Number.isSafeInteger(s.uid) &&
    (s.uid as number) > 0 &&
    typeof s.login === 'string' &&
    s.login.length <= 64 &&
    typeof s.sid === 'string' &&
    s.sid.length >= 16 &&
    Number.isSafeInteger(s.iat) &&
    Number.isSafeInteger(s.exp)
  )
}

/** CSRF token for admin forms, bound to this sign-in (sid). */
export function csrfToken(s: Session, secret: string): Promise<string> {
  return sign(secret, 'csrf.v1', s.sid)
}

export async function verifyCsrf(token: unknown, s: Session, secret: string): Promise<boolean> {
  return typeof token === 'string' && token.length <= 128 && verify(secret, 'csrf.v1', s.sid, token)
}

/** OAuth state: random value in a short-lived cookie, compared on the callback. */
export async function statesMatch(cookieState: string | undefined, queryState: string | null): Promise<boolean> {
  if (!cookieState || !queryState || cookieState.length > 128 || queryState.length > 128) return false
  // Compare HMACs so the comparison time doesn't depend on where the strings differ.
  const k = randomToken()
  return (await sign(k, 'state', cookieState)) === (await sign(k, 'state', queryState))
}
