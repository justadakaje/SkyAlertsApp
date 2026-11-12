import 'dart:math' as math;

const double mjdUnixEpoch = 40587.0;
const double _degToRad = math.pi / 180.0;
const double _radToDeg = 180.0 / math.pi;

// North Galactic Pole in J2000 equatorial coordinates (degrees).
const double _alphaG = 192.85948 * _degToRad;
const double _deltaG = 27.12825 * _degToRad;
const double _lOmega = 32.93192 * _degToRad;

DateTime mjdToDate(double mjd) {
  final millis = ((mjd - mjdUnixEpoch) * 86400000.0).round();
  return DateTime.fromMillisecondsSinceEpoch(millis, isUtc: true);
}

double dateToMjd(DateTime dt) {
  return dt.toUtc().millisecondsSinceEpoch / 86400000.0 + mjdUnixEpoch;
}

String formatRa(double? raDeg) {
  if (raDeg == null || !raDeg.isFinite) return '—';
  final norm = ((raDeg % 360.0) + 360.0) % 360.0;
  final totalSeconds = (norm / 15.0) * 3600.0;
  final h = (totalSeconds ~/ 3600) % 24;
  final m = (totalSeconds ~/ 60) % 60;
  final s = totalSeconds - (h * 3600 + m * 60);
  final hh = h.toString().padLeft(2, '0');
  final mm = m.toString().padLeft(2, '0');
  final ss = s.toStringAsFixed(1).padLeft(4, '0');
  return '${hh}h ${mm}m ${ss}s';
}

String formatDec(double? decDeg) {
  if (decDeg == null || !decDeg.isFinite) return '—';
  final sign = decDeg < 0 ? '−' : '+';
  final absDeg = decDeg.abs();
  final totalArcsec = absDeg * 3600.0;
  final d = totalArcsec ~/ 3600;
  final m = (totalArcsec ~/ 60) % 60;
  final s = (totalArcsec % 60).round();
  final dd = d.toString().padLeft(2, '0');
  final mm = m.toString().padLeft(2, '0');
  final ss = s.toString().padLeft(2, '0');
  return '$sign$dd° $mm′ $ss″';
}

/// Converts Galactic (l, b in degrees) to Equatorial J2000 (RA, Dec in degrees).
({double ra, double dec}) galacticToEquatorial(double lDeg, double bDeg) {
  final l = lDeg * _degToRad;
  final b = bDeg * _degToRad;
  final sinDec = math.sin(b) * math.sin(_deltaG) +
      math.cos(b) * math.cos(_deltaG) * math.sin(l - _lOmega);
  final dec = math.asin(sinDec.clamp(-1.0, 1.0));
  final y = math.cos(b) * math.cos(l - _lOmega);
  final x = math.sin(b) * math.cos(_deltaG) -
      math.cos(b) * math.sin(_deltaG) * math.sin(l - _lOmega);
  final ra = (math.atan2(y, x) + _alphaG) * _radToDeg;
  return (ra: ((ra % 360.0) + 360.0) % 360.0, dec: dec * _radToDeg);
}

/// Returns Galactic latitude b in degrees for J2000 (RA, Dec).
double galacticLatitude(double raDeg, double decDeg) {
  final ra = raDeg * _degToRad;
  final dec = decDeg * _degToRad;
  final sinB = math.sin(dec) * math.sin(_deltaG) +
      math.cos(dec) * math.cos(_deltaG) * math.cos(ra - _alphaG);
  return math.asin(sinB.clamp(-1.0, 1.0)) * _radToDeg;
}

/// Plain-language sky region & mid-northern (~40°N) visibility note.
String? skyRegion(double? raDeg, double? decDeg) {
  if (raDeg == null || decDeg == null || !raDeg.isFinite || !decDeg.isFinite) {
    return null;
  }
  final bAbs = galacticLatitude(raDeg, decDeg).abs();
  final planeNote = bAbs < 15.0
      ? 'Near the Milky Way plane'
      : (bAbs > 50.0 ? 'High above the Milky Way plane' : 'Mid-galactic latitude');
  final String visNote;
  if (decDeg >= 50.0) {
    visNote = 'circumpolar from ~40°N';
  } else if (decDeg >= -15.0) {
    visNote = 'visible from both hemispheres (~40°N friendly)';
  } else if (decDeg >= -45.0) {
    visNote = 'low in the southern sky from ~40°N; best from the Southern Hemisphere';
  } else {
    visNote = 'far-southern sky (below the horizon from ~40°N)';
  }
  return '$planeNote · $visNote';
}
