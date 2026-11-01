import type { ClassificationRow } from './queries'

export interface ClassifierGroup {
  classifier: string
  version: string
  rows: ClassificationRow[]
}

const cmp = (a: string, b: string) => a.localeCompare(b, 'en', { numeric: true })

// ALeRCE's main production classifiers lead; experimental and sub-tree ones follow.
const MAIN_CLASSIFIERS = [
  'lc_classifier',
  'stamp_classifier',
  'stamp_classifier_rubin_beta_20260421',
  'stamp_classifier_rubin_beta',
]

function priority(name: string, preferred: string | null): number {
  if (name === preferred) return -1
  const i = MAIN_CLASSIFIERS.indexOf(name)
  return i === -1 ? MAIN_CLASSIFIERS.length : i
}

/**
 * Group rows by (classifier, version), highest probability first. The newest
 * version of each classifier is "primary" (the object's own top classifier,
 * then ALeRCE's main classifiers, lead); superseded versions are returned
 * separately so the page can fold them.
 */
export function groupClassifications(
  rows: ClassificationRow[],
  preferred: string | null,
): { primary: ClassifierGroup[]; older: ClassifierGroup[] } {
  const byKey = new Map<string, ClassifierGroup>()
  for (const r of rows) {
    const key = `${r.classifier}\u0000${r.version}`
    const g = byKey.get(key) ?? { classifier: r.classifier, version: r.version, rows: [] }
    g.rows.push(r)
    byKey.set(key, g)
  }
  const groups = [...byKey.values()]
  for (const g of groups) g.rows.sort((a, b) => b.probability - a.probability)

  const latest = new Map<string, ClassifierGroup>()
  for (const g of groups) {
    const cur = latest.get(g.classifier)
    if (!cur || cmp(g.version, cur.version) > 0) latest.set(g.classifier, g)
  }
  const primary = [...latest.values()].sort(
    (a, b) =>
      priority(a.classifier, preferred) - priority(b.classifier, preferred) ||
      cmp(a.classifier, b.classifier),
  )
  const older = groups
    .filter((g) => latest.get(g.classifier) !== g)
    .sort((a, b) => cmp(a.classifier, b.classifier) || cmp(b.version, a.version))
  return { primary, older }
}
