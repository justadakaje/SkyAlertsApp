import { NextResponse, type NextRequest } from 'next/server'

import { getAdminPool } from '@/lib/admin/db'
import { insertAudit } from '@/lib/admin/queries'
import { adminConfig, SESSION_COOKIE, STATE_COOKIE } from '@/lib/auth/config'
import { exchangeCode, fetchUser } from '@/lib/auth/github'
import { COOKIE_OPTS, log } from '@/lib/auth/server'
import { encodeSession, newSession, SESSION_TTL_S, statesMatch } from '@/lib/auth/session'

export const dynamic = 'force-dynamic'

const CODE_RE = /^[A-Za-z0-9_-]{1,128}$/

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
    return fail('denied')
  }

  const session = newSession(user.id, user.login)
  // One line per sign-in, so a log alert can watch for it (SPEC §Security → Monitoring).
  log('info', 'admin sign-in', { uid: user.id, login: user.login, event: 'admin_sign_in' })
  await audit({ actor: user.id, action: 'auth.sign_in', details: { login: user.login } })

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
