class GearRecommendation {
  const GearRecommendation({
    required this.id,
    required this.name,
    required this.tagline,
    required this.specsNote,
    required this.maxReachableMag,
    required this.url,
    required this.categoryBadge,
  });

  final String id;
  final String name;
  final String tagline;
  final String specsNote;
  final double maxReachableMag;
  final String url;
  final String categoryBadge;
}

const String ftcAffiliateDisclosure =
    'Affiliate disclosure: As an Amazon Associate I earn from qualifying purchases. '
    'Gear suggestions are matched by optical limiting magnitude and never affect scientific alert rankings.';

const GearRecommendation _binocs10x50 = GearRecommendation(
  id: 'celestron_10x50',
  name: '10×50 Wide-Field Astronomy Binoculars',
  tagline: 'Grab-and-go sweep for bright comets, novae, and conjunctions',
  specsNote: '50 mm objective · up to ~9.5 mag under dark skies',
  maxReachableMag: 9.5,
  url: 'https://www.amazon.com/s?k=10x50+astronomy+binoculars&tag=skyalerts-20',
  categoryBadge: 'Wide-Field (≤9.5 mag)',
);

const GearRecommendation _seestarS30 = GearRecommendation(
  id: 'zwo_seestar_s30',
  name: 'ZWO Seestar S30 Smart Telescope',
  tagline: 'Ultra-portable 30 mm smart astrograph for bright supernovae & comets',
  specsNote: '30 mm APO triplet · 2.46° FOV · ~15.5 mag',
  maxReachableMag: 15.5,
  url: 'https://www.amazon.com/s?k=ZWO+Seestar+S30&tag=skyalerts-20',
  categoryBadge: 'Smart Scope (≤15.5 mag)',
);

const GearRecommendation _seestarS50 = GearRecommendation(
  id: 'zwo_seestar_s50',
  name: 'ZWO Seestar S50 All-in-One Smart Scope',
  tagline: 'Automated plate-solving & stacking down to mag 16.5 in 30–60 min',
  specsNote: '50 mm f/5 APO · 1.27° FOV · ~16.5 mag',
  maxReachableMag: 16.5,
  url: 'https://www.amazon.com/s?k=ZWO+Seestar+S50&tag=skyalerts-20',
  categoryBadge: 'Smart Scope (≤16.5 mag)',
);

const GearRecommendation _dwarf3 = GearRecommendation(
  id: 'dwarflab_dwarf_3',
  name: 'DWARF 3 Dual-Lens Smart Telescope',
  tagline: 'Telephoto + wide-field smart rig for bright transients and NEOs',
  specsNote: '35 mm f/4.3 APO · 3.0° FOV · ~15.8 mag',
  maxReachableMag: 15.8,
  url: 'https://www.amazon.com/s?k=DWARF+3+smart+telescope&tag=skyalerts-20',
  categoryBadge: 'Smart Scope (≤15.8 mag)',
);

const GearRecommendation _unistellarOdyssey = GearRecommendation(
  id: 'unistellar_odyssey',
  name: 'Unistellar Odyssey / eVscope Smart Telescope',
  tagline: 'Nikon-optics 114 mm reflector built for faint supernovae & AGN',
  specsNote: '114 mm f/3.9 · Enhanced Vision · ~17.5 mag',
  maxReachableMag: 17.5,
  url: 'https://www.amazon.com/s?k=Unistellar+Odyssey+smart+telescope&tag=skyalerts-20',
  categoryBadge: 'Deep Smart Scope (≤17.5 mag)',
);

const GearRecommendation _astrograph8 = GearRecommendation(
  id: '8in_f4_astrograph',
  name: '8" f/4 Imaging Newtonian Astrograph + Cooled CMOS',
  tagline: 'Fast 203 mm light bucket for faint ZTF & Rubin transients',
  specsNote: '203 mm f/4 · long-exposure guided · ~19.0+ mag',
  maxReachableMag: 19.0,
  url: 'https://www.amazon.com/s?k=8+inch+f4+imaging+newtonian+telescope&tag=skyalerts-20',
  categoryBadge: 'Deep Astrograph (≤19+ mag)',
);

/// Returns 2 contextual gear recommendations capable of reaching [mag].
List<GearRecommendation> recommendGearForMagnitude(double? mag) {
  if (mag != null && mag <= 10.5) {
    return const [_binocs10x50, _seestarS30];
  }
  if (mag != null && mag <= 16.5) {
    return const [_seestarS50, _dwarf3];
  }
  return const [_unistellarOdyssey, _astrograph8];
}
