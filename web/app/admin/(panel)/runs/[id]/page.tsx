import type { Metadata } from 'next'
import Link from 'next/link'
import { notFound } from 'next/navigation'
import type { ReactNode } from 'react'

import { formatDuration, RunStatusPill, When } from '@/components/admin/AdminBits'
import { getAdminPool } from '@/lib/admin/db'
import { getRun } from '@/lib/admin/queries'
import { requireAdmin } from '@/lib/auth/server'
import { formatUtc } from '@/lib/format'

type Params = Promise<{ id: string }>

export async function generateMetadata({ params }: { params: Params }): Promise<Metadata> {
  const { id } = await params
  return /^\d{1,12}$/.test(id) ? { title: `Run #${id}` } : {}
}

export default async function RunPage({ params }: { params: Params }) {
  await requireAdmin()
  const { id } = await params
  if (!/^\d{1,12}$/.test(id)) notFound()
  const run = await getRun(getAdminPool(), Number(id))
  if (!run) notFound()
  const now = new Date()
  const rows: [string, ReactNode][] = [
    ['Status', <RunStatusPill key="s" status={run.status} />],
    ['Trigger', run.trigger],
    ['Surveys', run.surveys.join(', ')],
    ['Started', <span key="st">{formatUtc(new Date(run.startedAt * 1000))} (<When unix={run.startedAt} now={now} />)</span>],
    ['Finished', run.finishedAt ? formatUtc(new Date(run.finishedAt * 1000)) : '—'],
    ['Duration', formatDuration(run.durationMs)],
    ['Requests', run.requests],
    ['Objects seen / upserted', `${run.objectsSeen} / ${run.objectsUpserted}`],
    ['Classifications upserted', run.classificationsUpserted],
    ['Objects enriched / points stored', `${run.objectsEnriched} / ${run.detectionsUpserted}`],
    ['Errors', run.errorCount],
  ]
  return (
    <>
      <p className="small">
        <Link href="/admin/runs">← All runs</Link>
      </p>
      <h1>Run #{run.id}</h1>
      <section className="panel">
        <dl className="kv">
          {rows.map(([k, v]) => (
            <div key={k}>
              <dt>{k}</dt>
              <dd>{v}</dd>
            </div>
          ))}
        </dl>
      </section>
      <section className="panel" aria-labelledby="errors-heading">
        <h2 id="errors-heading">Errors</h2>
        {run.errorCount ? (
          // Upstream error text is rendered as escaped text, never HTML.
          <pre className="code-block">{JSON.stringify(run.errors, null, 2)}</pre>
        ) : (
          <p className="muted">None.</p>
        )}
      </section>
    </>
  )
}
