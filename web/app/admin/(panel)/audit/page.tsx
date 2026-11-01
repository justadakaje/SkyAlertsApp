import type { Metadata } from 'next'

import { When } from '@/components/admin/AdminBits'
import { getAdminPool } from '@/lib/admin/db'
import { listAudit } from '@/lib/admin/queries'
import { requireAdmin } from '@/lib/auth/server'
import { formatUtc } from '@/lib/format'

export const metadata: Metadata = { title: 'Audit log' }

export default async function AuditPage() {
  await requireAdmin()
  const entries = await listAudit(getAdminPool(), 200)
  const now = new Date()
  return (
    <>
      <h1>Audit log</h1>
      <p className="muted">
        Every admin sign-in, denied sign-in, sign-out and action. Append-only: the admin database role can add entries
        but never change or delete them.
      </p>
      <section className="panel">
        {entries.length ? (
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th scope="col">When</th>
                  <th scope="col">Action</th>
                  <th scope="col">GitHub id</th>
                  <th scope="col">Target</th>
                  <th scope="col">Details</th>
                </tr>
              </thead>
              <tbody>
                {entries.map((e) => (
                  <tr key={e.id}>
                    <td title={formatUtc(new Date(e.at * 1000))}>
                      <When unix={e.at} now={now} />
                    </td>
                    <td>
                      <code>{e.action}</code>
                    </td>
                    <td className="num">{e.actor}</td>
                    <td>{e.target ?? '—'}</td>
                    <td>
                      <code className="small">{JSON.stringify(e.details)}</code>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="muted">No entries yet.</p>
        )}
      </section>
    </>
  )
}
