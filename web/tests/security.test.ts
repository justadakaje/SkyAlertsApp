import { describe, expect, it } from 'vitest'

import { securityHeaders } from '@/next.config'
import { buildCsp } from '@/proxy'

describe('content security policy', () => {
  it('is strict in production', () => {
    const csp = buildCsp('abc123', false)
    expect(csp).toContain("script-src 'self' 'nonce-abc123' 'strict-dynamic'")
    expect(csp).toContain("style-src 'self' 'nonce-abc123'")
    expect(csp).toContain("frame-ancestors 'none'")
    expect(csp).toContain("object-src 'none'")
    expect(csp).toContain('upgrade-insecure-requests')
    expect(csp).not.toContain('unsafe-inline')
    expect(csp).not.toContain('unsafe-eval')
  })

  it('allows eval only in development', () => {
    expect(buildCsp('n', true)).toContain("'unsafe-eval'")
  })
})

describe('static security headers', () => {
  const h = Object.fromEntries(securityHeaders.map(({ key, value }) => [key, value]))

  it('sets HSTS for at least a year, with subdomains', () => {
    const maxAge = Number(/max-age=(\d+)/.exec(h['Strict-Transport-Security'] ?? '')?.[1])
    expect(maxAge).toBeGreaterThanOrEqual(31_536_000)
    expect(h['Strict-Transport-Security']).toContain('includeSubDomains')
  })

  it('sets the rest of the SPEC header list', () => {
    expect(h['X-Content-Type-Options']).toBe('nosniff')
    expect(h['Referrer-Policy']).toBeTruthy()
    expect(h['Permissions-Policy']).toContain('camera=()')
    expect(h['X-Frame-Options']).toBe('DENY')
  })
})
