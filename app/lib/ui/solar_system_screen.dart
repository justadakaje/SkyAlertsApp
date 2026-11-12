import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:url_launcher/url_launcher.dart';

import '../data/firestore_repository.dart';
import '../domain/astro.dart';
import '../domain/solar.dart';
import 'theme.dart';

class SolarSystemScreen extends StatefulWidget {
  const SolarSystemScreen({super.key, required this.repository});

  final SkyAlertsRepository repository;

  @override
  State<SolarSystemScreen> createState() => _SolarSystemScreenState();
}

class _SolarSystemScreenState extends State<SolarSystemScreen> {
  OverviewRollup? _overview;
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
    return Scaffold(
      appBar: AppBar(title: const Text('Solar System · Dwarf Planets & Asteroid Catches')),
      body: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 1120),
          child: _loading
              ? const Center(child: CircularProgressIndicator())
              : ListView(
                  padding: const EdgeInsets.all(16),
                  children: [
                    if (overview != null && overview.matchedAsteroids.isNotEmpty) ...[
                      const Text(
                        'RECENT SURVEY ASTEROIDS MATCHED VIA IMCCE SKYBOT',
                        style: TextStyle(
                          fontSize: 12,
                          fontWeight: FontWeight.bold,
                          letterSpacing: 1.1,
                          color: SkyColors.textSecondary,
                        ),
                      ),
                      const SizedBox(height: 8),
                      ...overview.matchedAsteroids.map((m) {
                        final name = (m['sso_name'] as String?) ?? 'Asteroid';
                        final numVal = (m['sso_number'] as num?)?.toInt();
                        final label = formatSsoLabel(numVal, name);
                        final survey = (m['survey'] as String?) ?? 'ztf';
                        final oid = (m['oid'] as String?) ?? '';
                        final sep = (m['sep_arcsec'] as num?)?.toDouble();
                        return Card(
                          child: ListTile(
                            onTap: () => context.go('/objects/$survey/$oid'),
                            title: Text(label, style: const TextStyle(fontWeight: FontWeight.bold)),
                            subtitle: Text(
                              'Alert $oid (${survey.toUpperCase()}) · '
                              '${sep != null ? "${sep.toStringAsFixed(2)}″ separation" : "matched"}',
                            ),
                            trailing: const Icon(Icons.chevron_right),
                          ),
                        );
                      }),
                      const SizedBox(height: 24),
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
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Row(
                                children: [
                                  Text(
                                    '(${body.number}) ${body.name}',
                                    style: const TextStyle(
                                      fontSize: 17,
                                      fontWeight: FontWeight.bold,
                                    ),
                                  ),
                                  const SizedBox(width: 8),
                                  Chip(
                                    label: Text(
                                      body.status == 'dwarf' ? 'IAU Dwarf Planet' : 'Candidate',
                                      style: const TextStyle(fontSize: 11),
                                    ),
                                  ),
                                  const Spacer(),
                                  TextButton.icon(
                                    onPressed: () => launchUrl(Uri.parse(body.jplUrl)),
                                    icon: const Icon(Icons.open_in_new, size: 15),
                                    label: const Text('JPL SBDB'),
                                  ),
                                ],
                              ),
                              const SizedBox(height: 4),
                              Text(
                                body.blurb,
                                style: const TextStyle(color: SkyColors.textSecondary),
                              ),
                              if (ephem != null && ra != null && dec != null) ...[
                                const Divider(height: 20),
                                Wrap(
                                  spacing: 20,
                                  runSpacing: 6,
                                  children: [
                                    Text('Tonight RA/Dec: ${formatRa(ra)} ${formatDec(dec)}'),
                                    if (cnst != null) Text('Constellation: $cnst'),
                                    if (mag != null) Text('V mag: ${mag.toStringAsFixed(1)}'),
                                    if (distAu != null)
                                      Text('Distance: ${distAu.toStringAsFixed(2)} AU'),
                                    if (elong != null)
                                      Text(viewingHint(elongation: elong, mag: mag)),
                                  ],
                                ),
                              ],
                            ],
                          ),
                        ),
                      );
                    }),
                  ],
                ),
        ),
      ),
    );
  }
}
