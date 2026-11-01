import Link from 'next/link'

import { mjdToDate } from '@/lib/astro'
import { formatAgo, formatProbability, formatUtc } from '@/lib/format'
import type { EventRow } from '@/lib/queries'

import { ClassBadge } from './ClassBadge'

export function objectHref(survey: string, oid: string): string {
  return `/objects/${survey}/${encodeURIComponent(oid)}`
}

export function EventTable({ rows, now }: { rows: EventRow[]; now: Date }) {
  return (
    <div className="table-scroll">
      <table className="events">
        <thead>
          <tr>
            <th scope="col">Object</th>
            <th scope="col">Class</th>
            <th scope="col" className="num">
              Confidence
            </th>
            <th scope="col">Last seen</th>
            <th scope="col" className="hide-sm">
              First seen
            </th>
            <th scope="col" className="num hide-sm">
              Detections
            </th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => {
            const last = r.lastmjd === null ? null : mjdToDate(r.lastmjd)
            const first = r.firstmjd === null ? null : mjdToDate(r.firstmjd)
            return (
              <tr key={`${r.survey}/${r.oid}`}>
                <td>
                  <Link className="oid" href={objectHref(r.survey, r.oid)}>
                    {r.oid}
                  </Link>
                  <span className="survey-tag">{r.survey.toUpperCase()}</span>
                </td>
                <td>
                  <ClassBadge name={r.topClass} />
                </td>
                <td className="num">{formatProbability(r.probability)}</td>
                <td>{last ? <time dateTime={last.toISOString()} title={formatUtc(last)}>{formatAgo(last, now)}</time> : '—'}</td>
                <td className="hide-sm">
                  {first ? <time dateTime={first.toISOString()} title={formatUtc(first)}>{formatAgo(first, now)}</time> : '—'}
                </td>
                <td className="num hide-sm">{r.ndet ?? '—'}</td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
