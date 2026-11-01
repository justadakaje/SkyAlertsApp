import type { Metadata } from 'next'

import { StatusPill } from '@/components/admin/AdminBits'
import { triggerConfig } from '@/lib/auth/config'
import { requireAdmin } from '@/lib/auth/server'
import { formatUtc } from '@/lib/format'

export const metadata: Metadata = { title: 'Settings' }

export default async function SettingsPage() {
  const { cfg, session } = await requireAdmin()
  const trigger = triggerConfig()
  // Presence only: secret values and lengths are never rendered.
  const checks: [string, boolean, string][] = [
    ['GitHub OAuth app', true, 'GITHUB_CLIENT_ID / GITHUB_CLIENT_SECRET'],
    ['Session signing secret', true, 'ADMIN_SESSION_SECRET'],
    ['Admin database role', Boolean(process.env.ADMIN_DATABASE_URL), 'ADMIN_DATABASE_URL (skyalerts_web_admin)'],
    ['Public database role', Boolean(process.env.DATABASE_URL), 'DATABASE_URL (skyalerts_ro)'],
    ['Manual ingest trigger', trigger !== null, 'MANUAL_TRIGGER_URL / MANUAL_TRIGGER_SECRET'],
  ]
  return (
    <>
      <h1>Settings</h1>
      <section className="panel" aria-labelledby="config-heading">
        <h2 id="config-heading">Configuration</h2>
        <p className="muted small">Set in the Vercel project&rsquo;s environment variables. Only presence is shown here.</p>
        <ul className="checklist">
          {checks.map(([name, ok, env]) => (
            <li key={name}>
              <StatusPill level={ok ? 'good' : 'critical'} label={ok ? 'Set' : 'Missing'} /> {name}{' '}
              <code className="small muted">{env}</code>
            </li>
          ))}
        </ul>
        {trigger ? (
          <p className="small muted">
            Manual runs go to <code>{new URL(trigger.url).host}</code>.
          </p>
        ) : null}
      </section>
      <section className="panel" aria-labelledby="access-heading">
        <h2 id="access-heading">Access</h2>
        <p>
          Allowed GitHub user ids (<code>ADMIN_GITHUB_IDS</code>): {[...cfg.allowedIds].map((id) => <code key={id}>{id} </code>)}
        </p>
        <p className="small muted">
          Your session ends {formatUtc(new Date(session.exp * 1000))}. Rotating <code>ADMIN_SESSION_SECRET</code> signs
          everyone out; removing an id takes effect on the next request.
        </p>
      </section>
      <section className="panel">
        <h2>Digest settings</h2>
        <p className="muted">Recipient and schedule arrive with the Phase 3 digest.</p>
      </section>
    </>
  )
}
