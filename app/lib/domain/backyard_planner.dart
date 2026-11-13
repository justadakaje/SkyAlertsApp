import 'dart:math' as math;

import '../data/firestore_repository.dart';

const double _degToRad = math.pi / 180.0;
const double _radToDeg = 180.0 / math.pi;

enum ScopePreset {
  seestarS50(
    id: 'seestar_s50',
    label: 'ZWO Seestar S50',
    shortLabel: 'Seestar S50',
    apertureMm: 50,
    limitingMag: 16.5,
    fovNote: '1.27° × 0.71° FOV · 50 mm f/5',
  ),
  seestarS30(
    id: 'seestar_s30',
    label: 'ZWO Seestar S30',
    shortLabel: 'Seestar S30',
    apertureMm: 30,
    limitingMag: 15.5,
    fovNote: '2.46° × 1.38° FOV · 30 mm f/5',
  ),
  dwarf3(
    id: 'dwarf_3',
    label: 'DWARF 3',
    shortLabel: 'DWARF 3',
    apertureMm: 35,
    limitingMag: 15.8,
    fovNote: '3.0° × 1.7° FOV · 35 mm f/4.3',
  ),
  unistellar(
    id: 'unistellar',
    label: 'Unistellar eVscope / Odyssey',
    shortLabel: 'Unistellar',
    apertureMm: 114,
    limitingMag: 17.5,
    fovNote: '0.6° × 0.45° FOV · 114 mm',
  ),
  visual8(
    id: 'visual_8',
    label: '8" Visual / Dobsonian',
    shortLabel: '8" Visual',
    apertureMm: 203,
    limitingMag: 14.0,
    fovNote: 'Visual eyepiece · 203 mm',
  ),
  astrograph8(
    id: 'astrograph_8',
    label: '8" Imaging Rig (Cooled CMOS)',
    shortLabel: '8" Astrograph',
    apertureMm: 203,
    limitingMag: 19.0,
    fovNote: 'Dedicated astrograph · 203 mm',
  ),
  binoculars(
    id: 'binoculars_10x50',
    label: '10×50 Binoculars / Naked Eye',
    shortLabel: '10×50 Binocs',
    apertureMm: 50,
    limitingMag: 9.5,
    fovNote: 'Wide-field handheld · 50 mm',
  );

  const ScopePreset({
    required this.id,
    required this.label,
    required this.shortLabel,
    required this.apertureMm,
    required this.limitingMag,
    required this.fovNote,
  });

  final String id;
  final String label;
  final String shortLabel;
  final int apertureMm;
  final double limitingMag;
  final String fovNote;
}

class ObservatoryLocation {
  const ObservatoryLocation({
    required this.latitudeDeg,
    required this.longitudeDeg,
    this.label = 'Custom Backyard',
  });

  final double latitudeDeg;
  final double longitudeDeg;
  final String label;

  /// Rounds coordinates to 0.1° (~10 km) for privacy-preserving sync.
  ObservatoryLocation get roundedToTenth => ObservatoryLocation(
        latitudeDeg: (latitudeDeg * 10.0).round() / 10.0,
        longitudeDeg: (longitudeDeg * 10.0).round() / 10.0,
        label: label,
      );

  static const List<ObservatoryLocation> presets = [
    ObservatoryLocation(latitudeDeg: 40.0, longitudeDeg: -75.0, label: 'US East (~40°N, 75°W)'),
    ObservatoryLocation(latitudeDeg: 34.0, longitudeDeg: -118.2, label: 'US West (~34°N, 118°W)'),
    ObservatoryLocation(latitudeDeg: 51.5, longitudeDeg: -0.1, label: 'UK / Europe (~51.5°N, 0°W)'),
    ObservatoryLocation(latitudeDeg: -33.9, longitudeDeg: 151.2, label: 'Australia (~33.9°S, 151°E)'),
    ObservatoryLocation(latitudeDeg: -30.2, longitudeDeg: -70.7, label: 'Chile / Rubin (~30.2°S, 71°W)'),
  ];
}

class NightSample {
  const NightSample({
    required this.utc,
    required this.altDeg,
    required this.azDeg,
    required this.sunAltDeg,
    required this.moonSepDeg,
  });

  final DateTime utc;
  final double altDeg;
  final double azDeg;
  final double sunAltDeg;
  final double moonSepDeg;

  bool get isDark => sunAltDeg <= -12.0;
}

class NightWindowSummary {
  const NightWindowSummary({
    required this.windowStartUtc,
    required this.windowEndUtc,
    required this.darkStartUtc,
    required this.darkEndUtc,
    required this.moonIllumPercent,
    required this.hasDarkSky,
  });

  final DateTime windowStartUtc;
  final DateTime windowEndUtc;
  final DateTime? darkStartUtc;
  final DateTime? darkEndUtc;
  final int moonIllumPercent;
  final bool hasDarkSky;
}

class PlannedTarget {
  const PlannedTarget({
    required this.object,
    required this.reachable,
    required this.visibleTonight,
    required this.peakAltDeg,
    required this.peakAzDeg,
    required this.airmassAtPeak,
    required this.moonSepDeg,
    required this.moonIllumPercent,
    required this.bestTimeUtc,
    required this.windowStartUtc,
    required this.windowEndUtc,
    required this.windowMinutes,
    required this.samples,
    required this.score,
    required this.statusLine,
  });

  final CatalogObject object;
  final bool reachable;
  final bool visibleTonight;
  final double peakAltDeg;
  final double peakAzDeg;
  final double? airmassAtPeak;
  final double moonSepDeg;
  final int moonIllumPercent;
  final DateTime bestTimeUtc;
  final DateTime? windowStartUtc;
  final DateTime? windowEndUtc;
  final int windowMinutes;
  final List<NightSample> samples;
  final double score;
  final String statusLine;

  double? get effectiveMag => object.effectiveMag;
}

/// Days since J2000.0 (2000-01-01T12:00:00Z).
double _daysSinceJ2000(DateTime utc) {
  final j2000 = DateTime.utc(2000, 1, 1, 12);
  return utc.toUtc().difference(j2000).inMicroseconds / 86400000000.0;
}

double _normDeg(double deg) {
  final m = deg % 360.0;
  return m < 0 ? m + 360.0 : m;
}

/// Greenwich Mean Sidereal Time in degrees [0, 360).
double gmstDeg(DateTime utc) {
  final d = _daysSinceJ2000(utc);
  return _normDeg(280.46061837 + 360.98564736629 * d);
}

/// Local Sidereal Time in degrees [0, 360).
double lstDeg(DateTime utc, double longitudeDeg) {
  return _normDeg(gmstDeg(utc) + longitudeDeg);
}

/// Converts Equatorial J2000 (RA, Dec in degrees) to Horizontal (Alt, Az in degrees)
/// and Kasten-Young airmass (null if below horizon).
({double altDeg, double azDeg, double? airmass}) equatorialToHorizontal({
  required double raDeg,
  required double decDeg,
  required double latitudeDeg,
  required double longitudeDeg,
  required DateTime utc,
}) {
  final haRad = _normDeg(lstDeg(utc, longitudeDeg) - raDeg) * _degToRad;
  final decRad = decDeg * _degToRad;
  final latRad = latitudeDeg * _degToRad;

  final sinAlt = math.sin(decRad) * math.sin(latRad) +
      math.cos(decRad) * math.cos(latRad) * math.cos(haRad);
  final altRad = math.asin(sinAlt.clamp(-1.0, 1.0));
  final altDeg = altRad * _radToDeg;

  final y = -math.sin(haRad) * math.cos(decRad);
  final x = math.cos(latRad) * math.sin(decRad) -
      math.sin(latRad) * math.cos(decRad) * math.cos(haRad);
  final azDeg = _normDeg(math.atan2(y, x) * _radToDeg);

  double? airmass;
  if (altDeg > 0.0) {
    final denom = math.sin(altRad) + 0.50572 * math.pow(altDeg + 6.07995, -1.6364);
    if (denom > 0.0) {
      airmass = (1.0 / denom).clamp(1.0, 38.0);
    }
  }
  return (altDeg: altDeg, azDeg: azDeg, airmass: airmass);
}

/// Angular separation in degrees between two J2000 points.
double angularSeparationDeg(double ra1Deg, double dec1Deg, double ra2Deg, double dec2Deg) {
  final r1 = ra1Deg * _degToRad;
  final d1 = dec1Deg * _degToRad;
  final r2 = ra2Deg * _degToRad;
  final d2 = dec2Deg * _degToRad;
  final cosSep = math.sin(d1) * math.sin(d2) +
      math.cos(d1) * math.cos(d2) * math.cos(r1 - r2);
  return math.acos(cosSep.clamp(-1.0, 1.0)) * _radToDeg;
}

/// Low-precision solar equatorial position (~0.01° accuracy, ideal for twilight).
({double raDeg, double decDeg, double eclLonDeg}) sunEquatorial(DateTime utc) {
  final d = _daysSinceJ2000(utc);
  final g = _normDeg(357.529 + 0.98560028 * d) * _degToRad;
  final q = _normDeg(280.459 + 0.98564736 * d);
  final lDeg = _normDeg(q + 1.915 * math.sin(g) + 0.020 * math.sin(2.0 * g));
  final l = lDeg * _degToRad;
  final eps = (23.439 - 0.00000036 * d) * _degToRad;

  final raDeg = _normDeg(math.atan2(math.cos(eps) * math.sin(l), math.cos(l)) * _radToDeg);
  final decDeg = math.asin((math.sin(eps) * math.sin(l)).clamp(-1.0, 1.0)) * _radToDeg;
  return (raDeg: raDeg, decDeg: decDeg, eclLonDeg: lDeg);
}

/// Low-precision lunar equatorial position & illuminated fraction (~1° accuracy).
({double raDeg, double decDeg, double illumFraction}) moonEquatorialAndPhase(DateTime utc) {
  final d = _daysSinceJ2000(utc);
  final l0 = _normDeg(218.316 + 13.176396 * d);
  final m = _normDeg(134.963 + 13.064993 * d) * _degToRad;
  final f = _normDeg(93.272 + 13.229350 * d) * _degToRad;

  final lambdaDeg = l0 + 6.289 * math.sin(m);
  final betaDeg = 5.128 * math.sin(f);
  final lambda = lambdaDeg * _degToRad;
  final beta = betaDeg * _degToRad;
  final eps = (23.439 - 0.00000036 * d) * _degToRad;

  final sinDec = math.sin(beta) * math.cos(eps) +
      math.cos(beta) * math.sin(eps) * math.sin(lambda);
  final decDeg = math.asin(sinDec.clamp(-1.0, 1.0)) * _radToDeg;
  final y = math.sin(lambda) * math.cos(eps) - math.tan(beta) * math.sin(eps);
  final x = math.cos(lambda);
  final raDeg = _normDeg(math.atan2(y, x) * _radToDeg);

  final sun = sunEquatorial(utc);
  final elongRad = _normDeg(lambdaDeg - sun.eclLonDeg) * _degToRad;
  final illumFraction = ((1.0 - math.cos(elongRad)) / 2.0).clamp(0.0, 1.0);
  return (raDeg: raDeg, decDeg: decDeg, illumFraction: illumFraction);
}

/// Returns a 24h-anchored UTC start around local sunset for tonight's observing window.
({DateTime startUtc, int stepMinutes, int steps}) _nightGrid(
  ObservatoryLocation loc,
  DateTime nowUtc,
) {
  // Approximate local solar time offset in hours from longitude.
  final approxOffsetHours = (loc.longitudeDeg / 15.0).round();
  final localNow = nowUtc.toUtc().add(Duration(hours: approxOffsetHours));
  // If before 08:00 local, "tonight" started yesterday evening.
  final eveningDate = localNow.hour < 8
      ? DateTime.utc(localNow.year, localNow.month, localNow.day)
          .subtract(const Duration(days: 1))
      : DateTime.utc(localNow.year, localNow.month, localNow.day);
  final startLocal = eveningDate.add(const Duration(hours: 17));
  final startUtc = startLocal.subtract(Duration(hours: approxOffsetHours));
  return (startUtc: startUtc, stepMinutes: 20, steps: 42); // 17:00 -> 07:00 local (14h)
}

NightWindowSummary summarizeTonight(
  ObservatoryLocation loc, {
  DateTime? nowUtc,
}) {
  final ref = (nowUtc ?? DateTime.now().toUtc()).toUtc();
  final grid = _nightGrid(loc, ref);
  DateTime? darkStart;
  DateTime? darkEnd;

  for (var i = 0; i <= grid.steps; i++) {
    final t = grid.startUtc.add(Duration(minutes: i * grid.stepMinutes));
    final sun = sunEquatorial(t);
    final sunHoriz = equatorialToHorizontal(
      raDeg: sun.raDeg,
      decDeg: sun.decDeg,
      latitudeDeg: loc.latitudeDeg,
      longitudeDeg: loc.longitudeDeg,
      utc: t,
    );
    if (sunHoriz.altDeg <= -12.0) {
      darkStart ??= t;
      darkEnd = t;
    }
  }

  final midNight = darkStart != null && darkEnd != null
      ? darkStart.add(darkEnd.difference(darkStart) ~/ 2)
      : grid.startUtc.add(const Duration(hours: 7));
  final moon = moonEquatorialAndPhase(midNight);

  return NightWindowSummary(
    windowStartUtc: grid.startUtc,
    windowEndUtc: grid.startUtc.add(Duration(minutes: grid.steps * grid.stepMinutes)),
    darkStartUtc: darkStart,
    darkEndUtc: darkEnd,
    moonIllumPercent: (moon.illumFraction * 100.0).round(),
    hasDarkSky: darkStart != null && darkEnd != null,
  );
}

PlannedTarget? planTarget(
  CatalogObject obj,
  ObservatoryLocation loc,
  ScopePreset scope, {
  DateTime? nowUtc,
  double minAltDeg = 30.0,
  double minMoonSepDeg = 20.0,
}) {
  final ra = obj.meanRa;
  final dec = obj.meanDec;
  if (ra == null || dec == null || !ra.isFinite || !dec.isFinite) {
    return null;
  }

  final ref = (nowUtc ?? DateTime.now().toUtc()).toUtc();
  final grid = _nightGrid(loc, ref);
  final samples = <NightSample>[];

  var peakAlt = -90.0;
  var peakAz = 0.0;
  double? peakAirmass;
  var bestTime = grid.startUtc;
  var moonSepAtBest = 180.0;

  DateTime? bestRunStart;
  DateTime? bestRunEnd;
  var bestRunSteps = 0;
  DateTime? curRunStart;
  var curRunSteps = 0;

  for (var i = 0; i <= grid.steps; i++) {
    final t = grid.startUtc.add(Duration(minutes: i * grid.stepMinutes));
    final horiz = equatorialToHorizontal(
      raDeg: ra,
      decDeg: dec,
      latitudeDeg: loc.latitudeDeg,
      longitudeDeg: loc.longitudeDeg,
      utc: t,
    );
    final sun = sunEquatorial(t);
    final sunHoriz = equatorialToHorizontal(
      raDeg: sun.raDeg,
      decDeg: sun.decDeg,
      latitudeDeg: loc.latitudeDeg,
      longitudeDeg: loc.longitudeDeg,
      utc: t,
    );
    final moon = moonEquatorialAndPhase(t);
    final moonSep = angularSeparationDeg(ra, dec, moon.raDeg, moon.decDeg);

    final sample = NightSample(
      utc: t,
      altDeg: horiz.altDeg,
      azDeg: horiz.azDeg,
      sunAltDeg: sunHoriz.altDeg,
      moonSepDeg: moonSep,
    );
    samples.add(sample);

    if (sample.isDark && horiz.altDeg > peakAlt) {
      peakAlt = horiz.altDeg;
      peakAz = horiz.azDeg;
      peakAirmass = horiz.airmass;
      bestTime = t;
      moonSepAtBest = moonSep;
    }

    final inWindow = sample.isDark && horiz.altDeg >= minAltDeg && moonSep >= minMoonSepDeg;
    if (inWindow) {
      curRunStart ??= t;
      curRunSteps += 1;
      if (curRunSteps > bestRunSteps) {
        bestRunSteps = curRunSteps;
        bestRunStart = curRunStart;
        bestRunEnd = t.add(Duration(minutes: grid.stepMinutes));
      }
    } else {
      curRunStart = null;
      curRunSteps = 0;
    }
  }

  // Fallback if no dark samples exist (e.g. polar summer)
  if (peakAlt <= -90.0 && samples.isNotEmpty) {
    for (final s in samples) {
      if (s.altDeg > peakAlt) {
        peakAlt = s.altDeg;
        peakAz = s.azDeg;
        bestTime = s.utc;
        moonSepAtBest = s.moonSepDeg;
      }
    }
  }

  final moonAtBest = moonEquatorialAndPhase(bestTime);
  final moonIllum = (moonAtBest.illumFraction * 100.0).round();
  final windowMinutes = bestRunSteps * grid.stepMinutes;
  final visibleTonight = peakAlt >= minAltDeg && windowMinutes >= grid.stepMinutes;

  final effMag = obj.effectiveMag;
  final magReachable = effMag != null && effMag <= scope.limitingMag;
  final reachable = visibleTonight && magReachable;

  // Score: prioritize reachable targets, bright margin, high altitude, and long window.
  double score = 0.0;
  if (visibleTonight) score += 40.0;
  if (magReachable) {
    score += 50.0 + ((scope.limitingMag - effMag).clamp(0.0, 10.0) * 3.0);
  } else if (effMag != null) {
    score -= (effMag - scope.limitingMag).clamp(0.0, 10.0) * 4.0;
  }
  score += (peakAlt.clamp(0.0, 90.0) / 90.0) * 20.0;
  score += (windowMinutes.clamp(0, 360) / 360.0) * 15.0;
  score += (moonSepAtBest.clamp(0.0, 120.0) / 120.0) * 5.0;

  final String statusLine;
  if (reachable) {
    statusLine =
        'Reachable · Peak ${peakAlt.round()}° · ${_formatDurationMinutes(windowMinutes)} window';
  } else if (!visibleTonight) {
    statusLine = peakAlt < minAltDeg
        ? 'Below ${minAltDeg.round()}° min altitude (peak ${peakAlt.round()}°)'
        : 'Moon too close (${moonSepAtBest.round()}° < ${minMoonSepDeg.round()}°)';
  } else if (effMag == null) {
    statusLine = 'Visible (peak ${peakAlt.round()}°) · Magnitude unmeasured';
  } else {
    statusLine =
        'Too faint for ${scope.shortLabel} (${effMag.toStringAsFixed(1)} > ${scope.limitingMag.toStringAsFixed(1)} mag)';
  }

  return PlannedTarget(
    object: obj,
    reachable: reachable,
    visibleTonight: visibleTonight,
    peakAltDeg: peakAlt,
    peakAzDeg: peakAz,
    airmassAtPeak: peakAirmass,
    moonSepDeg: moonSepAtBest,
    moonIllumPercent: moonIllum,
    bestTimeUtc: bestTime,
    windowStartUtc: bestRunStart,
    windowEndUtc: bestRunEnd,
    windowMinutes: windowMinutes,
    samples: samples,
    score: score,
    statusLine: statusLine,
  );
}

List<PlannedTarget> rankBackyardTargets(
  List<CatalogObject> objects,
  ObservatoryLocation loc,
  ScopePreset scope, {
  DateTime? nowUtc,
  double minAltDeg = 30.0,
  double minMoonSepDeg = 20.0,
  bool onlyReachable = false,
}) {
  final planned = <PlannedTarget>[];
  for (final obj in objects) {
    final p = planTarget(
      obj,
      loc,
      scope,
      nowUtc: nowUtc,
      minAltDeg: minAltDeg,
      minMoonSepDeg: minMoonSepDeg,
    );
    if (p == null) continue;
    if (onlyReachable && !p.reachable) continue;
    planned.add(p);
  }
  planned.sort((a, b) => b.score.compareTo(a.score));
  return planned;
}

String _formatDurationMinutes(int minutes) {
  final h = minutes ~/ 60;
  final m = minutes % 60;
  if (h == 0) return '${m}m';
  if (m == 0) return '${h}h';
  return '${h}h ${m}m';
}

/// Formats RA in colon-separated sexagesimal `HH:MM:SS.s` (Seestar/ASIAIR/N.I.N.A.).
String formatRaColon(double? raDeg) {
  if (raDeg == null || !raDeg.isFinite) return '—';
  final norm = _normDeg(raDeg);
  final totalSeconds = (norm / 15.0) * 3600.0;
  final h = (totalSeconds ~/ 3600) % 24;
  final m = (totalSeconds ~/ 60) % 60;
  final s = totalSeconds - (h * 3600 + m * 60);
  return '${h.toString().padLeft(2, '0')}:${m.toString().padLeft(2, '0')}:${s.toStringAsFixed(1).padLeft(4, '0')}';
}

/// Formats Dec in colon-separated sexagesimal `+DD:MM:SS` (Seestar/ASIAIR/N.I.N.A.).
String formatDecColon(double? decDeg) {
  if (decDeg == null || !decDeg.isFinite) return '—';
  final sign = decDeg < 0 ? '-' : '+';
  final totalArcsec = decDeg.abs() * 3600.0;
  final d = totalArcsec ~/ 3600;
  final m = (totalArcsec ~/ 60) % 60;
  final s = (totalArcsec % 60).round();
  return '$sign${d.toString().padLeft(2, '0')}:${m.toString().padLeft(2, '0')}:${s.toString().padLeft(2, '0')}';
}

/// Formats J2000 coordinates for smart-telescope / N.I.N.A. clipboard copy.
String formatCoordinatesForRig(CatalogObject obj) {
  final ra = obj.meanRa;
  final dec = obj.meanDec;
  if (ra == null || dec == null) return obj.displayLabel;
  return '${formatRaColon(ra)} ${formatDecColon(dec)} '
      '(J2000: ${ra.toStringAsFixed(5)}°, ${dec.toStringAsFixed(5)}°)';
}

/// Exports planned targets to N.I.N.A./CSV-compatible rows.
String exportPlannedTargetsCsv(List<PlannedTarget> targets) {
  final buf = StringBuffer()
    ..writeln('name,survey,oid,ra_hms,dec_dms,ra_deg,dec_deg,mag,peak_alt_deg,window_min,moon_sep_deg');
  for (final t in targets) {
    final o = t.object;
    final name = o.displayLabel.replaceAll(',', ' ');
    final mag = o.effectiveMag?.toStringAsFixed(2) ?? '';
    final raDeg = o.meanRa?.toStringAsFixed(6) ?? '';
    final decDeg = o.meanDec?.toStringAsFixed(6) ?? '';
    buf.writeln(
      '$name,${o.survey},${o.oid},${formatRaColon(o.meanRa)},${formatDecColon(o.meanDec)},'
      '$raDeg,$decDeg,$mag,${t.peakAltDeg.toStringAsFixed(1)},${t.windowMinutes},${t.moonSepDeg.toStringAsFixed(1)}',
    );
  }
  return buf.toString();
}
