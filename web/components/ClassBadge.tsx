import { classInfo } from '@/lib/classes'

// Text stays in text colour; the dot carries the group colour.
export function ClassBadge({ name }: { name: string | null }) {
  const info = classInfo(name)
  return (
    <span className="badge" data-group={info.group} title={info.blurb || undefined}>
      <span className="badge-dot" aria-hidden="true" />
      {info.label}
    </span>
  )
}
