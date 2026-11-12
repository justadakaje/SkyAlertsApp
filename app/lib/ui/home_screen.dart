import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../data/firestore_repository.dart';
import '../domain/astro.dart';
import '../domain/classes.dart';
import '../domain/format.dart';
import '../domain/solar.dart';
import 'theme.dart';

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key, required this.repository});

  final SkyAlertsRepository repository;

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  String? _selectedSurvey;
  bool _newestFirst = false;
  bool _includeArtifacts = false;
  OverviewRollup? _overview;
  List<CatalogObject> _objects = const [];
  bool _loading = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final results = await Future.wait([
        widget.repository.fetchOverview(),
        widget.repository.fetchCatalogFeed(
          survey: _selectedSurvey,
          newestFirst: _newestFirst,
          includeArtifacts: _includeArtifacts,
        ),
      ]);
      if (!mounted) return;
      setState(() {
        _overview = results[0] as OverviewRollup;
        _objects = results[1] as List<CatalogObject>;
        _loading = false;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _error = '$e';
        _loading = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final overview = _overview;
    return Scaffold(
      appBar: AppBar(
        title: const Text('Sky Alerts · What the Sky Is Doing'),
        actions: [
          IconButton(
            onPressed: _load,
            icon: const Icon(Icons.refresh),
            tooltip: 'Refresh feed',
          ),
        ],
      ),
      body: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 1120),
          child: _loading
              ? const Center(child: CircularProgressIndicator())
              : _error != null
                  ? Center(child: Text('Error loading feed: $_error'))
                  : RefreshIndicator(
                      onRefresh: _load,
                      child: ListView(
                        padding: const EdgeInsets.all(16),
                        children: [
                          if (overview != null && overview.highlights.isNotEmpty) ...[
                            const Text(
                              'WHAT STOOD OUT RECENTLY',
                              style: TextStyle(
                                fontSize: 12,
                                fontWeight: FontWeight.w700,
                                letterSpacing: 1.1,
                                color: SkyColors.textSecondary,
                              ),
                            ),
                            const SizedBox(height: 8),
                            Wrap(
                              spacing: 12,
                              runSpacing: 12,
                              children: overview.highlights
                                  .map(
                                    (h) => SizedBox(
                                      width: 340,
                                      child: Card(
                                        child: InkWell(
                                          borderRadius: BorderRadius.circular(12),
                                          onTap: () => context.go(
                                            '/objects/${h.survey}/${h.oid}',
                                          ),
                                          child: Padding(
                                            padding: const EdgeInsets.all(14),
                                            child: Column(
                                              crossAxisAlignment: CrossAxisAlignment.start,
                                              children: [
                                                Text(
                                                  h.eyebrow.toUpperCase(),
                                                  style: const TextStyle(
                                                    fontSize: 11,
                                                    fontWeight: FontWeight.w600,
                                                    color: SkyColors.accentAmber,
                                                  ),
                                                ),
                                                const SizedBox(height: 6),
                                                Text(
                                                  h.headline,
                                                  style: const TextStyle(
                                                    fontSize: 15,
                                                    fontWeight: FontWeight.bold,
                                                  ),
                                                ),
                                                const SizedBox(height: 4),
                                                Text(
                                                  h.subtitle,
                                                  style: const TextStyle(
                                                    fontSize: 13,
                                                    color: SkyColors.textSecondary,
                                                  ),
                                                ),
                                              ],
                                            ),
                                          ),
                                        ),
                                      ),
                                    ),
                                  )
                                  .toList(),
                            ),
                            const SizedBox(height: 20),
                          ],
                          Wrap(
                            spacing: 8,
                            runSpacing: 8,
                            crossAxisAlignment: WrapCrossAlignment.center,
                            children: [
                              ChoiceChip(
                                label: const Text('All surveys'),
                                selected: _selectedSurvey == null,
                                onSelected: (_) {
                                  _selectedSurvey = null;
                                  _load();
                                },
                              ),
                              ChoiceChip(
                                label: const Text('Rubin (LSST)'),
                                selected: _selectedSurvey == 'lsst',
                                onSelected: (_) {
                                  _selectedSurvey = 'lsst';
                                  _load();
                                },
                              ),
                              ChoiceChip(
                                label: const Text('ZTF'),
                                selected: _selectedSurvey == 'ztf',
                                onSelected: (_) {
                                  _selectedSurvey = 'ztf';
                                  _load();
                                },
                              ),
                              FilterChip(
                                label: Text(_newestFirst ? 'Sort: Newest' : 'Sort: Notable first'),
                                selected: _newestFirst,
                                onSelected: (val) {
                                  _newestFirst = val;
                                  _load();
                                },
                              ),
                              FilterChip(
                                label: const Text('Include artifacts'),
                                selected: _includeArtifacts,
                                onSelected: (val) {
                                  _includeArtifacts = val;
                                  _load();
                                },
                              ),
                            ],
                          ),
                          const SizedBox(height: 16),
                          ..._objects.map((obj) => _ObjectCard(object: obj)),
                        ],
                      ),
                    ),
        ),
      ),
    );
  }
}

class _ObjectCard extends StatelessWidget {
  const _ObjectCard({required this.object});

  final CatalogObject object;

  @override
  Widget build(BuildContext context) {
    final info = classInfo(object.topClass);
    final groupColor = SkyColors.forGroup(info.group);
    final sso = object.sso;
    final ssoLabel = (sso != null && sso.isMatched)
        ? formatSsoLabel(sso.ssoNumber, sso.ssoName!)
        : null;

    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: Card(
        child: InkWell(
          borderRadius: BorderRadius.circular(12),
          onTap: () => context.go('/objects/${object.survey}/${object.oid}'),
          child: Padding(
            padding: const EdgeInsets.all(14),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                      decoration: BoxDecoration(
                        color: groupColor.withValues(alpha: 0.16),
                        borderRadius: BorderRadius.circular(6),
                        border: Border.all(color: groupColor.withValues(alpha: 0.5)),
                      ),
                      child: Text(
                        info.label,
                        style: TextStyle(
                          fontSize: 12,
                          fontWeight: FontWeight.w600,
                          color: groupColor,
                        ),
                      ),
                    ),
                    const SizedBox(width: 8),
                    if (ssoLabel != null)
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                        decoration: BoxDecoration(
                          color: SkyColors.accentAmber.withValues(alpha: 0.18),
                          borderRadius: BorderRadius.circular(6),
                        ),
                        child: Text(
                          'Known asteroid: $ssoLabel',
                          style: const TextStyle(
                            fontSize: 12,
                            fontWeight: FontWeight.w600,
                            color: SkyColors.accentAmber,
                          ),
                        ),
                      ),
                    const Spacer(),
                    Text(
                      object.survey.toUpperCase(),
                      style: const TextStyle(
                        fontSize: 12,
                        fontWeight: FontWeight.bold,
                        color: SkyColors.textSecondary,
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 8),
                Text(
                  object.oid,
                  style: const TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
                ),
                const SizedBox(height: 4),
                Text(
                  info.blurb,
                  style: const TextStyle(fontSize: 13, color: SkyColors.textSecondary),
                ),
                const SizedBox(height: 8),
                Wrap(
                  spacing: 16,
                  runSpacing: 4,
                  children: [
                    Text(
                      'Confidence: ${formatProbability(object.topProbability)}',
                      style: const TextStyle(fontSize: 12, color: SkyColors.textSecondary),
                    ),
                    Text(
                      'Detections: ${formatCount(object.nDetections)}',
                      style: const TextStyle(fontSize: 12, color: SkyColors.textSecondary),
                    ),
                    Text(
                      'Coords: ${formatRa(object.meanRa)} ${formatDec(object.meanDec)}',
                      style: const TextStyle(fontSize: 12, color: SkyColors.textSecondary),
                    ),
                    Text(
                      'Last seen: ${formatAgo(object.lastMjd)}',
                      style: const TextStyle(fontSize: 12, color: SkyColors.textSecondary),
                    ),
                  ],
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
