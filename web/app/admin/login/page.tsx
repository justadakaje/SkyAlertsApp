import type { Metadata } from 'next'
import { redirect } from 'next/navigation'

import { adminConfig } from '@/lib/auth/config'
import { currentAdmin } from '@/lib/auth/server'
import type { SearchParams } from '@/lib/filters'

export const metadata: Metadata = { title: 'Admin sign-in', robots: { index: false, follow: false } }

// Only known codes map to text; nothing from the query string is echoed.
const ERRORS: Record<string, string> = {
  denied: 'That GitHub account is not allowed to use admin.',
  cancelled: 'Sign-in was cancelled on GitHub.',
  state: 'Sign-in expired or was tampered with. Please try again.',
  github: 'GitHub sign-in failed. Please try again.',
  config: 'Admin is not configured on this deployment.',
}

export default async function LoginPage({ searchParams }: { searchParams: Promise<SearchParams> }) {
  if (await currentAdmin()) redirect('/admin')
  const sp = await searchParams
  const code = typeof sp.error === 'string' ? sp.error : ''
  const configured = adminConfig() !== null

  return (
    <section className="hero narrow">
      <h1>Admin</h1>
      <p className="lede">Owner only. Sign in with the allowlisted GitHub account.</p>
      {ERRORS[code] ? (
        <p className="notice" data-level="critical" role="alert">
          {ERRORS[code]}
        </p>
      ) : null}
      {configured ? (
        <p>
          <a className="button" href="/api/auth/github/start">
            Sign in with GitHub
          </a>
        </p>
      ) : (
        <p className="muted">Admin is not configured on this deployment.</p>
      )}
    </section>
  )
}
