import { after, NextResponse, type NextRequest } from 'next/server'

import { getAdminPool } from '@/lib/admin/db'
import { insertAudit } from '@/lib/admin/queries'
import { adminConfig, SESSION_COOKIE, STATE_COOKIE } from '@/lib/auth/config'
import { exchangeCode, fetchUser } from '@/lib/auth/github'
import { COOKIE_OPTS, log } from '@/lib/auth/server'
import { encodeSession, newSession, SESSION_TTL_S, statesMatch } from '@/lib/auth/session'

export const dynamic = 'force-dynamic'

const CODE_RE = /^[A-Za-z0-9_-]{1,128}$/
const RESEND_EMAILS_URL = 'https://api.resend.com/emails'

export async function GET(request: NextRequest) {
  const fail = (error: string) => {
    const res = NextResponse.redirect(new URL(`/admin/login?error=${error}`, request.url), 303)
    res.cookies.set(STATE_COOKIE, '', { ...COOKIE_OPTS, maxAge: 0 })
    return res
  }

  const cfg = adminConfig()
  if (!cfg) return fail('config')
  const params = request.nextUrl.searchParams
  if (params.get('error')) return fail('cancelled')
  if (!(await statesMatch(request.cookies.get(STATE_COOKIE)?.value, params.get('state')))) {
    log('warn', 'admin oauth state mismatch')
    return fail('state')
  }
  const code = params.get('code')
  if (!code || !CODE_RE.test(code)) return fail('state')

  let user: { id: number; login: string }
  try {
    const redirectUri = new URL('/api/auth/github/callback', request.nextUrl.origin).toString()
    const token = await exchangeCode(code, cfg.clientId, cfg.clientSecret, redirectUri)
    user = await fetchUser(token)
  } catch (err) {
    log('error', 'admin github sign-in failed', { error: err instanceof Error ? err.message : 'unknown' })
    return fail('github')
  }

  if (!cfg.allowedIds.has(user.id)) {
    log('warn', 'admin sign-in denied', { uid: user.id, login: user.login })
    await audit({ actor: user.id, action: 'auth.sign_in_denied', details: { login: user.login } })
    after(() => notifyAuthAlert('auth.sign_in_denied', user))
    return fail('denied')
  }

  const session = newSession(user.id, user.login)
  // One line per sign-in, so a log alert can watch for it (SPEC §Security → Monitoring).
  log('info', 'admin sign-in', { uid: user.id, login: user.login, event: 'admin_sign_in' })
  await audit({ actor: user.id, action: 'auth.sign_in', details: { login: user.login } })
  after(() => notifyAuthAlert('admin_sign_in', user))

  const res = NextResponse.redirect(new URL('/admin', request.url), 303)
  res.cookies.set(STATE_COOKIE, '', { ...COOKIE_OPTS, maxAge: 0 })
  res.cookies.set(SESSION_COOKIE, await encodeSession(session, cfg.sessionSecret), {
    ...COOKIE_OPTS,
    maxAge: SESSION_TTL_S,
  })
  return res
}

// Sign-in events are best effort: a database blip must not lock the owner out,
// and the structured log line above is the primary record.
async function audit(entry: Parameters<typeof insertAudit>[1]) {
  try {
    await insertAudit(getAdminPool(), entry)
  } catch (err) {
    log('error', 'admin audit write failed', { action: entry.action, error: err instanceof Error ? err.message : 'unknown' })
  }
}

async function notifyAuthAlert(event: 'admin_sign_in' | 'auth.sign_in_denied', user: { id: number; login: string }) {
  const apiKey = (process.env.ALERT_RESEND_API_KEY || process.env.RESEND_API_KEY || '').trim()
  const recipient = (process.env.ALERT_TO || process.env.DIGEST_TO || '').trim()
  if (!apiKey || !recipient) return
  const subject =
    event === 'admin_sign_in'
      ? `[Sky Alerts] Admin sign-in: ${user.login} (#${user.id})`
      : `[Sky Alerts] Denied admin sign-in attempt: ${user.login} (#${user.id})`
  try {
    await fetch(RESEND_EMAILS_URL, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${apiKey}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        from: 'Sky Alerts <alerts@sky.henseler.app>',
        to: [recipient],
        subject,
        text: `${subject}\nTime: ${new Date().toISOString()}\nAudit log: https://sky.henseler.app/admin/audit`,
      }),
      signal: AbortSignal.timeout(8000),
      cache: 'no-store',
    })
  } catch {
    log('warn', 'admin auth alert email failed', { event, uid: user.id })
  }
}
