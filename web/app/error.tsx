'use client'

// Error details stay in server logs; the page shows only a digest for support.
export default function ErrorPage({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  return (
    <section className="hero">
      <h1>Clouds rolled in</h1>
      <p className="lede">Something went wrong loading this page. It is usually the database waking up; try again.</p>
      <p>
        <button type="button" onClick={reset}>
          Try again
        </button>
      </p>
      {error.digest ? <p className="muted small">Reference: {error.digest}</p> : null}
    </section>
  )
}
