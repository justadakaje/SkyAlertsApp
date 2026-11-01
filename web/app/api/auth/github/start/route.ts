import { NextResponse, type NextRequest } from 'next/server'

import { adminConfig, STATE_COOKIE, STATE_TTL_S } from '@/lib/auth/config'
import { authorizeUrl } from '@/lib/auth/github'
import { COOKIE_OPTS } from '@/lib/auth/server'
import { randomToken } from '@/lib/auth/session'

export const dynamic = 'force-dynamic'

export function GET(request: NextRequest) {
  const cfg = adminConfig()
  if (!cfg) return NextResponse.redirect(new URL('/admin/login?error=config', request.url), 303)
  // GitHub only accepts redirect URIs under the OAuth app's registered callback,
  // so a spoofed Host can't send the code anywhere else.
  const redirectUri = new URL('/api/auth/github/callback', request.nextUrl.origin).toString()
  const state = randomToken()
  const res = NextResponse.redirect(authorizeUrl(cfg.clientId, redirectUri, state), 303)
  res.cookies.set(STATE_COOKIE, state, { ...COOKIE_OPTS, maxAge: STATE_TTL_S })
  return res
}
