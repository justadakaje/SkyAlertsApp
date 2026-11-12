import 'dart:math' as math;

import 'astro.dart';
import 'classes.dart';
import 'solar.dart';

const List<String> _months = [
  'Jan',
  'Feb',
  'Mar',
  'Apr',
  'May',
  'Jun',
  'Jul',
  'Aug',
  'Sep',
  'Oct',
  'Nov',
  'Dec',
];

String formatUtc(double? mjd) {
  if (mjd == null || !mjd.isFinite) return '—';
  final dt = mjdToDate(mjd);
  final mon = _months[dt.month - 1];
  final dd = dt.day.toString().padLeft(2, '0');
  final hh = dt.hour.toString().padLeft(2, '0');
  final mm = dt.minute.toString().padLeft(2, '0');
  return '${dt.year} $mon $dd $hh:$mm UTC';
}

String formatAgo(double? mjd, {DateTime? now}) {
  if (mjd == null || !mjd.isFinite) return '—';
  final ref = (now ?? DateTime.now()).toUtc();
  final dt = mjdToDate(mjd);
  final diffHours = ref.difference(dt).inMinutes / 60.0;
  if (diffHours < 1.0) return 'just now';
  if (diffHours < 24.0) {
    final h = diffHours.round();
    return '$h ${h == 1 ? 'hour' : 'hours'} ago';
  }
  final d = (diffHours / 24.0).round();
  return '$d ${d == 1 ? 'day' : 'days'} ago';
}

String formatProbability(double? prob) {
  if (prob == null || !prob.isFinite) return '—';
  return '${(prob.clamp(0.0, 1.0) * 100.0).round()}%';
}

String formatCount(int? n) {
  if (n == null) return '—';
  final s = n.abs().toString();
  final buf = StringBuffer();
  for (var i = 0; i < s.length; i++) {
    if (i > 0 && (s.length - i) % 3 == 0) buf.write(',');
    buf.write(s[i]);
  }
  return n < 0 ? '-$buf' : buf.toString();
}

/// Converts peak magnitude to a plain-language comparison vs naked-eye limit (mag 6).
String? humanBrightness(double? peakMag, {String? band}) {
  if (peakMag == null || !peakMag.isFinite) return null;
  final magStr = peakMag.toStringAsFixed(1);
  final bandLabel = (band != null && band.isNotEmpty) ? ' ($band-band)' : '';
  if (peakMag <= 6.0) {
    return 'mag $magStr$bandLabel — bright enough to see with the naked eye from a dark site';
  }
  final faintFactor = math.pow(10.0, 0.4 * (peakMag - 6.0)).round();
  final factorStr = formatCount(faintFactor);
  final String instrument;
  if (peakMag <= 9.5) {
    instrument = 'reachable with binoculars';
  } else if (peakMag <= 14.0) {
    instrument = 'reachable with a backyard telescope';
  } else {
    instrument = 'requires a research telescope or long camera exposure';
  }
  return 'mag $magStr$bandLabel — ~$factorStr× fainter than the naked-eye limit ($instrument)';
}

class HighlightCardModel {
  const HighlightCardModel({
    required this.kind,
    required this.eyebrow,
    required this.survey,
    required this.oid,
    required this.headline,
    required this.subtitle,
  });

  final String kind; // 'explosion' | 'active' | 'solar'
  final String eyebrow;
  final String survey;
  final String oid;
  final String headline;
  final String subtitle;
}

/// Builds up to 3 "What stood out" highlight cards from recent catalog objects.
List<HighlightCardModel> pickHomeHighlights(List<Map<String, dynamic>> rows) {
  final out = <HighlightCardModel>[];
  final usedKeys = <String>{};

  String keyOf(Map<String, dynamic> r) => '${r['survey']}_${r['oid']}';

  final explosions = rows
      .where((r) => transientClasses.contains(r['top_class']))
      .toList()
    ..sort((a, b) {
      final pa = (a['top_probability'] as num?)?.toDouble() ?? 0.0;
      final pb = (b['top_probability'] as num?)?.toDouble() ?? 0.0;
      if (pb != pa) return pb.compareTo(pa);
      final la = (a['lastmjd'] as num?)?.toDouble() ?? 0.0;
      final lb = (b['lastmjd'] as num?)?.toDouble() ?? 0.0;
      return lb.compareTo(la);
    });

  if (explosions.isNotEmpty) {
    final top = explosions.first;
    usedKeys.add(keyOf(top));
    final info = classInfo(top['top_class'] as String?);
    final prob = formatProbability((top['top_probability'] as num?)?.toDouble());
    out.add(
      HighlightCardModel(
        kind: 'explosion',
        eyebrow: 'Standout cosmic explosion',
        survey: '${top['survey']}',
        oid: '${top['oid']}',
        headline: '${info.label} (${top['oid']})',
        subtitle: '$prob confidence · ${info.blurb}',
      ),
    );
  }

  final active = rows
      .where((r) => !usedKeys.contains(keyOf(r)) && r['top_class'] != artifactClass)
      .toList()
    ..sort((a, b) {
      final na = (a['ndet'] as num?)?.toInt() ?? 0;
      final nb = (b['ndet'] as num?)?.toInt() ?? 0;
      if (nb != na) return nb.compareTo(na);
      final la = (a['lastmjd'] as num?)?.toDouble() ?? 0.0;
      final lb = (b['lastmjd'] as num?)?.toDouble() ?? 0.0;
      return lb.compareTo(la);
    });

  if (active.isNotEmpty) {
    final top = active.first;
    usedKeys.add(keyOf(top));
    final ndet = (top['ndet'] as num?)?.toInt() ?? 0;
    final info = classInfo(top['top_class'] as String?);
    out.add(
      HighlightCardModel(
        kind: 'active',
        eyebrow: 'Most-observed object',
        survey: '${top['survey']}',
        oid: '${top['oid']}',
        headline: '${top['oid']} · ${formatCount(ndet)} detections',
        subtitle: '${info.label} tracked across repeated survey passes.',
      ),
    );
  }

  final solar = rows
      .where(
        (r) =>
            !usedKeys.contains(keyOf(r)) &&
            (r['top_class'] == asteroidClass || r['top_class'] == 'SSO'),
      )
      .toList()
    ..sort((a, b) {
      final sa = (a['sso'] is Map && (a['sso'] as Map)['status'] == 'matched') ? 1 : 0;
      final sb = (b['sso'] is Map && (b['sso'] as Map)['status'] == 'matched') ? 1 : 0;
      if (sb != sa) return sb.compareTo(sa);
      final pa = (a['top_probability'] as num?)?.toDouble() ?? 0.0;
      final pb = (b['top_probability'] as num?)?.toDouble() ?? 0.0;
      return pb.compareTo(pa);
    });

  if (solar.isNotEmpty) {
    final top = solar.first;
    final sso = top['sso'] is Map ? Map<String, dynamic>.from(top['sso'] as Map) : null;
    final matchedName = sso != null && sso['status'] == 'matched'
        ? (sso['sso_name'] as String?)
        : null;
    final ssoNum = sso != null ? (sso['sso_number'] as num?)?.toInt() : null;
    final label = matchedName != null
        ? formatSsoLabel(ssoNum, matchedName)
        : '${top['oid']}';
    out.add(
      HighlightCardModel(
        kind: 'solar',
        eyebrow: 'Solar System catch',
        survey: '${top['survey']}',
        oid: '${top['oid']}',
        headline: matchedName != null ? 'Asteroid $label' : 'Moving object ${top['oid']}',
        subtitle: matchedName != null
            ? 'Cross-matched with IMCCE SkyBoT ephemeris ($label).'
            : 'Fast-moving Solar System candidate spotted in survey frames.',
      ),
    );
  }

  return out;
}
