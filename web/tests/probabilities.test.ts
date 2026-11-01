import { describe, expect, it } from 'vitest'

import { groupClassifications } from '@/lib/probabilities'
import type { ClassificationRow } from '@/lib/queries'

const row = (classifier: string, version: string, className: string, probability: number): ClassificationRow => ({
  classifier,
  version,
  className,
  probability,
  ranking: null,
})

describe('groupClassifications', () => {
  const rows = [
    row('stamp_classifier', 'stamp_classifier_1.0.0', 'SN', 0.4),
    row('stamp_classifier', 'stamp_classifier_1.0.4', 'VS', 0.2),
    row('stamp_classifier', 'stamp_classifier_1.0.4', 'SN', 0.7),
    row('lc_classifier', 'lc_classifier_1.1.13', 'RRL', 0.5),
    row('lc_classifier', 'lc_classifier_1.1.9', 'RRL', 0.6),
  ]

  it('keeps the newest version per classifier, preferred classifier first', () => {
    const { primary, older } = groupClassifications(rows, 'stamp_classifier')
    expect(primary.map((g) => `${g.classifier}@${g.version}`)).toEqual([
      'stamp_classifier@stamp_classifier_1.0.4',
      'lc_classifier@lc_classifier_1.1.13',
    ])
    expect(primary[0]!.rows.map((r) => r.className)).toEqual(['SN', 'VS'])
    expect(older.map((g) => g.version)).toEqual(['lc_classifier_1.1.9', 'stamp_classifier_1.0.0'])
  })

  it('sorts alphabetically without a preference', () => {
    expect(groupClassifications(rows, null).primary[0]!.classifier).toBe('lc_classifier')
  })
})
