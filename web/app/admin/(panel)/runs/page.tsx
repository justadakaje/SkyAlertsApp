import type { Metadata } from 'next'

import { RunsTable } from '@/components/admin/AdminBits'
import { getAdminPool } from '@/lib/admin/db'
import { listRuns } from '@/lib/admin/queries'
import { requireAdmin } from '@/lib/auth/server'

export const metadata: Metadata = { title: 'Runs' }

export default async function RunsPage() {
  await requireAdmin()
  const runs = await listRuns(getAdminPool(), 100)
  return (
    <>
      <h1>Ingest runs</h1>
      <p className="muted">The last {runs.length} runs, newest first. Open a run for its error details.</p>
      <section className="panel">{runs.length ? <RunsTable runs={runs} now={new Date()} /> : <p className="muted">No runs yet.</p>}</section>
    </>
  )
}
