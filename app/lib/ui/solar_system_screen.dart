import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:url_launcher/url_launcher.dart';

import '../data/firestore_repository.dart';
import '../domain/astro.dart';
import '../domain/solar.dart';
import 'sky_media_widgets.dart';
import 'theme.dart';

class SolarSystemScreen extends StatefulWidget {
  const SolarSystemScreen({super.key, required this.repository});

  final SkyAlertsRepository repository;

  @override
  State<SolarSystemScreen> createState() => _SolarSystemScreenState();
}

class _SolarSystemScreenState extends State<SolarSystemScreen> {
  OverviewRollup? _overview;
  String _searchQuery = '';
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() => _loading = true);
    final ov = await widget.repository.fetchOverview();
    if (!mounted) return;
    setState(() {
      _overview = ov;
      _loading = false;
    });
  }

  @override
  Widget build(BuildContext context) {
    final overview = _overview;
    final q = _searchQuery.trim().toLowerCase();
    final matched = (overview?.matchedAsteroids ?? const []).where((m) {
      if (q.isEmpty) return true;
      final name = ('${m['sso_name'] ?? ''}').toLowerCase();
      final numStr = '${m['sso_number'] ?? ''}';
      final oid = ('${m['oid'] ?? ''}').toLowerCase();
      final cls = ('${m['sso_class'] ?? ''}').toLowerCase();
      return name.contains(q) || numStr.contains(q) || oid.contains(q) || cls.contains(q);
    }).toList();

    return Scaffold(
      appBar: AppBar(
        title: const Text('Solar System · Dwarf Planets & Asteroid Catches'),
        actions: [
          IconButton(
            onPressed: _load,
            icon: const Icon(Icons.refresh),
            tooltip: 'Refresh Solar System ephemerides',
          ),
        ],
      ),
      body: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 1120),
          child: _loading
              ? const Center(child: CircularProgressIndicator())
              : RefreshIndicator(
                  onRefresh: _load,
                  child: ListView(
                    padding: const EdgeInsets.all(16),
                    children: [
                      if (overview != null && overview.solarEphemerides.isNotEmpty) ...[
                        Card(
                          child: Padding(
                            padding: const EdgeInsets.all(16),
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                const Text(
                                  'Tonight’s Outer Solar System Sky Map (Live JPL Horizons)',
                                  style: TextStyle(
                                    fontSize: 16,
                                    fontWeight: FontWeight.bold,
                                  ),
                                ),
                                const SizedBox(height: 4),
                                const Text(
                                  'All-sky J2000 positions of Pluto, Ceres, Eris, Haumea, Makemake, Sedna, Quaoar, Orcus, and Gonggong.',
                                  style: TextStyle(
                                    fontSize: 12,
                                    color: SkyColors.textSecondary,
                                  ),
                                ),
                                const SizedBox(height: 12),
                                SizedBox(
                                  height: 210,
                                  width: double.infinity,
                                  child: CustomPaint(
                                    painter: _SolarEclipticMapPainter(
                                      ephemerides: overview.solarEphemerides,
                                    ),
                                  ),
                                ),
                              ],
                            ),
                          ),
                        ),
                        const SizedBox(height: 20),
                      ],
                      const Text(
                        'PLUTO & OUTER SOLAR SYSTEM DWARF PLANETS (LIVE JPL HORIZONS)',
                        style: TextStyle(
                          fontSize: 12,
                          fontWeight: FontWeight.bold,
                          letterSpacing: 1.1,
                          color: SkyColors.textSecondary,
                        ),
                      ),
                      const SizedBox(height: 8),
                      ...solarBodies.map((body) {
                        final ephemRaw = overview?.solarEphemerides[body.id];
                        final ephem = ephemRaw is Map
                            ? Map<String, dynamic>.from(ephemRaw)
                            : null;
                        final ra = (ephem?['ra'] as num?)?.toDouble();
                        final dec = (ephem?['dec'] as num?)?.toDouble();
                        final mag = (ephem?['mag'] as num?)?.toDouble();
                        final distAu = (ephem?['distance_au'] as num?)?.toDouble();
                        final elong = (ephem?['elongation'] as num?)?.toDouble();
                        final cnst = ephem?['constellation'] as String?;

                        return Card(
                          margin: const EdgeInsets.only(bottom: 12),
                          child: Padding(
                            padding: const EdgeInsets.all(16),
                            child: Row(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                SkyCutoutThumbnail(
                                  ra: ra,
                                  dec: dec,
                                  width: 84,
                                  height: 84,
                                  title: '(${body.number}) ${body.name} · Tonight’s Sky Field',
                                ),
                                const SizedBox(width: 14),
                                Expanded(
                                  child: Column(
                                    crossAxisAlignment: CrossAxisAlignment.start,
                                    children: [
                                      Wrap(
                                        spacing: 8,
                                        runSpacing: 6,
                                        crossAxisAlignment: WrapCrossAlignment.center,
                                        children: [
                                          Text(
                                            '(${body.number}) ${body.name}',
                                            style: const TextStyle(
                                              fontSize: 17,
                                              fontWeight: FontWeight.bold,
                                            ),
                                          ),
                                          Chip(
                                            label: Text(
                                              body.status == 'dwarf'
                                                  ? 'IAU Dwarf Planet'
                                                  : 'Candidate',
                                              style: const TextStyle(fontSize: 11),
                                            ),
                                          ),
                                          TextButton.icon(
                                            onPressed: () =>
                                                launchUrl(Uri.parse(body.jplUrl)),
                                            icon: const Icon(Icons.open_in_new, size: 15),
                                            label: const Text('JPL SBDB'),
                                          ),
                                        ],
                                      ),
                                      const SizedBox(height: 4),
                                      Text(
                                        body.blurb,
                                        style: const TextStyle(
                                          color: SkyColors.textSecondary,
                                        ),
                                      ),
                                      if (ephem != null && ra != null && dec != null) ...[
                                        const Divider(height: 20),
                                        Wrap(
                                          spacing: 18,
                                          runSpacing: 6,
                                          children: [
                                            Text(
                                              'Tonight RA/Dec: ${formatRa(ra)} ${formatDec(dec)}',
                                            ),
                                            if (cnst != null)
                                              Text('Constellation: $cnst'),
                                            if (mag != null)
                                              Text(
                                                'V mag: ${mag.toStringAsFixed(1)}',
                                                style: const TextStyle(
                                                  color: SkyColors.accentAmber,
                                                ),
                                              ),
                                            if (distAu != null)
                                              Text(
                                                'Distance: ${distAu.toStringAsFixed(2)} AU',
                                              ),
                                            if (elong != null)
                                              Text(
                                                viewingHint(elongation: elong, mag: mag),
                                                style: const TextStyle(
                                                  color: SkyColors.textSecondary,
                                                ),
                                              ),
                                          ],
                                        ),
                                      ],
                                    ],
                                  ),
                                ),
                              ],
                            ),
                          ),
                        );
                      }),
                      const SizedBox(height: 20),
                      if (overview != null && overview.matchedAsteroids.isNotEmpty) ...[
                        Text(
                          'RECENT SURVEY ASTEROIDS MATCHED VIA IMCCE SKYBOT (${overview.matchedAsteroids.length})',
                          style: const TextStyle(
                            fontSize: 12,
                            fontWeight: FontWeight.bold,
                            letterSpacing: 1.1,
                            color: SkyColors.textSecondary,
                          ),
                        ),
                        const SizedBox(height: 8),
                        TextField(
                          onChanged: (v) => setState(() => _searchQuery = v),
                          decoration: InputDecoration(
                            hintText:
                                'Filter matched asteroids by name, number, orbit class, or ZTF/Rubin ID...',
                            prefixIcon: const Icon(Icons.search, size: 20),
                            filled: true,
                            fillColor: SkyColors.bgSurface,
                            contentPadding: const EdgeInsets.symmetric(
                              horizontal: 14,
                              vertical: 10,
                            ),
                            border: OutlineInputBorder(
                              borderRadius: BorderRadius.circular(10),
                              borderSide: const BorderSide(color: SkyColors.borderSubtle),
                            ),
                          ),
                        ),
                        const SizedBox(height: 10),
                        ...matched.map((m) {
                          final name = (m['sso_name'] as String?) ?? 'Asteroid';
                          final numVal = (m['sso_number'] as num?)?.toInt();
                          final label = formatSsoLabel(numVal, name);
                          final survey = (m['survey'] as String?) ?? 'ztf';
                          final oid = (m['oid'] as String?) ?? '';
                          final sep = (m['sep_arcsec'] as num?)?.toDouble();
                          final ssoClass = m['sso_class'] as String?;
                          final predMag = (m['predicted_mag'] as num?)?.toDouble();
                          final helioAu = (m['helio_dist_au'] as num?)?.toDouble();
                          final sbdb = jplSbdbUrl(numVal, name);

                          return Card(
                            margin: const EdgeInsets.only(bottom: 8),
                            child: ListTile(
                              onTap: () => context.go('/objects/$survey/$oid'),
                              leading: CircleAvatar(
                                backgroundColor:
                                    const Color(0xFF3DDC97).withValues(alpha: 0.16),
                                child: const Icon(
                                  Icons.track_changes,
                                  size: 18,
                                  color: Color(0xFF3DDC97),
                                ),
                              ),
                              title: Row(
                                children: [
                                  Expanded(
                                    child: Text(
                                      label,
                                      style: const TextStyle(fontWeight: FontWeight.bold),
                                    ),
                                  ),
                                  if (ssoClass != null)
                                    Container(
                                      padding: const EdgeInsets.symmetric(
                                        horizontal: 7,
                                        vertical: 2,
                                      ),
                                      decoration: BoxDecoration(
                                        color: SkyColors.bgElevated,
                                        borderRadius: BorderRadius.circular(4),
                                      ),
                                      child: Text(
                                        ssoClass,
                                        style: const TextStyle(
                                          fontSize: 10,
                                          color: SkyColors.textSecondary,
                                        ),
                                      ),
                                    ),
                                ],
                              ),
                              subtitle: Text(
                                'Alert $oid (${survey.toUpperCase()}) · '
                                '${sep != null ? "${sep.toStringAsFixed(2)}″ sep" : "matched"}'
                                '${predMag != null ? " · V mag ${predMag.toStringAsFixed(1)}" : ""}'
                                '${helioAu != null ? " · ${helioAu.toStringAsFixed(2)} AU" : ""}',
                              ),
                              trailing: sbdb != null
                                  ? IconButton(
                                      tooltip: 'Open JPL Small-Body Database',
                                      onPressed: () => launchUrl(Uri.parse(sbdb)),
                                      icon: const Icon(Icons.open_in_new, size: 18),
                                    )
                                  : const Icon(Icons.chevron_right),
                            ),
                          );
                        }),
                      ],
                    ],
                  ),
                ),
        ),
      ),
    );
  }
}

class _SolarEclipticMapPainter extends CustomPainter {
  const _SolarEclipticMapPainter({required this.ephemerides});

  final Map<String, dynamic> ephemerides;

  Offset _project(double ra, double dec, Size size) {
    final l = ((180.0 - ra) * math.pi) / 180.0;
    final phi = (dec * math.pi) / 180.0;
    final alpha = math.acos((math.cos(phi) * math.cos(l / 2.0)).clamp(-1.0, 1.0));
    final sinc = alpha == 0.0 ? 1.0 : math.sin(alpha) / alpha;
    final x = (2.0 * math.cos(phi) * math.sin(l / 2.0)) / sinc;
    final y = math.sin(phi) / sinc;
    final cx = size.width / 2.0 + (x / math.pi) * (size.width * 0.44);
    final cy = size.height / 2.0 - (y / (math.pi / 2.0)) * (size.height * 0.42);
    return Offset(cx, cy);
  }

  @override
  void paint(Canvas canvas, Size size) {
    canvas.drawOval(
      Rect.fromCenter(
        center: Offset(size.width / 2, size.height / 2),
        width: size.width * 0.9,
        height: size.height * 0.86,
      ),
      Paint()
        ..color = SkyColors.borderSubtle
        ..style = PaintingStyle.stroke
        ..strokeWidth = 1.2,
    );

    // Draw celestial equator
    canvas.drawLine(
      Offset(size.width * 0.05, size.height / 2),
      Offset(size.width * 0.95, size.height / 2),
      Paint()..color = SkyColors.borderSubtle.withValues(alpha: 0.5),
    );

    for (final body in solarBodies) {
      final raw = ephemerides[body.id];
      if (raw is! Map) continue;
      final ra = (raw['ra'] as num?)?.toDouble();
      final dec = (raw['dec'] as num?)?.toDouble();
      if (ra == null || dec == null) continue;
      final pt = _project(ra, dec, size);
      final color = body.status == 'dwarf'
          ? const Color(0xFF3DDC97)
          : SkyColors.accentAmber;
      canvas.drawCircle(pt, 5.0, Paint()..color = color);

      final tp = TextPainter(
        text: TextSpan(
          text: body.name,
          style: const TextStyle(
            fontSize: 10,
            fontWeight: FontWeight.w600,
            color: SkyColors.textPrimary,
          ),
        ),
        textDirection: TextDirection.ltr,
      )..layout();
      tp.paint(canvas, Offset(pt.dx + 6, pt.dy - 6));
    }
  }

  @override
  bool shouldRepaint(covariant _SolarEclipticMapPainter oldDelegate) =>
      oldDelegate.ephemerides != ephemerides;
}
