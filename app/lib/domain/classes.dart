enum ClassGroup {
  transients('transients', 'Cosmic explosions & outbursts'),
  variables('variables', 'Variable & eclipsing stars'),
  agn('agn', 'Active galaxies & quasars'),
  solar('solar', 'Solar System'),
  other('other', 'Other & artifacts');

  const ClassGroup(this.id, this.label);
  final String id;
  final String label;
}

class ClassMetadata {
  const ClassMetadata({
    required this.code,
    required this.label,
    required this.group,
    required this.blurb,
  });

  final String code;
  final String label;
  final ClassGroup group;
  final String blurb;
}

const String artifactClass = 'bogus';
const String asteroidClass = 'asteroid';

const Set<String> transientClasses = {
  'SN',
  'SNIa',
  'SNIbc',
  'SNII',
  'SNIIn',
  'SLSN',
  'TDE',
  'KN',
  'CV/Nova',
  'Microlensing',
};

const Map<String, ClassMetadata> _catalog = {
  'SNIa': ClassMetadata(
    code: 'SNIa',
    label: 'Type Ia Supernova',
    group: ClassGroup.transients,
    blurb: 'Thermonuclear explosion of a white dwarf star; used as a cosmic distance ruler.',
  ),
  'SNIbc': ClassMetadata(
    code: 'SNIbc',
    label: 'Stripped-Envelope Supernova (Ib/c)',
    group: ClassGroup.transients,
    blurb: 'Core collapse of a massive star that shed its outer hydrogen envelope.',
  ),
  'SNII': ClassMetadata(
    code: 'SNII',
    label: 'Type II Supernova',
    group: ClassGroup.transients,
    blurb: 'Core collapse of a massive hydrogen-rich red supergiant star.',
  ),
  'SNIIn': ClassMetadata(
    code: 'SNIIn',
    label: 'Interacting Supernova (IIn)',
    group: ClassGroup.transients,
    blurb: 'Supernova shockwave slamming into dense gas cast off before the explosion.',
  ),
  'SLSN': ClassMetadata(
    code: 'SLSN',
    label: 'Superluminous Supernova',
    group: ClassGroup.transients,
    blurb: 'Rare stellar explosion shining 10 to 100 times brighter than a typical supernova.',
  ),
  'SN': ClassMetadata(
    code: 'SN',
    label: 'Supernova Candidate',
    group: ClassGroup.transients,
    blurb: 'Exploding star candidate identified from image cutouts or early light curves.',
  ),
  'TDE': ClassMetadata(
    code: 'TDE',
    label: 'Tidal Disruption Event',
    group: ClassGroup.transients,
    blurb: 'Flare produced when a star wanders too close to a supermassive black hole and is shredded.',
  ),
  'KN': ClassMetadata(
    code: 'KN',
    label: 'Kilonova',
    group: ClassGroup.transients,
    blurb: 'Radioactive glow from the merger of two neutron stars or a neutron star and black hole.',
  ),
  'CV/Nova': ClassMetadata(
    code: 'CV/Nova',
    label: 'Cataclysmic Variable / Nova',
    group: ClassGroup.transients,
    blurb: 'Sudden thermonuclear flash or disk outburst on a white dwarf pulling gas from a companion.',
  ),
  'Microlensing': ClassMetadata(
    code: 'Microlensing',
    label: 'Gravitational Microlensing',
    group: ClassGroup.transients,
    blurb: 'Temporary brightening as a foreground star or planet magnifies a background star’s light.',
  ),
  'CEP': ClassMetadata(
    code: 'CEP',
    label: 'Cepheid Variable',
    group: ClassGroup.variables,
    blurb: 'Pulsating supergiant star whose regular period reveals its intrinsic luminosity.',
  ),
  'RRL': ClassMetadata(
    code: 'RRL',
    label: 'RR Lyrae Variable',
    group: ClassGroup.variables,
    blurb: 'Old, pulsating horizontal-branch star often used to trace halo distances.',
  ),
  'E': ClassMetadata(
    code: 'E',
    label: 'Eclipsing Binary',
    group: ClassGroup.variables,
    blurb: 'Two stars orbiting in our line of sight that periodically dim as they pass in front of each other.',
  ),
  'EB/EW': ClassMetadata(
    code: 'EB/EW',
    label: 'Contact / Near-Contact Eclipsing Binary',
    group: ClassGroup.variables,
    blurb: 'Close pair of stars sharing or nearly sharing an outer atmosphere.',
  ),
  'EA': ClassMetadata(
    code: 'EA',
    label: 'Detached Eclipsing Binary (Algol-type)',
    group: ClassGroup.variables,
    blurb: 'Well-separated binary stars with sharp eclipse dips.',
  ),
  'LPV': ClassMetadata(
    code: 'LPV',
    label: 'Long-Period Variable',
    group: ClassGroup.variables,
    blurb: 'Cool red giant or asymptotic giant branch star pulsating over months to years.',
  ),
  'YSO': ClassMetadata(
    code: 'YSO',
    label: 'Young Stellar Object',
    group: ClassGroup.variables,
    blurb: 'Protostar or pre-main-sequence star flickering as it accretes gas and dust.',
  ),
  'DSCT': ClassMetadata(
    code: 'DSCT',
    label: 'Delta Scuti Variable',
    group: ClassGroup.variables,
    blurb: 'Short-period pulsating star oscillating over hours.',
  ),
  'Periodic-Other': ClassMetadata(
    code: 'Periodic-Other',
    label: 'Periodic Variable Star',
    group: ClassGroup.variables,
    blurb: 'Star exhibiting repeating brightness variations.',
  ),
  'AGN': ClassMetadata(
    code: 'AGN',
    label: 'Active Galactic Nucleus',
    group: ClassGroup.agn,
    blurb: 'Accreting supermassive black hole at a galaxy’s core flickering across weeks and months.',
  ),
  'QSO': ClassMetadata(
    code: 'QSO',
    label: 'Quasar',
    group: ClassGroup.agn,
    blurb: 'Luminous distant active galaxy powered by a rapidly feeding supermassive black hole.',
  ),
  'Blazar': ClassMetadata(
    code: 'Blazar',
    label: 'Blazar',
    group: ClassGroup.agn,
    blurb: 'Active galaxy with a relativistic jet pointed nearly straight toward Earth.',
  ),
  'asteroid': ClassMetadata(
    code: 'asteroid',
    label: 'Solar System Object (Asteroid)',
    group: ClassGroup.solar,
    blurb: 'Moving minor planet or comet caught crossing the survey camera field.',
  ),
  'SSO': ClassMetadata(
    code: 'SSO',
    label: 'Solar System Object',
    group: ClassGroup.solar,
    blurb: 'Moving minor planet or comet caught crossing the survey camera field.',
  ),
  'bogus': ClassMetadata(
    code: 'bogus',
    label: 'Instrument / Subtraction Artifact',
    group: ClassGroup.other,
    blurb: 'Likely image-subtraction ghost, cosmic ray, or satellite glint.',
  ),
};

ClassMetadata classInfo(String? code) {
  if (code == null || code.isEmpty) {
    return const ClassMetadata(
      code: 'unclassified',
      label: 'Unclassified Alert',
      group: ClassGroup.other,
      blurb: 'Alert awaiting automated stamp or light-curve classification.',
    );
  }
  return _catalog[code] ??
      ClassMetadata(
        code: code,
        label: code,
        group: ClassGroup.variables,
        blurb: 'Astronomical alert classified by ALeRCE as $code.',
      );
}

ClassGroup groupOf(String? code) => classInfo(code).group;
