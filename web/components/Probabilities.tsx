import { classInfo } from '@/lib/classes'
import { formatProbability } from '@/lib/format'
import { groupClassifications, type ClassifierGroup } from '@/lib/probabilities'
import type { ClassificationRow } from '@/lib/queries'

const SHOW_PER_GROUP = 3
const SHOW_GROUPS = 3

export function Probabilities({ rows, preferred }: { rows: ClassificationRow[]; preferred: string | null }) {
  const { primary, older } = groupClassifications(rows, preferred)
  const shown = primary.slice(0, SHOW_GROUPS)
  const folded = [...primary.slice(SHOW_GROUPS), ...older]
  return (
    <div>
      <div className="prob-grid">
        {shown.map((g) => (
          <ProbGroup key={`${g.classifier}${g.version}`} group={g} />
        ))}
      </div>
      {folded.length ? (
        <details className="table-view">
          <summary>
            More classifiers and versions ({folded.length})
          </summary>
          <div className="prob-grid">
            {folded.map((g) => (
              <ProbGroup key={`${g.classifier}${g.version}`} group={g} />
            ))}
          </div>
        </details>
      ) : null}
    </div>
  )
}

function ProbGroup({ group }: { group: ClassifierGroup }) {
  return (
    <section className="prob-group">
      <h3 className="prob-title">
        {group.classifier}
        {group.version ? <span className="muted"> · {group.version}</span> : null}
      </h3>
      <ul className="prob-list">
        {group.rows.slice(0, SHOW_PER_GROUP).map((r) => {
          const info = classInfo(r.className)
          return (
            <li key={r.className} className="prob-row" data-group={info.group}>
              <span className="prob-label" title={info.blurb || undefined}>
                {info.label}
              </span>
              <svg className="prob-bar" viewBox="0 0 100 8" preserveAspectRatio="none" aria-hidden="true">
                <rect className="prob-track" x={0} y={0} width={100} height={8} rx={2} />
                <rect className="prob-fill" x={0} y={0} width={Math.max(1, r.probability * 100)} height={8} rx={2} />
              </svg>
              <span className="prob-value num">{formatProbability(r.probability)}</span>
            </li>
          )
        })}
      </ul>
    </section>
  )
}
