'use server'

import { cookies } from 'next/headers'
import { redirect } from 'next/navigation'
import { after } from 'next/server'

import { getAdminPool } from '@/lib/admin/db'
import { activeRun, insertAudit } from '@/lib/admin/queries'
import { SESSION_COOKIE, triggerConfig } from '@/lib/auth/config'
import { COOKIE_OPTS, log, requireAdminForm } from '@/lib/auth/server'

// Ingest takes up to ~4 min; leave the manual call room to finish under Vercel's 300 s.
const TRIGGER_TIMEOUT_MS = 290_000

/** Ask the ingest project to run now (trigger = manual). Audited before it's sent. */
export async function runIngestNow(form: FormData) {
  const { session } = await requireAdminForm(form)
  const trigger = triggerConfig()
  if (!trigger) redirect('/admin?notice=unconfigured')

  const db = getAdminPool()
  const running = await activeRun(db)
  if (running !== null) redirect(`/admin?notice=busy`)

  // The audit row is written first: if it fails, nothing is triggered.
  await insertAudit(db, { actor: session.uid, action: 'ingest.rerun', target: 'ingest', details: { login: session.login } })
  log('info', 'manual ingest requested', { uid: session.uid })

  after(async () => {
    try {
      const res = await fetch(trigger.url, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${trigger.secret}`,
          ...(trigger.bypass ? { 'x-vercel-protection-bypass': trigger.bypass } : {}),
        },
        signal: AbortSignal.timeout(TRIGGER_TIMEOUT_MS),
        cache: 'no-store',
      })
      log(res.ok ? 'info' : 'error', 'manual ingest finished', { status: res.status })
    } catch (err) {
      log('error', 'manual ingest call failed', { error: err instanceof Error ? err.name : 'unknown' })
    }
  })
  redirect('/admin?notice=requested')
}

export async function signOut(form: FormData) {
  const { session } = await requireAdminForm(form)
  try {
    await insertAudit(getAdminPool(), { actor: session.uid, action: 'auth.sign_out', details: { login: session.login } })
  } catch (err) {
    log('error', 'admin audit write failed', { action: 'auth.sign_out', error: err instanceof Error ? err.message : 'unknown' })
  }
  ;(await cookies()).set(SESSION_COOKIE, '', { ...COOKIE_OPTS, maxAge: 0 })
  redirect('/')
}
