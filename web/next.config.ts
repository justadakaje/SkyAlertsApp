import type { NextConfig } from 'next'

// Static security headers on every response (CSP is per request, in proxy.ts).
export const securityHeaders = [
  { key: 'Strict-Transport-Security', value: 'max-age=63072000; includeSubDomains' },
  { key: 'X-Content-Type-Options', value: 'nosniff' },
  { key: 'X-Frame-Options', value: 'DENY' },
  { key: 'Referrer-Policy', value: 'strict-origin-when-cross-origin' },
  {
    key: 'Permissions-Policy',
    value: 'camera=(), microphone=(), geolocation=(), payment=(), usb=(), browsing-topics=()',
  },
  { key: 'Cross-Origin-Opener-Policy', value: 'same-origin' },
]

// Static CSP for /skyalerts-explainer.html, which is self-contained (inline JS/CSS,
// data: SVG favicon and canvas-export images, embedded data: fonts, no network calls).
export const explainerCsp = [
  "default-src 'none'",
  "script-src 'unsafe-inline'",
  "style-src 'unsafe-inline'",
  "img-src 'self' data:",
  "font-src 'self' data:",
  "connect-src 'none'",
  "base-uri 'none'",
  "form-action 'none'",
  "frame-ancestors 'none'",
].join('; ')

const nextConfig: NextConfig = {
  poweredByHeader: false,
  reactStrictMode: true,
  async headers() {
    const noindex = [{ key: 'X-Robots-Tag', value: 'noindex, nofollow' }]
    return [
      { source: '/:path*', headers: securityHeaders },
      {
        source: '/skyalerts-explainer.html',
        headers: [{ key: 'Content-Security-Policy', value: explainerCsp }],
      },
      { source: '/admin/:path*', headers: noindex },
      { source: '/admin', headers: noindex },
      { source: '/api/auth/:path*', headers: noindex },
    ]
  },
}

export default nextConfig
