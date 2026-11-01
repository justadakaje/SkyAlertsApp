import { describe, expect, it } from 'vitest'

import { authorizeUrl, exchangeCode, fetchUser, GitHubAuthError, type Fetch } from '@/lib/auth/github'

function fakeFetch(status: number, body: unknown) {
  const calls: { url: string; init?: RequestInit }[] = []
  const f: Fetch = async (url, init) => {
    calls.push({ url: String(url), init })
    return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
  }
  return { f, calls }
}

describe('github oauth', () => {
  it('builds an authorize URL without scopes', () => {
    const u = new URL(authorizeUrl('Iv1.abc', 'https://sky.henseler.app/api/auth/github/callback', 'st8'))
    expect(u.origin + u.pathname).toBe('https://github.com/login/oauth/authorize')
    expect(Object.fromEntries(u.searchParams)).toEqual({
      client_id: 'Iv1.abc',
      redirect_uri: 'https://sky.henseler.app/api/auth/github/callback',
      state: 'st8',
      allow_signup: 'false',
    })
  })

  it('exchanges a code for a token', async () => {
    const { f, calls } = fakeFetch(200, { access_token: 'gho_test', token_type: 'bearer' })
    expect(await exchangeCode('code1', 'id', 'secret', 'https://x/cb', f)).toBe('gho_test')
    expect(calls[0]!.url).toBe('https://github.com/login/oauth/access_token')
    expect(JSON.parse(String(calls[0]!.init?.body))).toMatchObject({ code: 'code1', client_id: 'id' })
  })

  it('surfaces GitHub errors without leaking the code', async () => {
    const { f } = fakeFetch(200, { error: 'bad_verification_code' })
    await expect(exchangeCode('code-xyz', 'id', 'secret', 'https://x/cb', f)).rejects.toThrow(GitHubAuthError)
    await expect(exchangeCode('code-xyz', 'id', 'secret', 'https://x/cb', f)).rejects.not.toThrow(/code-xyz/)
  })

  it('reads the numeric user id and validates it', async () => {
    expect(await fetchUser('t', fakeFetch(200, { id: 16056018, login: 'justadakaje' }).f)).toEqual({
      id: 16056018,
      login: 'justadakaje',
    })
    await expect(fetchUser('t', fakeFetch(200, { id: '16056018', login: 'x' }).f)).rejects.toThrow(GitHubAuthError)
    await expect(fetchUser('t', fakeFetch(401, { message: 'Bad credentials' }).f)).rejects.toThrow(GitHubAuthError)
  })
})
