class SolarBody {
  const SolarBody({
    required this.id,
    required this.name,
    required this.number,
    required this.designation,
    required this.status,
    required this.zone,
    required this.approxDiameterKm,
    required this.blurb,
    required this.a,
    required this.e,
    required this.i,
    required this.q,
    required this.bigQ,
    required this.periodDays,
    required this.rotationH,
    required this.discovered,
    required this.discoveredBy,
    this.orbitviewer,
  });

  final String id;
  final String name;
  final int number;
  final String designation;
  final String status; // 'dwarf' | 'candidate'
  final String zone;
  final String approxDiameterKm;
  final String blurb;
  final double a;
  final double e;
  final double i;
  final double q;
  final double bigQ;
  final double periodDays;
  final double rotationH;
  final String discovered;
  final String discoveredBy;
  final String? orbitviewer;

  String get jplUrl => 'https://ssd.jpl.nasa.gov/tools/sbdb_lookup.html#/?sstr=$number';
  String? get orbitviewerUrl =>
      orbitviewer != null ? 'https://orbitviewer.app/en/solar-items/$orbitviewer/' : null;
}

const List<SolarBody> solarBodies = [
  SolarBody(
    id: 'ceres',
    name: 'Ceres',
    number: 1,
    designation: 'A801 AA',
    status: 'dwarf',
    zone: 'Asteroid belt',
    approxDiameterKm: '939',
    blurb:
        'The largest object in the asteroid belt and the only dwarf planet in the inner Solar System. NASA’s Dawn spacecraft orbited it from 2015 to 2018.',
    a: 2.77,
    e: 0.0797,
    i: 10.6,
    q: 2.55,
    bigQ: 2.99,
    periodDays: 1680,
    rotationH: 9.074,
    discovered: '1801-01-01',
    discoveredBy: 'G. Piazzi',
    orbitviewer: 'ceres',
  ),
  SolarBody(
    id: 'pluto',
    name: 'Pluto',
    number: 134340,
    designation: '1930 BM',
    status: 'dwarf',
    zone: 'Kuiper belt',
    approxDiameterKm: '2,377',
    blurb:
        'Found by Clyde Tombaugh in 1930. New Horizons flew past in July 2015 and revealed nitrogen-ice plains and water-ice mountains.',
    a: 39.6,
    e: 0.252,
    i: 17.1,
    q: 29.6,
    bigQ: 49.6,
    periodDays: 91000,
    rotationH: 153.29,
    discovered: '1930-01-23',
    discoveredBy: 'C. W. Tombaugh',
    orbitviewer: 'pluto',
  ),
  SolarBody(
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
    bigQ: 97.7,
    periodDays: 205000,
    rotationH: 25.9,
    discovered: '2003-10-21',
    discoveredBy: 'M. E. Brown, C. A. Trujillo, D. Rabinowitz',
    orbitviewer: 'eris',
  ),
  SolarBody(
    id: 'haumea',
    name: 'Haumea',
    number: 136108,
    designation: '2003 EL61',
    status: 'dwarf',
    zone: 'Kuiper belt',
    approxDiameterKm: '~2,100 (long axis)',
    blurb:
        'Spins once every 3.9 hours, stretching it into a triaxial ellipsoid with a ring and two moons, Hiʻiaka and Namaka.',
    a: 43.1,
    e: 0.194,
    i: 28.2,
    q: 34.7,
    bigQ: 51.4,
    periodDays: 103000,
    rotationH: 3.915,
    discovered: '2003-03-07',
    discoveredBy: 'Sierra Nevada Observatory / Palomar',
    orbitviewer: 'haumea',
  ),
  SolarBody(
    id: 'makemake',
    name: 'Makemake',
    number: 136472,
    designation: '2005 FY9',
    status: 'dwarf',
    zone: 'Kuiper belt',
    approxDiameterKm: '1,430',
    blurb:
        'The second-brightest object in the Kuiper belt after Pluto, with methane-covered surfaces and a small moon.',
    a: 45.6,
    e: 0.159,
    i: 29.0,
    q: 38.3,
    bigQ: 52.8,
    periodDays: 112000,
    rotationH: 22.83,
    discovered: '2005-03-31',
    discoveredBy: 'M. E. Brown, C. A. Trujillo, D. Rabinowitz',
    orbitviewer: 'makemake',
  ),
  SolarBody(
    id: 'gonggong',
    name: 'Gonggong',
    number: 225088,
    designation: '2007 OR10',
    status: 'candidate',
    zone: 'Scattered disc',
    approxDiameterKm: '1,230',
    blurb: 'One of the reddest large trans-Neptunian bodies known, with one moon, Xiangliu.',
    a: 66.9,
    e: 0.504,
    i: 30.9,
    q: 33.1,
    bigQ: 101.0,
    periodDays: 200000,
    rotationH: 22.4,
    discovered: '2007-07-17',
    discoveredBy: 'M. E. Schwamb, M. E. Brown, D. Rabinowitz',
  ),
  SolarBody(
    id: 'quaoar',
    name: 'Quaoar',
    number: 50000,
    designation: '2002 LM60',
    status: 'candidate',
    zone: 'Kuiper belt',
    approxDiameterKm: '1,110',
    blurb: 'Hosts a ring outside its classical Roche limit and a moon, Weywot.',
    a: 43.2,
    e: 0.0352,
    i: 7.99,
    q: 41.6,
    bigQ: 44.7,
    periodDays: 104000,
    rotationH: 8.84,
    discovered: '2002-06-04',
    discoveredBy: 'C. A. Trujillo, M. E. Brown',
  ),
  SolarBody(
    id: 'sedna',
    name: 'Sedna',
    number: 90377,
    designation: '2003 VB12',
    status: 'candidate',
    zone: 'Inner Oort cloud',
    approxDiameterKm: '~1,000',
    blurb:
        'Swings from 76 au out to ~1,000 au over 12,700 years; currently approaching perihelion (due ~2076).',
    a: 544.0,
    e: 0.86,
    i: 11.9,
    q: 76.2,
    bigQ: 1010.0,
    periodDays: 4630000,
    rotationH: 10.27,
    discovered: '2003-11-14',
    discoveredBy: 'M. E. Brown, C. A. Trujillo, D. Rabinowitz',
    orbitviewer: '2003-vb12',
  ),
  SolarBody(
    id: 'orcus',
    name: 'Orcus',
    number: 90482,
    designation: '2004 DW',
    status: 'candidate',
    zone: 'Kuiper belt (plutino)',
    approxDiameterKm: '910',
    blurb:
        'The “anti-Pluto”: shares Pluto’s 2:3 resonance with Neptune on the opposite phase of its orbit. Moon: Vanth.',
    a: 39.4,
    e: 0.221,
    i: 20.6,
    q: 30.7,
    bigQ: 48.1,
    periodDays: 90300,
    rotationH: 13.19,
    discovered: '2004-02-17',
    discoveredBy: 'M. Brown, C. Trujillo',
  ),
];

final RegExp _safeSsoNameRe = RegExp(r"^[A-Za-z0-9 ()/_.'-]{1,64}$");

String formatSsoLabel(int? ssoNumber, String ssoName) {
  if (ssoNumber != null && ssoNumber >= 1) {
    return '($ssoNumber) $ssoName';
  }
  return ssoName;
}

String? jplSbdbUrl(int? ssoNumber, [String? ssoName]) {
  if (ssoNumber != null && ssoNumber >= 1) {
    return 'https://ssd.jpl.nasa.gov/tools/sbdb_lookup.html#/?sstr=$ssoNumber';
  }
  final clean = ssoName?.trim() ?? '';
  if (clean.isNotEmpty && _safeSsoNameRe.hasMatch(clean)) {
    return 'https://ssd.jpl.nasa.gov/tools/sbdb_lookup.html#/?sstr=${Uri.encodeQueryComponent(clean)}';
  }
  return null;
}

String viewingHint({required double elongation, double? mag}) {
  if (elongation < 30.0) return 'Too close to the Sun to observe';
  if (mag == null || !mag.isFinite) return 'Brightness not available';
  if (mag <= 6.0) return 'Naked eye from a dark site';
  if (mag <= 9.0) return 'Binoculars';
  if (mag <= 13.0) return 'Small telescope';
  if (mag <= 15.0) return 'Large amateur telescope';
  return 'Research telescopes and long exposures';
}
