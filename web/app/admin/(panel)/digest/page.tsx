import type { Metadata } from 'next'

import { CsrfInput } from '@/components/admin/AdminBits'
import { digestNotice, fetchDigestPreview } from '@/lib/admin/digest'
import { digestConfig } from '@/lib/auth/config'
import { requireAdmin } from '@/lib/auth/server'
import type { SearchParams } from '@/lib/filters'

import { sendDigestNow } from '../../actions'

export const metadata: Metadata = { title: 'Digest' }

export default async function DigestPage({ searchParams }: { searchParams: Promise<SearchParams> }) {
  const { csrf } = await requireAdmin()
  const sp = await searchParams
  const notice = digestNotice(sp)
  const cfg = digestConfig()
  const preview = await fetchDigestPreview(cfg)

  return (
    <>
      <h1>Weekly digest</h1>
      {notice ? (
        <p className="notice" data-level={notice.level} role="status">
          {notice.text}
        </p>
      ) : null}

      {!preview.ok ? (
        <p className="notice" data-level="critical" role="status">
          {preview.reason === 'unconfigured'
            ? 'Digest preview and send are not configured (set DIGEST_URL and DIGEST_TRIGGER_SECRET).'
            : `Could not load digest preview from the digest service${preview.status ? ` (HTTP ${preview.status})` : ''}.`}
        </p>
      ) : null}

      <section className="panel" aria-labelledby="digest-actions-heading">
        <h2 id="digest-actions-heading">Send &amp; export</h2>
        {preview.ok ? (
          <dl className="kv">
            <div>
              <dt>Subject</dt>
              <dd>{preview.data.subject}</dd>
            </div>
            <div>
              <dt>Week ending (00:00 UTC)</dt>
              <dd>
                <code>{preview.data.weekEnd}</code>
              </dd>
            </div>
            <div>
              <dt>Headliners</dt>
              <dd className="num">{preview.data.headliners}</dd>
            </div>
          </dl>
        ) : null}
        <form action={sendDigestNow} className="rerun">
          <CsrfInput token={csrf} />
          <button type="submit" disabled={cfg === null}>
            Send digest now
          </button>
          <a href="/admin/digest/podcast" className="button">
            Download podcast outline (.md)
          </a>
          <span className="muted small">
            Audited before sending. Sends are idempotent (one send per UTC day, keyed by <code>week_end</code>): a
            repeat send the same UTC day is a no-op on Resend&rsquo;s side, and returns an error if the digest content
            changed in between.
          </span>
        </form>
      </section>

      {preview.ok ? (
        <>
          <section className="panel" aria-labelledby="email-markdown-heading">
            <h2 id="email-markdown-heading">Email digest (Markdown)</h2>
            <pre className="code-block">{preview.data.digestMarkdown}</pre>
          </section>

          <section className="panel" aria-labelledby="podcast-markdown-heading">
            <h2 id="podcast-markdown-heading">Podcast outline (Markdown)</h2>
            <p className="small">
              <a href="/admin/digest/podcast">
                Download <code>sky-this-week-{preview.data.weekEnd}.md</code> →
              </a>
            </p>
            <pre className="code-block">{preview.data.podcastMarkdown}</pre>
          </section>
        </>
      ) : null}
    </>
  )
}
