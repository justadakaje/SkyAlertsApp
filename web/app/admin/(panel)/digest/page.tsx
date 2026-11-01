import type { Metadata } from 'next'

import { requireAdmin } from '@/lib/auth/server'

export const metadata: Metadata = { title: 'Digest' }

export default async function DigestPage() {
  await requireAdmin()
  return (
    <>
      <h1>Weekly digest</h1>
      <section className="panel">
        <p>Preview and send arrive with Phase 3 (weekly digest through Resend from sky.henseler.app).</p>
        <p className="muted">
          This page will show the next digest as it will be emailed, with a send button that writes to the audit log.
        </p>
      </section>
    </>
  )
}
