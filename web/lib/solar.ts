// Dwarf planets and the largest dwarf-planet candidates, for the /solar-system page.
// Orbit and discovery facts are copied from the JPL Small-Body Database (SBDB API,
// fetched 2026-11-01); they change only when an orbit is refit, so they are static.
// Positions change nightly and come from JPL Horizons at request time (lib/data.ts).

export type SolarStatus = 'dwarf' | 'candidate'

export interface SolarBody {
  id: string
  name: string
  number: number // minor-planet number; also the Horizons and SBDB lookup key
  designation: string // provisional designation at discovery
  status: SolarStatus
  zone: string
  approxDiameterKm: string
  blurb: string
  a: number // semi-major axis, au
  e: number
  i: number // inclination, degrees
  q: number // perihelion, au
  Q: number // aphelion, au
  periodDays: number
  rotationH: number
  discovered: string
  discoveredAt: string
  discoveredBy: string
  // Path under orbitviewer.app/en/solar-items/. Only curated objects have a page
  // (checked 2026-11-01: Quaoar, Gonggong and Orcus return 404), so null means
  // "no page": link to JPL's orbit diagram instead.
  orbitviewer: string | null
  image: { src: string; alt: string; credit: string; source: string } | null
}

export const SOLAR_BODIES: readonly SolarBody[] = [
  {
    id: 'ceres',
    name: 'Ceres',
    number: 1,
    designation: 'A801 AA',
    status: 'dwarf',
    zone: 'Asteroid belt',
    approxDiameterKm: '939',
    blurb:
      'The largest object in the asteroid belt and the only dwarf planet in the inner Solar System. NASA’s Dawn spacecraft orbited it from 2015 to 2018 and found bright salt deposits in Occator Crater.',
    a: 2.77,
    e: 0.0797,
    i: 10.6,
    q: 2.55,
    Q: 2.99,
    periodDays: 1680,
    rotationH: 9.07417,
    discovered: '1801-01-01',
    discoveredAt: 'Palermo',
    discoveredBy: 'G. Piazzi',
    orbitviewer: 'ceres',
    image: {
      src: '/solar/ceres.webp',
      alt: 'Grey, cratered globe of Ceres centred on Occator Crater and its bright spots',
      credit: 'NASA/JPL-Caltech/UCLA/MPS/DLR/IDA (Dawn)',
      source: 'https://images.nasa.gov/details/PIA21906',
    },
  },
  {
    id: 'pluto',
    name: 'Pluto',
    number: 134340,
    designation: '1930 BM',
    status: 'dwarf',
    zone: 'Kuiper belt',
    approxDiameterKm: '2,377',
    blurb:
      'Found by Clyde Tombaugh in 1930 and reclassified as a dwarf planet in 2006. New Horizons flew past on 14 July 2015 and found nitrogen-ice plains, water-ice mountains and a hazy blue atmosphere.',
    a: 39.6,
    e: 0.252,
    i: 17.1,
    q: 29.6,
    Q: 49.6,
    periodDays: 91000,
    rotationH: 153.2935,
    discovered: '1930-01-23',
    discoveredAt: 'Flagstaff',
    discoveredBy: 'C. W. Tombaugh',
    orbitviewer: 'pluto',
    image: {
      src: '/solar/pluto.webp',
      alt: 'Enhanced-colour view of Pluto showing the pale heart-shaped Sputnik Planitia',
      credit: 'NASA/JHUAPL/SwRI (New Horizons)',
      source: 'https://images.nasa.gov/details/PIA19952',
    },
  },
  {
    id: 'eris',
    name: 'Eris',
    number: 136199,
    designation: '2003 UB313',
    status: 'dwarf',
    zone: 'Scattered disc',
    approxDiameterKm: '2,326',
    blurb:
      'Slightly smaller than Pluto but more massive. Its discovery led the IAU to define “planet” in 2006. It has one moon, Dysnomia.',
    a: 67.9,
    e: 0.438,
    i: 43.9,
    q: 38.2,
    Q: 97.7,
    periodDays: 205000,
    rotationH: 25.9,
    discovered: '2003-10-21',
    discoveredAt: 'Palomar',
    discoveredBy: 'M. E. Brown, C. A. Trujillo, D. Rabinowitz',
    orbitviewer: 'eris',
    image: null,
  },
  {
    id: 'haumea',
    name: 'Haumea',
    number: 136108,
    designation: '2003 EL61',
    status: 'dwarf',
    zone: 'Kuiper belt',
    approxDiameterKm: 'about 2,100 on its long axis',
    blurb:
      'Spins once every 3.9 hours, fast enough to stretch it into an elongated shape. It has a ring and two moons, Hiʻiaka and Namaka.',
    a: 43.1,
    e: 0.194,
    i: 28.2,
    q: 34.7,
    Q: 51.4,
    periodDays: 103000,
    rotationH: 3.9154,
    discovered: '2003-03-07',
    discoveredAt: 'Sierra Nevada',
    discoveredBy: 'F. J. Aceituno, P. Santos-Sanz, J. L. Ortiz',
    orbitviewer: 'haumea',
    image: null,
  },
  {
    id: 'makemake',
    name: 'Makemake',
    number: 136472,
    designation: '2005 FY9',
    status: 'dwarf',
    zone: 'Kuiper belt',
    approxDiameterKm: '1,430',
    blurb:
      'The second-brightest object in the Kuiper belt after Pluto. A small, dark moon was found in Hubble images in 2016.',
    a: 45.6,
    e: 0.159,
    i: 29,
    q: 38.3,
    Q: 52.8,
    periodDays: 112000,
    rotationH: 22.8266,
    discovered: '2005-03-31',
    discoveredAt: 'Palomar',
    discoveredBy: 'M. E. Brown, C. A. Trujillo, D. Rabinowitz',
    orbitviewer: 'makemake',
    image: null,
  },
  {
    id: 'gonggong',
    name: 'Gonggong',
    number: 225088,
    designation: '2007 OR10',
    status: 'candidate',
    zone: 'Scattered disc',
    approxDiameterKm: '1,230',
    blurb: 'Named in 2020 after a Chinese water god. One of the reddest large bodies known, with one moon, Xiangliu.',
    a: 66.9,
    e: 0.504,
    i: 30.9,
    q: 33.1,
    Q: 101,
    periodDays: 200000,
    rotationH: 22.4,
    discovered: '2007-07-17',
    discoveredAt: 'Palomar',
    discoveredBy: 'M. E. Schwamb, M. E. Brown, D. Rabinowitz',
    orbitviewer: null,
    image: null,
  },
  {
    id: 'quaoar',
    name: 'Quaoar',
    number: 50000,
    designation: '2002 LM60',
    status: 'candidate',
    zone: 'Kuiper belt',
    approxDiameterKm: '1,110',
    blurb:
      'Has a ring far outside the distance where rings are expected to survive, found in 2023 by watching it pass in front of stars. Its moon is Weywot.',
    a: 43.2,
    e: 0.0352,
    i: 7.99,
    q: 41.6,
    Q: 44.7,
    periodDays: 104000,
    rotationH: 8.84,
    discovered: '2002-06-04',
    discoveredAt: 'Palomar',
    discoveredBy: 'C. A. Trujillo, M. E. Brown',
    orbitviewer: null,
    image: null,
  },
  {
    id: 'sedna',
    name: 'Sedna',
    number: 90377,
    designation: '2003 VB12',
    status: 'candidate',
    zone: 'Inner Oort cloud',
    approxDiameterKm: 'about 1,000',
    blurb:
      'Its orbit swings from 76 au out to about 1,000 au and back over roughly 12,700 years. It is now near its closest approach, due around 2076.',
    a: 544,
    e: 0.86,
    i: 11.9,
    q: 76.2,
    Q: 1010,
    periodDays: 4630000,
    rotationH: 10.273,
    discovered: '2003-11-14',
    discoveredAt: 'Palomar',
    discoveredBy: 'M. E. Brown, C. A. Trujillo, D. Rabinowitz',
    orbitviewer: '2003-vb12',
    image: null,
  },
  {
    id: 'orcus',
    name: 'Orcus',
    number: 90482,
    designation: '2004 DW',
    status: 'candidate',
    zone: 'Kuiper belt (plutino)',
    approxDiameterKm: '910',
    blurb:
      'The “anti-Pluto”: it shares Pluto’s 2:3 resonance with Neptune but always sits on the opposite side of its orbit. Its moon is Vanth.',
    a: 39.4,
    e: 0.221,
    i: 20.6,
    q: 30.7,
    Q: 48.1,
    periodDays: 90300,
    rotationH: 13.188,
    discovered: '2004-02-17',
    discoveredAt: 'Palomar',
    discoveredBy: 'M. Brown, C. Trujillo',
    orbitviewer: null,
    image: null,
  },
]

export function orbitviewerUrl(b: SolarBody): string | null {
  return b.orbitviewer ? `https://orbitviewer.app/en/solar-items/${b.orbitviewer}/` : null
}

export function jplUrl(b: SolarBody): string {
  return `https://ssd.jpl.nasa.gov/tools/sbdb_lookup.html#/?sstr=${b.number}`
}

export function formatPeriod(days: number): string {
  const years = days / 365.25
  if (years < 10) return `${years.toFixed(1)} years`
  const rounded = years < 1000 ? Math.round(years) : Math.round(years / 100) * 100
  return `${rounded.toLocaleString('en-US')} years`
}

export function formatRotation(hours: number): string {
  return hours >= 48 ? `${(hours / 24).toFixed(1)} days` : `${hours.toFixed(1)} hours`
}

export interface Ephemeris {
  ra: number // degrees, ICRF
  dec: number
  mag: number | null // apparent V magnitude
  distanceAu: number // from Earth
  elongation: number // degrees from the Sun
  constellation: string
}

// Parses the first row between $$SOE and $$EOE of a Horizons observer table requested
// with QUANTITIES='1,9,20,23,29', ANG_FORMAT=DEG and CSV_FORMAT=YES. Columns:
// date, (blank), (blank), RA, Dec, APmag, S-brt, delta, deldot, S-O-T, /r, Cnst.
export function parseHorizons(result: string): Ephemeris | null {
  const start = result.indexOf('$$SOE')
  const end = result.indexOf('$$EOE')
  if (start < 0 || end < start) return null
  const row = result
    .slice(start + 5, end)
    .split('\n')
    .map((l) => l.trim())
    .find((l) => l.length > 0)
  if (!row) return null
  const c = row.split(',').map((s) => s.trim())
  if (c.length < 12) return null
  const ra = Number(c[3])
  const dec = Number(c[4])
  const mag = c[5] === 'n.a.' ? null : Number(c[5])
  const distanceAu = Number(c[7])
  const elongation = Number(c[9])
  const constellation = c[11] ?? ''
  if (![ra, dec, distanceAu, elongation].every(Number.isFinite)) return null
  if (ra < 0 || ra >= 360 || dec < -90 || dec > 90) return null
  if (mag !== null && !Number.isFinite(mag)) return null
  if (!/^[A-Z][a-z]{2}$/.test(constellation)) return null
  return { ra, dec, mag, distanceAu, elongation, constellation }
}

export function horizonsUrl(number: number, day: string): string {
  const next = new Date(Date.parse(`${day}T00:00:00Z`) + 86_400_000).toISOString().slice(0, 10)
  const p = new URLSearchParams({
    format: 'json',
    COMMAND: `'${number};'`,
    EPHEM_TYPE: 'OBSERVER',
    CENTER: "'500@399'",
    START_TIME: `'${day}'`,
    STOP_TIME: `'${next}'`,
    STEP_SIZE: "'1 d'",
    QUANTITIES: "'1,9,20,23,29'",
    ANG_FORMAT: 'DEG',
    OBJ_DATA: 'NO',
    CSV_FORMAT: 'YES',
  })
  return `https://ssd.jpl.nasa.gov/api/horizons.api?${p}`
}

// Rough guide to what it takes to see an object of a given magnitude from a dark site.
export function viewingHint(e: Ephemeris): string {
  if (e.elongation < 30) return 'Too close to the Sun to observe'
  if (e.mag === null) return 'Brightness not available'
  if (e.mag <= 6) return 'Naked eye from a dark site'
  if (e.mag <= 9) return 'Binoculars'
  if (e.mag <= 13) return 'Small telescope'
  if (e.mag <= 15) return 'Large amateur telescope'
  return 'Research telescopes and long exposures'
}

export const CONSTELLATIONS: Record<string, string> = {
  And: 'Andromeda', Ant: 'Antlia', Aps: 'Apus', Aqr: 'Aquarius', Aql: 'Aquila', Ara: 'Ara',
  Ari: 'Aries', Aur: 'Auriga', Boo: 'Boötes', Cae: 'Caelum', Cam: 'Camelopardalis',
  Cnc: 'Cancer', CVn: 'Canes Venatici', CMa: 'Canis Major', CMi: 'Canis Minor',
  Cap: 'Capricornus', Car: 'Carina', Cas: 'Cassiopeia', Cen: 'Centaurus', Cep: 'Cepheus',
  Cet: 'Cetus', Cha: 'Chamaeleon', Cir: 'Circinus', Col: 'Columba', Com: 'Coma Berenices',
  CrA: 'Corona Australis', CrB: 'Corona Borealis', Crv: 'Corvus', Crt: 'Crater', Cru: 'Crux',
  Cyg: 'Cygnus', Del: 'Delphinus', Dor: 'Dorado', Dra: 'Draco', Equ: 'Equuleus',
  Eri: 'Eridanus', For: 'Fornax', Gem: 'Gemini', Gru: 'Grus', Her: 'Hercules',
  Hor: 'Horologium', Hya: 'Hydra', Hyi: 'Hydrus', Ind: 'Indus', Lac: 'Lacerta', Leo: 'Leo',
  LMi: 'Leo Minor', Lep: 'Lepus', Lib: 'Libra', Lup: 'Lupus', Lyn: 'Lynx', Lyr: 'Lyra',
  Men: 'Mensa', Mic: 'Microscopium', Mon: 'Monoceros', Mus: 'Musca', Nor: 'Norma',
  Oct: 'Octans', Oph: 'Ophiuchus', Ori: 'Orion', Pav: 'Pavo', Peg: 'Pegasus', Per: 'Perseus',
  Phe: 'Phoenix', Pic: 'Pictor', Psc: 'Pisces', PsA: 'Piscis Austrinus', Pup: 'Puppis',
  Pyx: 'Pyxis', Ret: 'Reticulum', Sge: 'Sagitta', Sgr: 'Sagittarius', Sco: 'Scorpius',
  Scl: 'Sculptor', Sct: 'Scutum', Ser: 'Serpens', Sex: 'Sextans', Tau: 'Taurus',
  Tel: 'Telescopium', Tri: 'Triangulum', TrA: 'Triangulum Australe', Tuc: 'Tucana',
  UMa: 'Ursa Major', UMi: 'Ursa Minor', Vel: 'Vela', Vir: 'Virgo', Vol: 'Volans',
  Vul: 'Vulpecula',
}
