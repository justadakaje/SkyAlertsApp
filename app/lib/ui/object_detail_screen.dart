import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:url_launcher/url_launcher.dart';

import '../data/firestore_repository.dart';
import '../domain/astro.dart';
import '../domain/backyard_planner.dart';
import '../domain/classes.dart';
import '../domain/format.dart';
import '../domain/lightcurve.dart';
import '../domain/solar.dart';
import 'sky_media_widgets.dart';
import 'gear_card_widget.dart';
import 'theme.dart';
import 'tonight_arc_chart.dart';
import 'tonight_screen.dart';

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
    final simbadUrl = simbadConeUrl(obj.meanRa, obj.meanDec);
    final legacyUrl = legacyViewerUrl(obj.meanRa, obj.meanDec);

    // Count detections by filter band for legend
    final bandCounts = <String, int>{};
    for (final d in bundle.detections) {
      bandCounts[d.band] = (bandCounts[d.band] ?? 0) + 1;
    }

    return Scaffold(
      appBar: AppBar(
        title: Text('${obj.oid} (${obj.survey.toUpperCase()})'),
        actions: [
          IconButton(
            tooltip: 'Copy coordinates & ID',
            onPressed: () {
              Clipboard.setData(
                ClipboardData(
                  text: '${obj.oid} (${obj.survey.toUpperCase()}) · '
                      'RA ${formatRa(obj.meanRa)} Dec ${formatDec(obj.meanDec)}',
                ),
              );
              ScaffoldMessenger.of(context).showSnackBar(
                const SnackBar(content: Text('Copied object coordinates to clipboard.')),
              );
            },
            icon: const Icon(Icons.copy_outlined),
          ),
          IconButton(
            onPressed: () async {
              if (widget.repository.currentUser == null) {
                ScaffoldMessenger.of(context).showSnackBar(
                  const SnackBar(
                    content: Text('Sign in on the Alerts or Admin tab to save bookmarks.'),
                  ),
                );
                return;
              }
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
                      Row(
                        children: [
                          Expanded(
                            child: Text(
                              info.label,
                              style: TextStyle(
                                fontSize: 20,
                                fontWeight: FontWeight.bold,
                                color: SkyColors.forGroup(info.group),
                              ),
                            ),
                          ),
                          Container(
                            padding: const EdgeInsets.symmetric(
                              horizontal: 8,
                              vertical: 4,
                            ),
                            decoration: BoxDecoration(
                              color: SkyColors.bgElevated,
                              borderRadius: BorderRadius.circular(6),
                            ),
                            child: Text(
                              obj.survey == 'lsst'
                                  ? 'Vera C. Rubin Observatory (LSST)'
                                  : 'Zwicky Transient Facility (ZTF)',
                              style: const TextStyle(
                                fontSize: 11,
                                fontWeight: FontWeight.w600,
                                color: SkyColors.textSecondary,
                              ),
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 6),
                      Text(info.blurb),
                      if (sso != null && sso.isMatched) ...[
                        const SizedBox(height: 10),
                        Wrap(
                          spacing: 12,
                          runSpacing: 8,
                          crossAxisAlignment: WrapCrossAlignment.center,
                          children: [
                            Chip(
                              avatar: const Icon(Icons.public, size: 16),
                              label: Text(
                                'IMCCE SkyBoT Match: ${formatSsoLabel(sso.ssoNumber, sso.ssoName!)} '
                                '(${sso.sepArcsec?.toStringAsFixed(2) ?? "—"}″)',
                              ),
                            ),
                            if (sso.ssoClass != null)
                              Chip(label: Text('Orbit class: ${sso.ssoClass}')),
                            if (sso.helioDistAu != null)
                              Chip(
                                label: Text(
                                  'Heliocentric: ${sso.helioDistAu!.toStringAsFixed(2)} AU',
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
                          Text('RA (J2000): ${formatRa(obj.meanRa)}'),
                          Text('Dec (J2000): ${formatDec(obj.meanDec)}'),
                          Text('First seen: ${formatUtc(obj.firstMjd)}'),
                          Text('Last seen: ${formatUtc(obj.lastMjd)}'),
                          Text('Detections: ${formatCount(obj.nDetections)}'),
                          Text(
                            'Classifier: ${obj.topClassifier ?? "—"} '
                            '(${formatProbability(obj.topProbability)})',
                          ),
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
                      const SizedBox(height: 14),
                      Wrap(
                        spacing: 10,
                        runSpacing: 8,
                        children: [
                          if (obj.meanRa != null && obj.meanDec != null)
                            FilledButton.tonalIcon(
                              onPressed: () {
                                final text = formatCoordinatesForRig(obj);
                                Clipboard.setData(ClipboardData(text: text));
                                ScaffoldMessenger.of(context).showSnackBar(
                                  SnackBar(content: Text('Copied J2000 coordinates: $text')),
                                );
                              },
                              icon: const Icon(Icons.copy, size: 16),
                              label: const Text('Copy J2000 RA/Dec'),
                            ),
                          OutlinedButton.icon(
                            onPressed: () =>
                                launchUrl(Uri.parse(alerceExplorerUrl(obj.oid))),
                            icon: const Icon(Icons.travel_explore, size: 16),
                            label: const Text('ALeRCE Broker'),
                          ),
                          if (legacyUrl != null)
                            OutlinedButton.icon(
                              onPressed: () => launchUrl(Uri.parse(legacyUrl)),
                              icon: const Icon(Icons.layers_outlined, size: 16),
                              label: const Text('Legacy Survey DR10 Viewer'),
                            ),
                          if (simbadUrl != null)
                            OutlinedButton.icon(
                              onPressed: () => launchUrl(Uri.parse(simbadUrl)),
                              icon: const Icon(Icons.science_outlined, size: 16),
                              label: const Text('CDS SIMBAD Cone Search'),
                            ),
                        ],
                      ),
                    ],
                  ),
                ),
              ),
              const SizedBox(height: 16),
              if (obj.meanRa != null && obj.meanDec != null)
                Builder(
                  builder: (context) {
                    final loc = backyardLocationNotifier.value;
                    final scope = backyardScopeNotifier.value;
                    final minAlt = backyardMinAltNotifier.value;
                    final plan = planTarget(obj, loc, scope, minAltDeg: minAlt);
                    if (plan == null) return const SizedBox.shrink();
                    return Padding(
                      padding: const EdgeInsets.only(bottom: 16),
                      child: Card(
                        child: Padding(
                          padding: const EdgeInsets.all(16),
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Row(
                                children: [
                                  const Expanded(
                                    child: Text(
                                      "Tonight's Backyard Arc",
                                      style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
                                    ),
                                  ),
                                  Text(
                                    '${scope.shortLabel} · ${loc.label}',
                                    style: const TextStyle(
                                      fontSize: 12,
                                      color: SkyColors.textSecondary,
                                    ),
                                  ),
                                ],
                              ),
                              const SizedBox(height: 4),
                              Text(
                                plan.statusLine,
                                style: const TextStyle(fontSize: 13),
                              ),
                              const SizedBox(height: 12),
                              TonightArcChart(plan: plan, minAltDeg: minAlt),
                            ],
                          ),
                        ),
                      ),
                    );
                  },
                ),
              // Deep-Sky & Survey Cutout Imagery Card (always shown when RA/Dec are available)
              if (obj.meanRa != null && obj.meanDec != null)
                Card(
                  child: Padding(
                    padding: const EdgeInsets.all(16),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Text(
                          'Telescope Cutout Imagery (Tap any frame to zoom)',
                          style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
                        ),
                        const SizedBox(height: 4),
                        const Text(
                          'Archival deep-sky color CCD imaging (DESI Legacy Survey DR10 & SDSS DR18) at target J2000 coordinates, plus live ZTF alert stamps when available.',
                          style: TextStyle(fontSize: 12, color: SkyColors.textSecondary),
                        ),
                        const SizedBox(height: 14),
                        Wrap(
                          spacing: 16,
                          runSpacing: 16,
                          children: [
                            _CutoutFrame(
                              label: 'Archival Host View (Target at Crosshair) · Wide 84″',
                              child: SkyCutoutThumbnail(
                                ra: obj.meanRa,
                                dec: obj.meanDec,
                                width: 150,
                                height: 150,
                                pixscale: 0.35,
                                title: '${obj.oid} · Legacy DR10 Archival Wide Field (84″)',
                              ),
                            ),
                            _CutoutFrame(
                              label: 'Archival Host View (Target at Crosshair) · Zoom 34″',
                              child: SkyCutoutThumbnail(
                                ra: obj.meanRa,
                                dec: obj.meanDec,
                                width: 150,
                                height: 150,
                                pixscale: 0.14,
                                title: '${obj.oid} · Legacy DR10 Archival Host Zoom (34″)',
                              ),
                            ),
                            if (stamps != null) ...[
                              _StampTile(
                                label: 'Live Survey Detection Stamp (${stamps.band}-band)',
                                url: stamps.scienceUrl,
                              ),
                              _StampTile(
                                label: 'Live Survey Reference (Template)',
                                url: stamps.templateUrl,
                              ),
                              _StampTile(
                                label: 'Live Survey Difference (Subtraction)',
                                url: stamps.differenceUrl,
                              ),
                            ],
                          ],
                        ),
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
                        Row(
                          children: [
                            Expanded(
                              child: Text(
                                curve.mode == CurveMode.magnitude
                                    ? 'Photometric Light Curve (AB Magnitude — brighter at top)'
                                    : 'Photometric Light Curve (Difference Flux nJy)',
                                style: const TextStyle(
                                  fontSize: 16,
                                  fontWeight: FontWeight.bold,
                                ),
                              ),
                            ),
                            Text(
                              '${curve.points.length} epochs',
                              style: const TextStyle(
                                fontSize: 12,
                                color: SkyColors.textSecondary,
                              ),
                            ),
                          ],
                        ),
                        const SizedBox(height: 10),
                        Wrap(
                          spacing: 12,
                          runSpacing: 6,
                          children: bandCounts.entries.map((e) {
                            final c = SkyColors.forBand(e.key);
                            return Row(
                              mainAxisSize: MainAxisSize.min,
                              children: [
                                Container(
                                  width: 10,
                                  height: 10,
                                  decoration: BoxDecoration(
                                    color: c,
                                    shape: BoxShape.circle,
                                  ),
                                ),
                                const SizedBox(width: 5),
                                Text(
                                  '${e.key}-band (${e.value})',
                                  style: const TextStyle(
                                    fontSize: 12,
                                    color: SkyColors.textSecondary,
                                  ),
                                ),
                              ],
                            );
                          }).toList(),
                        ),
                        const SizedBox(height: 12),
                        SizedBox(
                          height: 250,
                          width: double.infinity,
                          child: CustomPaint(painter: LightCurvePainter(curve: curve)),
                        ),
                      ],
                    ),
                  ),
                )
              else
                Card(
                  child: Padding(
                    padding: const EdgeInsets.all(16),
                    child: Row(
                      children: [
                        const Icon(Icons.show_chart, color: SkyColors.textSecondary),
                        const SizedBox(width: 12),
                        Expanded(
                          child: Text(
                            'Catalog summary ingested (${formatCount(obj.nDetections)} survey detections between '
                            '${formatShortDate(obj.firstMjd)} and ${formatShortDate(obj.lastMjd)}). '
                            'Open ALeRCE Broker above for the full raw photometry table.',
                            style: const TextStyle(
                              fontSize: 13,
                              color: SkyColors.textSecondary,
                            ),
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
              if (bundle.classifications.isNotEmpty) ...[
                const SizedBox(height: 16),
                Card(
                  child: Padding(
                    padding: const EdgeInsets.all(16),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Text(
                          'ML Broker Classification Probabilities',
                          style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
                        ),
                        const SizedBox(height: 12),
                        ...bundle.classifications.take(8).map((c) {
                          final clsInfo = classInfo(c.className);
                          final barColor = SkyColors.forGroup(clsInfo.group);
                          return Padding(
                            padding: const EdgeInsets.only(bottom: 10),
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Row(
                                  children: [
                                    Text(
                                      '${clsInfo.label} (${c.className})',
                                      style: const TextStyle(
                                        fontSize: 13,
                                        fontWeight: FontWeight.w600,
                                      ),
                                    ),
                                    const SizedBox(width: 8),
                                    Text(
                                      c.classifier,
                                      style: const TextStyle(
                                        fontSize: 11,
                                        color: SkyColors.textSecondary,
                                      ),
                                    ),
                                    const Spacer(),
                                    Text(
                                      formatProbability(c.probability),
                                      style: const TextStyle(
                                        fontSize: 12,
                                        fontWeight: FontWeight.bold,
                                      ),
                                    ),
                                  ],
                                ),
                                const SizedBox(height: 4),
                                ClipRRect(
                                  borderRadius: BorderRadius.circular(4),
                                  child: LinearProgressIndicator(
                                    value: c.probability.clamp(0.0, 1.0),
                                    minHeight: 7,
                                    backgroundColor: SkyColors.bgElevated,
                                    color: barColor,
                                  ),
                                ),
                              ],
                            ),
                          );
                        }),
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
                          'All-Sky Aitoff Projection & Galactic Plane',
                          style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
                        ),
                        const SizedBox(height: 4),
                        Text(
                          'Target marked in amber at RA ${formatRa(obj.meanRa)}, Dec ${formatDec(obj.meanDec)} · Dotted curve traces the Milky Way plane.',
                          style: const TextStyle(
                            fontSize: 12,
                            color: SkyColors.textSecondary,
                          ),
                        ),
                        const SizedBox(height: 12),
                        SizedBox(
                          height: 210,
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
              const SizedBox(height: 16),
              GearRecommendationCard(magnitude: obj.effectiveMag),
            ],
          ),
        ),
      ),
    );
  }
}

class _CutoutFrame extends StatelessWidget {
  const _CutoutFrame({required this.label, required this.child});

  final String label;
  final Widget child;

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        child,
        const SizedBox(height: 6),
        Text(
          label,
          style: const TextStyle(fontSize: 12, color: SkyColors.textSecondary),
        ),
      ],
    );
  }
}

class _StampTile extends StatelessWidget {
  const _StampTile({required this.label, required this.url});

  final String label;
  final String url;

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: () => showCutoutLightbox(
        context,
        title: label,
        imageUrl: url,
        subtitle: 'ALeRCE ZTF Alert Cutout Stamp',
      ),
      child: Column(
        children: [
          ClipRRect(
            borderRadius: BorderRadius.circular(10),
            child: Image.network(
              url,
              width: 150,
              height: 150,
              fit: BoxFit.cover,
              errorBuilder: (_, __, ___) => Container(
                width: 150,
                height: 150,
                color: SkyColors.bgElevated,
                alignment: Alignment.center,
                child: const Text('Cutout unavailable', style: TextStyle(fontSize: 11)),
              ),
            ),
          ),
          const SizedBox(height: 6),
          Text(label, style: const TextStyle(fontSize: 12, color: SkyColors.textSecondary)),
        ],
      ),
    );
  }
}

class LightCurvePainter extends CustomPainter {
  const LightCurvePainter({required this.curve});

  final CurveModel curve;

  void _drawText(Canvas canvas, String text, Offset pos, {TextAlign align = TextAlign.left}) {
    final tp = TextPainter(
      text: TextSpan(
        text: text,
        style: const TextStyle(fontSize: 10, color: SkyColors.textSecondary),
      ),
      textAlign: align,
      textDirection: TextDirection.ltr,
    )..layout();
    tp.paint(canvas, pos);
  }

  @override
  void paint(Canvas canvas, Size size) {
    const padLeft = 52.0;
    const padRight = 18.0;
    const padTop = 14.0;
    const padBottom = 28.0;
    final plotW = math.max(1.0, size.width - padLeft - padRight);
    final plotH = math.max(1.0, size.height - padTop - padBottom);

    final gridPaint = Paint()
      ..color = SkyColors.borderSubtle.withValues(alpha: 0.65)
      ..strokeWidth = 1.0;

    // Horizontal grid lines & Y-axis labels
    const yTicks = 4;
    for (var i = 0; i <= yTicks; i++) {
      final frac = i / yTicks;
      final y = padTop + frac * plotH;
      canvas.drawLine(Offset(padLeft, y), Offset(padLeft + plotW, y), gridPaint);
      final val = curve.mode == CurveMode.magnitude
          ? curve.minY + frac * (curve.maxY - curve.minY)
          : curve.maxY - frac * (curve.maxY - curve.minY);
      final label = curve.mode == CurveMode.magnitude
          ? val.toStringAsFixed(2)
          : val.round().toString();
      _drawText(canvas, label, Offset(4, y - 6));
    }

    // X-axis date labels (start, mid, end)
    for (final frac in const [0.0, 0.5, 1.0]) {
      final mjd = curve.minMjd + frac * (curve.maxMjd - curve.minMjd);
      final x = padLeft + frac * plotW;
      _drawText(canvas, formatShortDate(mjd), Offset(x - 18, padTop + plotH + 8));
    }

    canvas.drawRect(
      Rect.fromLTWH(padLeft, padTop, plotW, plotH),
      Paint()
        ..color = SkyColors.borderSubtle
        ..style = PaintingStyle.stroke
        ..strokeWidth = 1.1,
    );

    double mapX(double mjd) =>
        padLeft + ((mjd - curve.minMjd) / (curve.maxMjd - curve.minMjd)) * plotW;

    double mapY(double val) {
      final norm = (val - curve.minY) / (curve.maxY - curve.minY);
      return curve.mode == CurveMode.magnitude
          ? padTop + norm * plotH
          : padTop + (1.0 - norm) * plotH;
    }

    // Connect points within each filter band with a subtle path
    final byBand = <String, List<Offset>>{};
    for (final pt in curve.points) {
      final val = curve.mode == CurveMode.magnitude ? pt.mag : pt.fluxNjy;
      final err = curve.mode == CurveMode.magnitude ? pt.magErr : pt.fluxErrNjy;
      if (val == null) continue;
      final x = mapX(pt.mjd);
      final y = mapY(val);
      final color = SkyColors.forBand(pt.band);
      byBand.putIfAbsent(pt.band, () => []).add(Offset(x, y));

      if (err != null && err > 0 && err.isFinite) {
        final y1 = mapY(val - err).clamp(padTop, padTop + plotH);
        final y2 = mapY(val + err).clamp(padTop, padTop + plotH);
        canvas.drawLine(
          Offset(x, y1),
          Offset(x, y2),
          Paint()
            ..color = color.withValues(alpha: 0.55)
            ..strokeWidth = 1.2,
        );
      }
      canvas.drawCircle(Offset(x, y), 4.2, Paint()..color = color);
    }

    for (final entry in byBand.entries) {
      final pts = entry.value;
      if (pts.length < 2) continue;
      final path = Path()..moveTo(pts.first.dx, pts.first.dy);
      for (var i = 1; i < pts.length; i++) {
        path.lineTo(pts[i].dx, pts[i].dy);
      }
      canvas.drawPath(
        path,
        Paint()
          ..color = SkyColors.forBand(entry.key).withValues(alpha: 0.32)
          ..style = PaintingStyle.stroke
          ..strokeWidth = 1.4,
      );
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

    // Equator & meridian guides
    canvas.drawLine(
      Offset(size.width * 0.05, size.height / 2),
      Offset(size.width * 0.95, size.height / 2),
      Paint()..color = SkyColors.borderSubtle.withValues(alpha: 0.5),
    );

    final mwPaint = Paint()
      ..color = SkyColors.textSecondary.withValues(alpha: 0.4)
      ..strokeWidth = 1.5;
    for (var l = 0; l < 360; l += 4) {
      final eq = galacticToEquatorial(l.toDouble(), 0.0);
      final p = _project(eq.ra, eq.dec, size);
      canvas.drawCircle(p, 1.3, mwPaint);
    }

    final target = _project(raDeg, decDeg, size);
    canvas.drawCircle(
      target,
      11.0,
      Paint()..color = SkyColors.accentAmber.withValues(alpha: 0.25),
    );
    canvas.drawCircle(
      target,
      5.5,
      Paint()..color = SkyColors.accentAmber,
    );
  }

  @override
  bool shouldRepaint(covariant SkyMapPainter oldDelegate) =>
      oldDelegate.raDeg != raDeg || oldDelegate.decDeg != decDeg;
}
