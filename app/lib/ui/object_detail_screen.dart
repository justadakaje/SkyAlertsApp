import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';

import '../data/firestore_repository.dart';
import '../domain/astro.dart';
import '../domain/classes.dart';
import '../domain/format.dart';
import '../domain/lightcurve.dart';
import '../domain/solar.dart';
import 'theme.dart';

class ObjectDetailScreen extends StatefulWidget {
  const ObjectDetailScreen({
    super.key,
    required this.repository,
    required this.survey,
    required this.oid,
  });

  final SkyAlertsRepository repository;
  final String survey;
  final String oid;

  @override
  State<ObjectDetailScreen> createState() => _ObjectDetailScreenState();
}

class _ObjectDetailScreenState extends State<ObjectDetailScreen> {
  ObjectDetailBundle? _bundle;
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() => _loading = true);
    final bundle = await widget.repository.fetchObjectDetail(widget.survey, widget.oid);
    if (!mounted) return;
    setState(() {
      _bundle = bundle;
      _loading = false;
    });
  }

  @override
  Widget build(BuildContext context) {
    if (_loading) {
      return Scaffold(
        appBar: AppBar(title: Text(widget.oid)),
        body: const Center(child: CircularProgressIndicator()),
      );
    }
    final bundle = _bundle;
    if (bundle == null) {
      return Scaffold(
        appBar: AppBar(title: Text(widget.oid)),
        body: const Center(child: Text('Object not found in catalog.')),
      );
    }

    final obj = bundle.object;
    final info = classInfo(obj.topClass);
    final curve = buildCurve(bundle.detections);
    final stamps = buildZtfStamps(obj.survey, obj.oid, bundle.detections);
    final brightnessNote = humanBrightness(obj.peakMag, band: obj.peakBand);
    final regionNote = skyRegion(obj.meanRa, obj.meanDec);
    final sso = obj.sso;
    final sbdbUrl = (sso != null && sso.isMatched)
        ? jplSbdbUrl(sso.ssoNumber, sso.ssoName)
        : null;

    return Scaffold(
      appBar: AppBar(
        title: Text('${obj.oid} (${obj.survey.toUpperCase()})'),
        actions: [
          IconButton(
            onPressed: () async {
              await widget.repository.toggleBookmark(obj);
              if (context.mounted) {
                ScaffoldMessenger.of(context).showSnackBar(
                  const SnackBar(content: Text('Updated saved object bookmarks.')),
                );
              }
            },
            icon: const Icon(Icons.bookmark_add_outlined),
            tooltip: 'Bookmark object for push alerts',
          ),
        ],
      ),
      body: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 1040),
          child: ListView(
            padding: const EdgeInsets.all(16),
            children: [
              Card(
                child: Padding(
                  padding: const EdgeInsets.all(16),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        info.label,
                        style: TextStyle(
                          fontSize: 20,
                          fontWeight: FontWeight.bold,
                          color: SkyColors.forGroup(info.group),
                        ),
                      ),
                      const SizedBox(height: 6),
                      Text(info.blurb),
                      if (sso != null && sso.isMatched) ...[
                        const SizedBox(height: 10),
                        Wrap(
                          spacing: 12,
                          crossAxisAlignment: WrapCrossAlignment.center,
                          children: [
                            Chip(
                              avatar: const Icon(Icons.public, size: 16),
                              label: Text(
                                'IMCCE SkyBoT Match: ${formatSsoLabel(sso.ssoNumber, sso.ssoName!)} '
                                '(${sso.sepArcsec?.toStringAsFixed(2) ?? "—"}″)',
                              ),
                            ),
                            if (sbdbUrl != null)
                              TextButton.icon(
                                onPressed: () => launchUrl(Uri.parse(sbdbUrl)),
                                icon: const Icon(Icons.open_in_new, size: 16),
                                label: const Text('JPL Small-Body Database'),
                              ),
                          ],
                        ),
                      ],
                      const Divider(height: 24),
                      Wrap(
                        spacing: 24,
                        runSpacing: 8,
                        children: [
                          Text('RA: ${formatRa(obj.meanRa)}'),
                          Text('Dec: ${formatDec(obj.meanDec)}'),
                          Text('First seen: ${formatUtc(obj.firstMjd)}'),
                          Text('Last seen: ${formatUtc(obj.lastMjd)}'),
                          Text('Detections: ${formatCount(obj.nDetections)}'),
                          Text('Confidence: ${formatProbability(obj.topProbability)}'),
                        ],
                      ),
                      if (brightnessNote != null) ...[
                        const SizedBox(height: 8),
                        Text(
                          'Peak brightness: $brightnessNote',
                          style: const TextStyle(color: SkyColors.accentAmber),
                        ),
                      ],
                      if (regionNote != null) ...[
                        const SizedBox(height: 4),
                        Text(
                          'Where in the sky: $regionNote',
                          style: const TextStyle(color: SkyColors.textSecondary),
                        ),
                      ],
                    ],
                  ),
                ),
              ),
              const SizedBox(height: 16),
              if (curve != null)
                Card(
                  child: Padding(
                    padding: const EdgeInsets.all(16),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          curve.mode == CurveMode.magnitude
                              ? 'Light Curve (Magnitude — brighter at top)'
                              : 'Light Curve (Difference Flux nJy)',
                          style: const TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
                        ),
                        const SizedBox(height: 12),
                        SizedBox(
                          height: 240,
                          width: double.infinity,
                          child: CustomPaint(painter: LightCurvePainter(curve: curve)),
                        ),
                      ],
                    ),
                  ),
                ),
              if (stamps != null) ...[
                const SizedBox(height: 16),
                Card(
                  child: Padding(
                    padding: const EdgeInsets.all(16),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          'ZTF Cutout Stamps (${stamps.band}-band · ${formatUtc(stamps.mjd)})',
                          style: const TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
                        ),
                        const SizedBox(height: 12),
                        Wrap(
                          spacing: 16,
                          runSpacing: 16,
                          children: [
                            _StampTile(label: 'Science ( tonight )', url: stamps.scienceUrl),
                            _StampTile(label: 'Reference ( template )', url: stamps.templateUrl),
                            _StampTile(
                              label: 'Difference ( subtraction )',
                              url: stamps.differenceUrl,
                            ),
                          ],
                        ),
                      ],
                    ),
                  ),
                ),
              ],
              if (obj.meanRa != null && obj.meanDec != null) ...[
                const SizedBox(height: 16),
                Card(
                  child: Padding(
                    padding: const EdgeInsets.all(16),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Text(
                          'All-Sky Aitoff Projection & Milky Way Plane',
                          style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
                        ),
                        const SizedBox(height: 12),
                        SizedBox(
                          height: 200,
                          width: double.infinity,
                          child: CustomPaint(
                            painter: SkyMapPainter(raDeg: obj.meanRa!, decDeg: obj.meanDec!),
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }
}

class _StampTile extends StatelessWidget {
  const _StampTile({required this.label, required this.url});

  final String label;
  final String url;

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        ClipRRect(
          borderRadius: BorderRadius.circular(8),
          child: Image.network(
            url,
            width: 140,
            height: 140,
            fit: BoxFit.cover,
            errorBuilder: (_, __, ___) => Container(
              width: 140,
              height: 140,
              color: SkyColors.bgElevated,
              alignment: Alignment.center,
              child: const Text('Cutout unavailable', style: TextStyle(fontSize: 11)),
            ),
          ),
        ),
        const SizedBox(height: 6),
        Text(label, style: const TextStyle(fontSize: 12, color: SkyColors.textSecondary)),
      ],
    );
  }
}

class LightCurvePainter extends CustomPainter {
  const LightCurvePainter({required this.curve});

  final CurveModel curve;

  @override
  void paint(Canvas canvas, Size size) {
    const padLeft = 44.0;
    const padRight = 16.0;
    const padTop = 12.0;
    const padBottom = 24.0;
    final plotW = math.max(1.0, size.width - padLeft - padRight);
    final plotH = math.max(1.0, size.height - padTop - padBottom);

    final gridPaint = Paint()
      ..color = SkyColors.borderSubtle
      ..strokeWidth = 1.0;
    canvas.drawRect(Rect.fromLTWH(padLeft, padTop, plotW, plotH), gridPaint..style = PaintingStyle.stroke);

    double mapX(double mjd) =>
        padLeft + ((mjd - curve.minMjd) / (curve.maxMjd - curve.minMjd)) * plotW;

    double mapY(double val) {
      final norm = (val - curve.minY) / (curve.maxY - curve.minY);
      // Invert Y axis for astronomical magnitude (smaller number = brighter = higher up)
      return curve.mode == CurveMode.magnitude
          ? padTop + norm * plotH
          : padTop + (1.0 - norm) * plotH;
    }

    for (final pt in curve.points) {
      final val = curve.mode == CurveMode.magnitude ? pt.mag : pt.fluxNjy;
      if (val == null) continue;
      final x = mapX(pt.mjd);
      final y = mapY(val);
      final color = SkyColors.forBand(pt.band);
      final dotPaint = Paint()..color = color;
      canvas.drawCircle(Offset(x, y), 4.0, dotPaint);
    }
  }

  @override
  bool shouldRepaint(covariant LightCurvePainter oldDelegate) => oldDelegate.curve != curve;
}

class SkyMapPainter extends CustomPainter {
  const SkyMapPainter({required this.raDeg, required this.decDeg});

  final double raDeg;
  final double decDeg;

  Offset _project(double ra, double dec, Size size) {
    final l = ((180.0 - ra) * math.pi) / 180.0;
    final phi = (dec * math.pi) / 180.0;
    final alpha = math.acos((math.cos(phi) * math.cos(l / 2.0)).clamp(-1.0, 1.0));
    final sinc = alpha == 0.0 ? 1.0 : math.sin(alpha) / alpha;
    final x = (2.0 * math.cos(phi) * math.sin(l / 2.0)) / sinc;
    final y = math.sin(phi) / sinc;
    final cx = size.width / 2.0 + (x / math.pi) * (size.width * 0.45);
    final cy = size.height / 2.0 - (y / (math.pi / 2.0)) * (size.height * 0.45);
    return Offset(cx, cy);
  }

  @override
  void paint(Canvas canvas, Size size) {
    final borderPaint = Paint()
      ..color = SkyColors.borderSubtle
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1.2;
    canvas.drawOval(
      Rect.fromCenter(
        center: Offset(size.width / 2, size.height / 2),
        width: size.width * 0.9,
        height: size.height * 0.9,
      ),
      borderPaint,
    );

    final mwPaint = Paint()
      ..color = SkyColors.textSecondary.withValues(alpha: 0.35)
      ..strokeWidth = 1.5;
    for (var l = 0; l < 360; l += 6) {
      final eq = galacticToEquatorial(l.toDouble(), 0.0);
      final p = _project(eq.ra, eq.dec, size);
      canvas.drawCircle(p, 1.2, mwPaint);
    }

    final target = _project(raDeg, decDeg, size);
    canvas.drawCircle(
      target,
      6.0,
      Paint()..color = SkyColors.accentAmber,
    );
  }

  @override
  bool shouldRepaint(covariant SkyMapPainter oldDelegate) =>
      oldDelegate.raDeg != raDeg || oldDelegate.decDeg != decDeg;
}
