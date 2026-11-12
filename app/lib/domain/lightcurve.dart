import 'dart:math' as math;

class DetectionPoint {
  const DetectionPoint({
    required this.measurementId,
    required this.mjd,
    required this.band,
    this.mag,
    this.magErr,
    this.fluxNjy,
    this.fluxErrNjy,
    this.negative = false,
    this.candid,
    this.hasStamp,
  });

  factory DetectionPoint.fromMap(Map<String, dynamic> map) {
    return DetectionPoint(
      measurementId: '${map['measurement_id'] ?? ''}',
      mjd: (map['mjd'] as num?)?.toDouble() ?? 0.0,
      band: (map['band'] as String?) ?? 'r',
      mag: (map['mag'] as num?)?.toDouble(),
      magErr: (map['mag_err'] as num?)?.toDouble(),
      fluxNjy: (map['flux_njy'] as num?)?.toDouble(),
      fluxErrNjy: (map['flux_err_njy'] as num?)?.toDouble(),
      negative: map['negative'] == true,
      candid: map['candid']?.toString(),
      hasStamp: map['has_stamp'] is bool ? map['has_stamp'] as bool : null,
    );
  }

  final String measurementId;
  final double mjd;
  final String band;
  final double? mag;
  final double? magErr;
  final double? fluxNjy;
  final double? fluxErrNjy;
  final bool negative;
  final String? candid;
  final bool? hasStamp;

  /// Effective AB magnitude (`mag` for ZTF, `-2.5 * log10(flux_njy) + 31.4` for positive Rubin flux).
  double? get effectiveAbMag {
    if (mag != null && mag!.isFinite && !negative) return mag;
    if (fluxNjy != null && fluxNjy!.isFinite && fluxNjy! > 0) {
      return -2.5 * (math.log(fluxNjy!) / math.ln10) + 31.4;
    }
    return null;
  }
}

enum CurveMode { magnitude, flux }

class CurveModel {
  const CurveModel({
    required this.mode,
    required this.points,
    required this.minMjd,
    required this.maxMjd,
    required this.minY,
    required this.maxY,
    required this.bands,
  });

  final CurveMode mode;
  final List<DetectionPoint> points;
  final double minMjd;
  final double maxMjd;
  final double minY;
  final double maxY;
  final List<String> bands;
}

CurveModel? buildCurve(List<DetectionPoint> detections) {
  final magPoints = detections
      .where((d) => d.mjd.isFinite && d.mag != null && d.mag!.isFinite)
      .toList()
    ..sort((a, b) => a.mjd.compareTo(b.mjd));

  if (magPoints.isNotEmpty) {
    var minMjd = magPoints.first.mjd;
    var maxMjd = magPoints.last.mjd;
    if (maxMjd <= minMjd) {
      minMjd -= 0.5;
      maxMjd += 0.5;
    }
    var minY = double.infinity;
    var maxY = double.negativeInfinity;
    final bandSet = <String>{};
    for (final p in magPoints) {
      bandSet.add(p.band);
      final err = (p.magErr != null && p.magErr!.isFinite) ? p.magErr! : 0.0;
      minY = math.min(minY, p.mag! - err);
      maxY = math.max(maxY, p.mag! + err);
    }
    if ((maxY - minY).abs() < 0.2) {
      minY -= 0.25;
      maxY += 0.25;
    }
    return CurveModel(
      mode: CurveMode.magnitude,
      points: magPoints,
      minMjd: minMjd,
      maxMjd: maxMjd,
      minY: minY,
      maxY: maxY,
      bands: bandSet.toList(),
    );
  }

  final fluxPoints = detections
      .where((d) => d.mjd.isFinite && d.fluxNjy != null && d.fluxNjy!.isFinite)
      .toList()
    ..sort((a, b) => a.mjd.compareTo(b.mjd));

  if (fluxPoints.isEmpty) return null;

  var minMjd = fluxPoints.first.mjd;
  var maxMjd = fluxPoints.last.mjd;
  if (maxMjd <= minMjd) {
    minMjd -= 0.5;
    maxMjd += 0.5;
  }
  var minY = double.infinity;
  var maxY = double.negativeInfinity;
  final bandSet = <String>{};
  for (final p in fluxPoints) {
    bandSet.add(p.band);
    final err = (p.fluxErrNjy != null && p.fluxErrNjy!.isFinite) ? p.fluxErrNjy! : 0.0;
    minY = math.min(minY, p.fluxNjy! - err);
    maxY = math.max(maxY, p.fluxNjy! + err);
  }
  if ((maxY - minY).abs() < 1.0) {
    minY -= 10.0;
    maxY += 10.0;
  }
  return CurveModel(
    mode: CurveMode.flux,
    points: fluxPoints,
    minMjd: minMjd,
    maxMjd: maxMjd,
    minY: minY,
    maxY: maxY,
    bands: bandSet.toList(),
  );
}

final RegExp _ztfOidRe = RegExp(r'^ZTF\d{2}[a-z]{7}$');
final RegExp _candidRe = RegExp(r'^\d{10,22}$');

enum ZtfStampKind { science, template, difference }

String? ztfStampUrl({
  required String oid,
  required String candid,
  required ZtfStampKind kind,
}) {
  if (!_ztfOidRe.hasMatch(oid) || !_candidRe.hasMatch(candid)) return null;
  final p = Uri.encodeQueryComponent;
  return 'https://avro.alerce.online/get_stamp?oid=${p(oid)}&candid=${p(candid)}&type=${kind.name}&format=png';
}

class ZtfStampSet {
  const ZtfStampSet({
    required this.oid,
    required this.candid,
    required this.mjd,
    required this.band,
    required this.scienceUrl,
    required this.templateUrl,
    required this.differenceUrl,
  });

  final String oid;
  final String candid;
  final double mjd;
  final String band;
  final String scienceUrl;
  final String templateUrl;
  final String differenceUrl;
}

ZtfStampSet? buildZtfStamps(String survey, String oid, List<DetectionPoint> detections) {
  if (survey != 'ztf' || !_ztfOidRe.hasMatch(oid)) return null;
  final withStamps = detections.where((d) {
    final c = d.candid ?? d.measurementId;
    return d.hasStamp != false && _candidRe.hasMatch(c);
  }).toList()
    ..sort((a, b) => b.mjd.compareTo(a.mjd));

  if (withStamps.isEmpty) return null;
  final chosen = withStamps.first;
  final candid = chosen.candid ?? chosen.measurementId;
  final sci = ztfStampUrl(oid: oid, candid: candid, kind: ZtfStampKind.science);
  final tpl = ztfStampUrl(oid: oid, candid: candid, kind: ZtfStampKind.template);
  final dif = ztfStampUrl(oid: oid, candid: candid, kind: ZtfStampKind.difference);
  if (sci == null || tpl == null || dif == null) return null;
  return ZtfStampSet(
    oid: oid,
    candid: candid,
    mjd: chosen.mjd,
    band: chosen.band,
    scienceUrl: sci,
    templateUrl: tpl,
    differenceUrl: dif,
  );
}
