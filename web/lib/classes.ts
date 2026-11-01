// ALeRCE class names -> plain-English labels and display groups.
// Class names come from upstream data, so anything unknown falls back to a neutral "other".

export type ClassGroup = 'stochastic' | 'transient' | 'variable' | 'solar' | 'other'

export interface ClassInfo {
  name: string | null
  label: string
  group: ClassGroup
  blurb: string
}

// Order matches the categorical colour slots (validated as adjacent pairs in stacks).
export const GROUPS: { id: ClassGroup; label: string }[] = [
  { id: 'stochastic', label: 'Active galaxies' },
  { id: 'transient', label: 'Explosions & outbursts' },
  { id: 'variable', label: 'Variable stars' },
  { id: 'solar', label: 'Solar system' },
  { id: 'other', label: 'Other & unclassified' },
]

const KNOWN: Record<string, Omit<ClassInfo, 'name'>> = {
  SN: { label: 'Supernova', group: 'transient', blurb: 'An exploding star, brightening over days and fading over weeks.' },
  SNIa: { label: 'Type Ia supernova', group: 'transient', blurb: 'A white dwarf blown apart. Their even brightness makes them cosmic yardsticks.' },
  SNIbc: { label: 'Type Ib/c supernova', group: 'transient', blurb: 'A massive star that lost its outer layers before collapsing.' },
  SNIIn: { label: 'Type IIn supernova', group: 'transient', blurb: 'A supernova slamming into gas the star shed before it died.' },
  SNIIb: { label: 'Type IIb supernova', group: 'transient', blurb: 'A massive star that kept only a thin shell of hydrogen before collapsing.' },
  SNII: { label: 'Type II supernova', group: 'transient', blurb: 'A massive star whose core collapsed while still wrapped in hydrogen.' },
  SLSN: { label: 'Superluminous supernova', group: 'transient', blurb: 'A rare explosion ten or more times brighter than a normal supernova.' },
  TDE: { label: 'Tidal disruption event', group: 'transient', blurb: 'A star torn apart by a supermassive black hole.' },
  KN: { label: 'Kilonova', group: 'transient', blurb: 'The glow left behind when two neutron stars merge.' },
  'CV/Nova': { label: 'Cataclysmic variable', group: 'transient', blurb: 'A white dwarf flaring as it pulls gas off a companion star.' },
  AGN: { label: 'Active galactic nucleus', group: 'stochastic', blurb: 'A feeding supermassive black hole flickering at the heart of a galaxy.' },
  QSO: { label: 'Quasar', group: 'stochastic', blurb: 'A very distant, very luminous active galactic nucleus.' },
  Blazar: { label: 'Blazar', group: 'stochastic', blurb: 'An active galaxy with its jet pointed almost straight at us.' },
  YSO: { label: 'Young stellar object', group: 'stochastic', blurb: 'A newborn star still gathering gas and dust.' },
  VS: { label: 'Variable star', group: 'variable', blurb: 'A star whose brightness changes over time.' },
  RRL: { label: 'RR Lyrae star', group: 'variable', blurb: 'An old star pulsing on a steady rhythm of about half a day.' },
  CEP: { label: 'Cepheid', group: 'variable', blurb: 'A pulsing giant whose period reveals its true brightness.' },
  DSCT: { label: 'Delta Scuti star', group: 'variable', blurb: 'A star that pulses every few hours.' },
  E: { label: 'Eclipsing binary', group: 'variable', blurb: "Two stars taking turns blocking each other's light." },
  LPV: { label: 'Long-period variable', group: 'variable', blurb: 'A swollen red giant that brightens and dims over months.' },
  RRLab: { label: 'RR Lyrae star (ab)', group: 'variable', blurb: 'An RR Lyrae star pulsing in its fundamental mode.' },
  RRLc: { label: 'RR Lyrae star (c)', group: 'variable', blurb: 'An RR Lyrae star pulsing in its first overtone.' },
  'Periodic-Other': { label: 'Periodic variable', group: 'variable', blurb: 'A star that repeats on a regular schedule.' },
  Transient: { label: 'Transient', group: 'transient', blurb: 'Something that appears or flares once, rather than repeating.' },
  Stochastic: { label: 'Irregular variable', group: 'stochastic', blurb: 'Brightness that wanders without a fixed rhythm.' },
  Periodic: { label: 'Periodic variable', group: 'variable', blurb: 'Brightness that repeats on a regular schedule.' },
  nuclear: { label: 'At a galaxy core', group: 'other', blurb: 'Sits at the centre of its host galaxy.' },
  'off-nuclear': { label: 'Away from a galaxy core', group: 'other', blurb: 'Sits away from the centre of its host galaxy.' },
  asteroid: { label: 'Asteroid', group: 'solar', blurb: 'A solar-system body caught moving across the field.' },
  bogus: { label: 'Artifact', group: 'other', blurb: 'Not a real sky source: a glitch in the image subtraction.' },
}

/** Ranking tiers for "notable" ordering. Keep in step with ingest enrichment tiers. */
export const TRANSIENT_CLASSES = ['SN', 'SNIa', 'SNIbc', 'SNII', 'SLSN', 'TDE', 'KN', 'CV/Nova']
export const LOW_PRIORITY_CLASSES = ['AGN', 'QSO', 'Blazar']
export const ARTIFACT_CLASS = 'bogus'

export function classInfo(name: string | null): ClassInfo {
  const known = name ? KNOWN[name] : undefined
  if (known) return { name, ...known }
  return { name, label: name ?? 'Unclassified', group: 'other', blurb: '' }
}

export function groupOf(name: string | null): ClassGroup {
  return classInfo(name).group
}
