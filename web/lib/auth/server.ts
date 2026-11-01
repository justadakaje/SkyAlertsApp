import 'server-only'

import { cookies } from 'next/headers'
import { redirect } from 'next/navigation'

import { adminConfig, SESSION_COOKIE, type AdminConfig } from './config'
import { csrfToken, decodeSession, verifyCsrf, type Session } from './session'

export interface AdminContext {
  cfg: AdminConfig
  session: Session
  csrf: string
}

export const COOKIE_OPTS = { httpOnly: true, secure: true, sameSite: 'lax', path: '/' } as const

/** The signed-in admin, or null. The allowlist is re-checked on every call. */
export async function currentAdmin(): Promise<AdminContext | null> {
  const cfg = adminConfig()
  if (!cfg) return null
  const session = await decodeSession((await cookies()).get(SESSION_COOKIE)?.value, cfg.sessionSecret)
  if (!session || !cfg.allowedIds.has(session.uid)) return null
  return { cfg, session, csrf: await csrfToken(session, cfg.sessionSecret) }
}

/**
 * Guard for every admin page and layout. Layouts alone aren't enough (they can
 * be skipped on client navigation), and the proxy is never the only check.
 */
export async function requireAdmin(): Promise<AdminContext> {
  const ctx = await currentAdmin()
  if (!ctx) redirect('/admin/login')
  return ctx
}

/** Guard for every admin server action: a valid session plus this session's CSRF token. */
export async function requireAdminForm(form: FormData): Promise<AdminContext> {
  const ctx = await requireAdmin()
  if (!(await verifyCsrf(form.get('csrf'), ctx.session, ctx.cfg.sessionSecret))) {
    log('warn', 'admin csrf rejected', { uid: ctx.session.uid })
    redirect('/admin?notice=expired')
  }
  return ctx
}

export function log(level: 'info' | 'warn' | 'error', msg: string, extra: Record<string, unknown> = {}): void {
  const line = JSON.stringify({ ts: new Date().toISOString(), level, logger: 'skyalerts.admin', msg, ...extra })
  if (level === 'error') console.error(line)
  else if (level === 'warn') console.warn(line)
  else console.log(line)
}
