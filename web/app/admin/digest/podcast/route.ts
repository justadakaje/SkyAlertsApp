import { fetchDigestPreview, podcastFilename } from '@/lib/admin/digest'
import { requireAdmin } from '@/lib/auth/server'

const ERROR_HEADERS = {
  'Cache-Control': 'no-store',
  'Content-Type': 'text/plain; charset=utf-8',
} as const

export async function GET(): Promise<Response> {
  await requireAdmin()
  const preview = await fetchDigestPreview()
  if (!preview.ok) {
    const status = preview.reason === 'unconfigured' ? 503 : 502
    const body =
      preview.reason === 'unconfigured'
        ? 'Digest service is not configured (DIGEST_URL / DIGEST_TRIGGER_SECRET).'
        : 'Could not fetch podcast outline from the digest service.'
    return new Response(body, { status, headers: ERROR_HEADERS })
  }

  const filename = podcastFilename(preview.data.weekEnd)
  if (!filename) {
    return new Response('Digest preview returned an invalid week_end.', { status: 502, headers: ERROR_HEADERS })
  }

  return new Response(preview.data.podcastMarkdown, {
    status: 200,
    headers: {
      'Content-Type': 'text/markdown; charset=utf-8',
      'Content-Disposition': `attachment; filename="${filename}"`,
      'Cache-Control': 'no-store',
    },
  })
}
