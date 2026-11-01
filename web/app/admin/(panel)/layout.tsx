import type { Metadata } from 'next'
import Link from 'next/link'
import type { ReactNode } from 'react'

import { CsrfInput } from '@/components/admin/AdminBits'
import { requireAdmin } from '@/lib/auth/server'

import { signOut } from '../actions'

export const metadata: Metadata = { title: { default: 'Admin', template: '%s · Admin · Sky Alerts' }, robots: { index: false, follow: false } }
// The manual re-run call runs in after() and needs the full function lifetime.
export const maxDuration = 300

export default async function AdminLayout({ children }: { children: ReactNode }) {
  const { session, csrf } = await requireAdmin()
  return (
    <div className="admin">
      <div className="admin-bar">
        <nav aria-label="Admin">
          <Link href="/admin">Overview</Link>
          <Link href="/admin/runs">Runs</Link>
          <Link href="/admin/audit">Audit log</Link>
          <Link href="/admin/digest">Digest</Link>
          <Link href="/admin/settings">Settings</Link>
        </nav>
        <form action={signOut} className="admin-user">
          <span className="muted small">Signed in as {session.login || `#${session.uid}`}</span>
          <CsrfInput token={csrf} />
          <button type="submit" className="secondary">
            Sign out
          </button>
        </form>
      </div>
      {children}
    </div>
  )
}
