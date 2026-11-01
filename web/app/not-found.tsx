import Link from 'next/link'

export default function NotFound() {
  return (
    <section className="hero">
      <h1>Not in our sky</h1>
      <p className="lede">We have no record of that page or object. Sky Alerts only stores objects seen recently.</p>
      <p>
        <Link href="/">Back to the latest events</Link>
      </p>
    </section>
  )
}
