import { describe, expect, it } from 'vitest'

import robots from '@/app/robots'
import sitemap from '@/app/sitemap'
import nextConfig, { explainerCsp, securityHeaders } from '@/next.config'
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

  it('locks down the static explainer page with no network egress or framing', async () => {
    const directives = Object.fromEntries(
      explainerCsp.split('; ').map((d) => {
        const [name, ...rest] = d.split(' ')
        return [name, rest.join(' ')]
      }),
    )
    expect(directives['default-src']).toBe("'none'")
    expect(directives['connect-src']).toBe("'none'")
    expect(directives['frame-ancestors']).toBe("'none'")
    expect(directives['base-uri']).toBe("'none'")
    expect(directives['form-action']).toBe("'none'")

    const rules = await nextConfig.headers!()
    const explainerRule = rules.find((r) => r.source === '/skyalerts-explainer.html')
    expect(explainerRule?.headers).toEqual([{ key: 'Content-Security-Policy', value: explainerCsp }])
  })
})

describe('robots and sitemap', () => {
  it('allows public routes and disallows /admin and /api/', () => {
    const r = robots()
    expect(r.rules).toEqual({
      userAgent: '*',
      allow: '/',
      disallow: ['/admin', '/api/'],
    })
    expect(r.sitemap).toBe('https://sky.henseler.app/sitemap.xml')
  })

  it('lists /, /stats, /solar-system and /about with absolute URLs on https://sky.henseler.app', () => {
    const urls = sitemap().map((entry) => entry.url)
    expect(urls).toEqual([
      'https://sky.henseler.app/',
      'https://sky.henseler.app/stats',
      'https://sky.henseler.app/solar-system',
      'https://sky.henseler.app/about',
    ])
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
