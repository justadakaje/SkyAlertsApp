import type { Metadata, Viewport } from 'next'
import Link from 'next/link'
import { connection } from 'next/server'
import { Suspense, type ReactNode } from 'react'

import { getLastUpdated } from '@/lib/data'
import { formatAgo, formatUtc } from '@/lib/format'

import './globals.css'

export const metadata: Metadata = {
  metadataBase: new URL('https://sky.henseler.app'),
  title: { default: 'Sky Alerts', template: '%s · Sky Alerts' },
  description:
    'What the sky did last night: supernovae, variable stars and more, from the ALeRCE broker (Rubin + ZTF).',
  openGraph: {
    siteName: 'Sky Alerts',
    type: 'website',
    url: 'https://sky.henseler.app',
    locale: 'en_US',
  },
  twitter: {
    card: 'summary_large_image',
  },
}

export const viewport: Viewport = {
  themeColor: [
    { media: '(prefers-color-scheme: dark)', color: '#070b16' },
    { media: '(prefers-color-scheme: light)', color: '#f5f6fa' },
  ],
}

export default async function RootLayout({ children }: { children: ReactNode }) {
  // The CSP nonce is per request (proxy.ts), so every page renders dynamically.
  await connection()
  return (
    <html lang="en">
      <body>
        <a className="skip-link" href="#main">
          Skip to content
        </a>
        <header className="site-header">
          <div className="wrap header-row">
            <Link href="/" className="brand">
              <svg viewBox="0 0 24 24" width="22" height="22" aria-hidden="true">
                <path className="brand-star" d="M12 2l2.2 6.8L21 11l-6.8 2.2L12 20l-2.2-6.8L3 11l6.8-2.2z" />
              </svg>
              Sky Alerts
            </Link>
            <nav aria-label="Main">
              <Link href="/">Events</Link>
              <Link href="/stats">Stats</Link>
              <Link href="/about">About</Link>
              <a href="/skyalerts-explainer.html">How It Works</a>
            </nav>
          </div>
        </header>
        <main id="main" className="wrap">
          {children}
        </main>
        <footer className="site-footer">
          <div className="wrap">
            <Suspense fallback={null}>
              <LastUpdated />
            </Suspense>
            <p>
              Alerts from the <a href="https://alerce.science">ALeRCE broker</a>, processing the Vera C. Rubin
              Observatory (LSST) and Zwicky Transient Facility (ZTF) streams. Classes are machine-learning
              predictions, not confirmed identifications.
            </p>
          </div>
        </footer>
      </body>
    </html>
  )
}

async function LastUpdated() {
  let t: number | null
  try {
    t = await getLastUpdated()
  } catch {
    return null // the footer never takes the page down
  }
  if (t === null) return null
  const d = new Date(t * 1000)
  return (
    <p>
      Data updated <time dateTime={d.toISOString()} title={formatUtc(d)}>{formatAgo(d, new Date())}</time>.
    </p>
  )
}
