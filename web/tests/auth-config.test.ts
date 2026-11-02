import { describe, expect, it } from 'vitest'

import { adminConfig, digestConfig, parseAllowlist, SESSION_COOKIE, triggerConfig } from '@/lib/auth/config'

const base = {
  GITHUB_CLIENT_ID: 'Iv1.test',
  GITHUB_CLIENT_SECRET: 'test-client-secret',
  ADMIN_SESSION_SECRET: 'x'.repeat(32),
  ADMIN_GITHUB_IDS: '16056018',
}

describe('parseAllowlist', () => {
  it('keeps numeric ids only', () => {
    expect([...parseAllowlist('16056018, 42 ,justadakaje,0,-1,1e5,')]).toEqual([16056018, 42])
    expect(parseAllowlist(undefined).size).toBe(0)
  })
})

describe('adminConfig', () => {
  it('loads a complete config', () => {
    expect(adminConfig(base)?.allowedIds).toEqual(new Set([16056018]))
  })

  it('fails closed on anything missing or weak', () => {
    expect(adminConfig({ ...base, GITHUB_CLIENT_ID: '' })).toBeNull()
    expect(adminConfig({ ...base, GITHUB_CLIENT_SECRET: undefined })).toBeNull()
    expect(adminConfig({ ...base, ADMIN_SESSION_SECRET: 'short' })).toBeNull()
    expect(adminConfig({ ...base, ADMIN_GITHUB_IDS: 'justadakaje' })).toBeNull()
  })

  it('uses a __Host- cookie (Secure, path=/, no Domain)', () => {
    expect(SESSION_COOKIE.startsWith('__Host-')).toBe(true)
  })
})

describe('triggerConfig', () => {
  const t = { MANUAL_TRIGGER_URL: 'https://skyalerts-ingest.vercel.app/api/manual/ingest', MANUAL_TRIGGER_SECRET: 's'.repeat(32) }

  it('carries an optional Vercel protection-bypass secret', () => {
    expect(triggerConfig({ ...t, MANUAL_TRIGGER_BYPASS: 'b'.repeat(32) })?.bypass).toBe('b'.repeat(32))
    expect(triggerConfig({ ...t, MANUAL_TRIGGER_BYPASS: '  ' })?.bypass).toBeNull()
    expect(triggerConfig({ ...t, MANUAL_TRIGGER_BYPASS: 'short' })).toBeNull()
  })

  it('requires https (localhost excepted) and a long secret', () => {
    expect(triggerConfig(t)).toEqual({ url: t.MANUAL_TRIGGER_URL, secret: t.MANUAL_TRIGGER_SECRET, bypass: null })
    expect(triggerConfig({ ...t, MANUAL_TRIGGER_URL: 'http://example.com/x' })).toBeNull()
    expect(triggerConfig({ ...t, MANUAL_TRIGGER_URL: 'http://localhost:8000/api/manual/ingest' })).not.toBeNull()
    expect(triggerConfig({ ...t, MANUAL_TRIGGER_URL: 'not a url' })).toBeNull()
    expect(triggerConfig({ ...t, MANUAL_TRIGGER_SECRET: 'short' })).toBeNull()
  })
})

describe('digestConfig', () => {
  const d = { DIGEST_URL: 'https://skyalerts-digest.vercel.app', DIGEST_TRIGGER_SECRET: 'd'.repeat(32) }

  it('requires https (or localhost/127.0.0.1) and a >=32-char secret, stripping trailing slashes', () => {
    expect(digestConfig(d)).toEqual({ url: 'https://skyalerts-digest.vercel.app', secret: d.DIGEST_TRIGGER_SECRET })
    expect(digestConfig({ ...d, DIGEST_URL: 'https://skyalerts-digest.vercel.app///' })?.url).toBe(
      'https://skyalerts-digest.vercel.app',
    )
    expect(digestConfig({ ...d, DIGEST_URL: 'http://localhost:8001' })?.url).toBe('http://localhost:8001')
    expect(digestConfig({ ...d, DIGEST_URL: 'http://127.0.0.1:8001/' })?.url).toBe('http://127.0.0.1:8001')
  })

  it('fails closed on missing, insecure, or short values', () => {
    expect(digestConfig({})).toBeNull()
    expect(digestConfig({ ...d, DIGEST_URL: '' })).toBeNull()
    expect(digestConfig({ ...d, DIGEST_URL: 'http://skyalerts-digest.vercel.app' })).toBeNull()
    expect(digestConfig({ ...d, DIGEST_URL: 'not-a-url' })).toBeNull()
    expect(digestConfig({ ...d, DIGEST_TRIGGER_SECRET: 'x'.repeat(31) })).toBeNull()
  })
})
