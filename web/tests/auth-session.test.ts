import { describe, expect, it } from 'vitest'

import {
  csrfToken,
  decodeSession,
  encodeSession,
  newSession,
  SESSION_TTL_S,
  statesMatch,
  verifyCsrf,
} from '@/lib/auth/session'

const SECRET = 'test-only-secret-0123456789abcdef0123456789'
const NOW = 1_793_000_000

describe('session cookie', () => {
  it('round-trips a valid session', async () => {
    const s = newSession(16056018, 'justadakaje', NOW)
    const token = await encodeSession(s, SECRET)
    expect(await decodeSession(token, SECRET, NOW + 10)).toEqual(s)
  })

  it('rejects a wrong secret, tampering and garbage', async () => {
    const token = await encodeSession(newSession(1, 'a', NOW), SECRET)
    const [payload, sig] = token.split('.')
    const forged = Buffer.from(JSON.stringify({ ...JSON.parse(Buffer.from(payload!, 'base64url').toString()), uid: 2 })).toString('base64url')
    expect(await decodeSession(token, `${SECRET}x`, NOW)).toBeNull()
    expect(await decodeSession(`${forged}.${sig}`, SECRET, NOW)).toBeNull()
    expect(await decodeSession(`${payload}.${sig}.x`, SECRET, NOW)).toBeNull()
    expect(await decodeSession(`${payload}.not*base64`, SECRET, NOW)).toBeNull()
    expect(await decodeSession('', SECRET, NOW)).toBeNull()
    expect(await decodeSession(undefined, SECRET, NOW)).toBeNull()
    expect(await decodeSession('a'.repeat(2000), SECRET, NOW)).toBeNull()
  })

  it('expires, and refuses sessions issued in the future or longer than the TTL', async () => {
    const s = newSession(1, 'a', NOW)
    const token = await encodeSession(s, SECRET)
    expect(await decodeSession(token, SECRET, NOW + SESSION_TTL_S)).toBeNull()
    expect(await decodeSession(token, SECRET, NOW - 3600)).toBeNull()
    const long = await encodeSession({ ...s, exp: NOW + SESSION_TTL_S * 10 }, SECRET)
    expect(await decodeSession(long, SECRET, NOW)).toBeNull()
  })

  it('rejects well-signed payloads of the wrong shape', async () => {
    const bad = await encodeSession({ uid: -5, login: 'x', sid: 'short', iat: NOW, exp: NOW + 60 }, SECRET)
    expect(await decodeSession(bad, SECRET, NOW)).toBeNull()
  })
})

describe('csrf', () => {
  it('binds tokens to the sign-in', async () => {
    const a = newSession(1, 'a', NOW)
    const b = newSession(1, 'a', NOW)
    const t = await csrfToken(a, SECRET)
    expect(await verifyCsrf(t, a, SECRET)).toBe(true)
    expect(await verifyCsrf(t, b, SECRET)).toBe(false)
    expect(await verifyCsrf(null, a, SECRET)).toBe(false)
    expect(await verifyCsrf('', a, SECRET)).toBe(false)
  })

  it('cannot be swapped with a session signature', async () => {
    const s = newSession(1, 'a', NOW)
    const sig = (await encodeSession(s, SECRET)).split('.')[1]
    expect(await verifyCsrf(sig, s, SECRET)).toBe(false)
  })
})

describe('oauth state', () => {
  it('matches only identical, present values', async () => {
    expect(await statesMatch('abc', 'abc')).toBe(true)
    expect(await statesMatch('abc', 'abd')).toBe(false)
    expect(await statesMatch(undefined, 'abc')).toBe(false)
    expect(await statesMatch('abc', null)).toBe(false)
    expect(await statesMatch('', '')).toBe(false)
  })
})
