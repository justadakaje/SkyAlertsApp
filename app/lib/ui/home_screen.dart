import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../data/firestore_repository.dart';
import '../domain/astro.dart';
import '../domain/classes.dart';
import '../domain/format.dart';
import '../domain/solar.dart';
import 'sky_media_widgets.dart';
import 'theme.dart';

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key, required this.repository});

  final SkyAlertsRepository repository;

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  String? _selectedSurvey;
  ClassGroup? _selectedGroup;
  bool _newestFirst = false;
  bool _includeArtifacts = false;
  String _searchQuery = '';
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
          limit: 60,
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

  List<CatalogObject> get _filteredObjects {
    final q = _searchQuery.trim().toLowerCase();
    return _objects.where((obj) {
      if (_selectedGroup != null &&
          !(_includeArtifacts && obj.isArtifact) &&
          groupOf(obj.topClass) != _selectedGroup) {
        return false;
      }
      if (q.isEmpty) return true;
      final info = classInfo(obj.topClass);
      final ssoName = obj.sso?.ssoName?.toLowerCase() ?? '';
      return obj.oid.toLowerCase().contains(q) ||
          (obj.topClass?.toLowerCase().contains(q) ?? false) ||
          info.label.toLowerCase().contains(q) ||
          ssoName.contains(q);
    }).toList();
  }

  int _groupCount7d(OverviewRollup? ov, ClassGroup group) {
    final map7d = ov?.windowClassCounts['7d'];
    if (map7d == null) return 0;
    var sum = 0;
    for (final entry in map7d.entries) {
      final cls = entry.key == '__null__' ? null : entry.key;
      if (cls == artifactClass) continue;
      if (groupOf(cls) == group) {
        sum += entry.value;
      }
    }
    return sum;
  }

  @override
  Widget build(BuildContext context) {
    final overview = _overview;
    final filtered = _filteredObjects;

    return Scaffold(
      appBar: AppBar(
        title: const Text('Sky Alerts · Live Observatory Feed'),
        actions: [
          if (overview != null && (overview.weeklyDispatchPodcast?.isNotEmpty ?? false))
            IconButton(
              tooltip: 'Listen to Weekly Sky Dispatch',
              onPressed: () => showSkyDispatchSheet(
                context,
                subject: overview.weeklyDispatchSubject ?? 'Weekly Sky Dispatch',
                podcastScript: overview.weeklyDispatchPodcast ?? '',
                markdownDispatch: overview.weeklyDispatchMarkdown ?? '',
              ),
              icon: const Icon(Icons.podcasts, color: SkyColors.accentAmber),
            ),
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
                  ? Center(
                      child: Padding(
                        padding: const EdgeInsets.all(24),
                        child: Card(
                          child: Padding(
                            padding: const EdgeInsets.all(20),
                            child: Column(
                              mainAxisSize: MainAxisSize.min,
                              children: [
                                const Icon(
                                  Icons.warning_amber_rounded,
                                  size: 36,
                                  color: SkyColors.accentAmber,
                                ),
                                const SizedBox(height: 12),
                                Text(
                                  'Error loading feed: $_error',
                                  textAlign: TextAlign.center,
                                ),
                                const SizedBox(height: 16),
                                Wrap(
                                  spacing: 12,
                                  children: [
                                    FilledButton.icon(
                                      onPressed: _load,
                                      icon: const Icon(Icons.refresh, size: 18),
                                      label: const Text('Retry'),
                                    ),
                                    OutlinedButton(
                                      onPressed: () {
                                        _selectedSurvey = null;
                                        _selectedGroup = null;
                                        _newestFirst = false;
                                        _includeArtifacts = false;
                                        _searchQuery = '';
                                        _load();
                                      },
                                      child: const Text('Reset Filters & Retry'),
                                    ),
                                  ],
                                ),
                              ],
                            ),
                          ),
                        ),
                      ),
                    )
                  : RefreshIndicator(
                      onRefresh: _load,
                      child: ListView(
                        padding: const EdgeInsets.all(16),
                        children: [
                          if (overview != null) ...[
                            _ObservatoryHeroBanner(overview: overview),
                            const SizedBox(height: 18),
                          ],
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
                                      width: 355,
                                      child: Card(
                                        child: InkWell(
                                          borderRadius: BorderRadius.circular(12),
                                          onTap: () => context.go(
                                            '/objects/${h.survey}/${h.oid}',
                                          ),
                                          child: Padding(
                                            padding: const EdgeInsets.all(12),
                                            child: Row(
                                              crossAxisAlignment: CrossAxisAlignment.start,
                                              children: [
                                                SkyCutoutThumbnail(
                                                  ra: h.ra,
                                                  dec: h.dec,
                                                  width: 78,
                                                  height: 78,
                                                  title: h.headline,
                                                ),
                                                const SizedBox(width: 12),
                                                Expanded(
                                                  child: Column(
                                                    crossAxisAlignment:
                                                        CrossAxisAlignment.start,
                                                    children: [
                                                      Text(
                                                        h.eyebrow.toUpperCase(),
                                                        style: const TextStyle(
                                                          fontSize: 10,
                                                          fontWeight: FontWeight.w700,
                                                          letterSpacing: 0.6,
                                                          color: SkyColors.accentAmber,
                                                        ),
                                                      ),
                                                      const SizedBox(height: 4),
                                                      Text(
                                                        h.headline,
                                                        style: const TextStyle(
                                                          fontSize: 14,
                                                          fontWeight: FontWeight.bold,
                                                        ),
                                                      ),
                                                      const SizedBox(height: 4),
                                                      Text(
                                                        h.subtitle,
                                                        maxLines: 3,
                                                        overflow: TextOverflow.ellipsis,
                                                        style: const TextStyle(
                                                          fontSize: 12,
                                                          color: SkyColors.textSecondary,
                                                        ),
                                                      ),
                                                    ],
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
                          TextField(
                            onChanged: (v) => setState(() => _searchQuery = v),
                            decoration: InputDecoration(
                              hintText:
                                  'Search by Object ID, asteroid name, or class (e.g. SNIa, SLSN, ZTF...)',
                              prefixIcon: const Icon(Icons.search, size: 20),
                              suffixIcon: _searchQuery.isNotEmpty
                                  ? IconButton(
                                      icon: const Icon(Icons.clear, size: 18),
                                      onPressed: () => setState(() => _searchQuery = ''),
                                    )
                                  : null,
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
                              enabledBorder: OutlineInputBorder(
                                borderRadius: BorderRadius.circular(10),
                                borderSide: const BorderSide(color: SkyColors.borderSubtle),
                              ),
                            ),
                          ),
                          const SizedBox(height: 12),
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
                          const SizedBox(height: 8),
                          SingleChildScrollView(
                            scrollDirection: Axis.horizontal,
                            child: Row(
                              children: [
                                Padding(
                                  padding: const EdgeInsets.only(right: 8),
                                  child: ChoiceChip(
                                    label: const Text('All Categories'),
                                    selected: _selectedGroup == null,
                                    onSelected: (_) =>
                                        setState(() => _selectedGroup = null),
                                  ),
                                ),
                                ...[
                                  ClassGroup.transients,
                                  ClassGroup.variables,
                                  ClassGroup.agn,
                                  ClassGroup.solar,
                                ].map((grp) {
                                  final cnt = _groupCount7d(overview, grp);
                                  final label = cnt > 0
                                      ? '${grp.label} (${formatCount(cnt)})'
                                      : grp.label;
                                  return Padding(
                                    padding: const EdgeInsets.only(right: 8),
                                    child: ChoiceChip(
                                      label: Text(label),
                                      selected: _selectedGroup == grp,
                                      onSelected: (_) => setState(
                                        () => _selectedGroup =
                                            _selectedGroup == grp ? null : grp,
                                      ),
                                    ),
                                  );
                                }),
                              ],
                            ),
                          ),
                          const SizedBox(height: 16),
                          if (filtered.isEmpty)
                            const Card(
                              child: Padding(
                                padding: EdgeInsets.all(24),
                                child: Center(
                                  child: Text(
                                    'No objects match the current search/filter criteria.',
                                    style: TextStyle(color: SkyColors.textSecondary),
                                  ),
                                ),
                              ),
                            )
                          else
                            ...filtered.map((obj) => _ObjectCard(object: obj)),
                        ],
                      ),
                    ),
        ),
      ),
    );
  }
}

class _ObservatoryHeroBanner extends StatelessWidget {
  const _ObservatoryHeroBanner({required this.overview});

  final OverviewRollup overview;

  @override
  Widget build(BuildContext context) {
    final hasPodcast = (overview.weeklyDispatchPodcast?.isNotEmpty ?? false);
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        gradient: const LinearGradient(
          colors: [Color(0xFF162035), Color(0xFF101624)],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: SkyColors.borderSubtle),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Icon(Icons.auto_awesome, size: 18, color: SkyColors.accentAmber),
              const SizedBox(width: 8),
              const Expanded(
                child: Text(
                  'VERA C. RUBIN OBSERVATORY (LSST) & ZWICKY TRANSIENT FACILITY',
                  style: TextStyle(
                    fontSize: 11,
                    fontWeight: FontWeight.w700,
                    letterSpacing: 1.0,
                    color: SkyColors.accentAmber,
                  ),
                ),
              ),
              if (hasPodcast)
                FilledButton.tonalIcon(
                  onPressed: () => showSkyDispatchSheet(
                    context,
                    subject: overview.weeklyDispatchSubject ?? 'Weekly Sky Dispatch',
                    podcastScript: overview.weeklyDispatchPodcast ?? '',
                    markdownDispatch: overview.weeklyDispatchMarkdown ?? '',
                  ),
                  icon: const Icon(Icons.podcasts, size: 16),
                  label: const Text('Sky Dispatch Audio & Briefing'),
                ),
            ],
          ),
          const SizedBox(height: 12),
          Wrap(
            spacing: 24,
            runSpacing: 10,
            children: [
              _StatBadge(
                label: 'Cataloged Objects',
                value: formatCount(overview.totalObjects),
              ),
              _StatBadge(
                label: 'New (7 Days)',
                value: formatCount(overview.newThisWeek),
              ),
              _StatBadge(
                label: 'Cosmic Explosions (7d)',
                value: formatCount(overview.transientsThisWeek),
                highlight: true,
              ),
              _StatBadge(
                label: 'SkyBoT Asteroids Matched',
                value: formatCount(overview.matchedAsteroids.length),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class _StatBadge extends StatelessWidget {
  const _StatBadge({
    required this.label,
    required this.value,
    this.highlight = false,
  });

  final String label;
  final String value;
  final bool highlight;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          value,
          style: TextStyle(
            fontSize: 20,
            fontWeight: FontWeight.bold,
            color: highlight ? const Color(0xFFFF6B4A) : SkyColors.textPrimary,
          ),
        ),
        Text(
          label,
          style: const TextStyle(fontSize: 11, color: SkyColors.textSecondary),
        ),
      ],
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
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                SkyCutoutThumbnail(
                  ra: object.meanRa,
                  dec: object.meanDec,
                  width: 82,
                  height: 82,
                  title: '${object.oid} (${info.label})',
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
                          Container(
                            padding: const EdgeInsets.symmetric(
                              horizontal: 8,
                              vertical: 3,
                            ),
                            decoration: BoxDecoration(
                              color: groupColor.withValues(alpha: 0.16),
                              borderRadius: BorderRadius.circular(6),
                              border: Border.all(
                                color: groupColor.withValues(alpha: 0.5),
                              ),
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
                          if (ssoLabel != null)
                            Container(
                              padding: const EdgeInsets.symmetric(
                                horizontal: 8,
                                vertical: 3,
                              ),
                              decoration: BoxDecoration(
                                color: SkyColors.accentAmber.withValues(alpha: 0.18),
                                borderRadius: BorderRadius.circular(6),
                              ),
                              child: Text(
                                'Asteroid $ssoLabel',
                                style: const TextStyle(
                                  fontSize: 12,
                                  fontWeight: FontWeight.w600,
                                  color: SkyColors.accentAmber,
                                ),
                              ),
                            ),
                          if (object.peakMag != null)
                            Container(
                              padding: const EdgeInsets.symmetric(
                                horizontal: 7,
                                vertical: 2,
                              ),
                              decoration: BoxDecoration(
                                color: SkyColors.bgElevated,
                                borderRadius: BorderRadius.circular(6),
                              ),
                              child: Text(
                                'Peak mag ${object.peakMag!.toStringAsFixed(1)}'
                                '${object.peakBand != null ? " (${object.peakBand})" : ""}',
                                style: const TextStyle(
                                  fontSize: 11,
                                  color: SkyColors.accentAmber,
                                ),
                              ),
                            ),
                          Container(
                            padding: const EdgeInsets.symmetric(
                              horizontal: 6,
                              vertical: 2,
                            ),
                            decoration: BoxDecoration(
                              color: object.survey == 'lsst'
                                  ? const Color(0xFF38BDF8).withValues(alpha: 0.16)
                                  : SkyColors.bgElevated,
                              borderRadius: BorderRadius.circular(4),
                            ),
                            child: Text(
                              object.survey == 'lsst' ? 'RUBIN · LSST' : 'ZTF',
                              style: TextStyle(
                                fontSize: 10,
                                fontWeight: FontWeight.bold,
                                color: object.survey == 'lsst'
                                    ? const Color(0xFF38BDF8)
                                    : SkyColors.textSecondary,
                              ),
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 6),
                      Text(
                        object.oid,
                        style: const TextStyle(
                          fontSize: 16,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                      const SizedBox(height: 3),
                      Text(
                        info.blurb,
                        style: const TextStyle(
                          fontSize: 13,
                          color: SkyColors.textSecondary,
                        ),
                      ),
                      const SizedBox(height: 8),
                      Wrap(
                        spacing: 14,
                        runSpacing: 4,
                        children: [
                          Text(
                            'Confidence: ${formatProbability(object.topProbability)}',
                            style: const TextStyle(
                              fontSize: 12,
                              color: SkyColors.textSecondary,
                            ),
                          ),
                          Text(
                            'Detections: ${formatCount(object.nDetections)}',
                            style: const TextStyle(
                              fontSize: 12,
                              color: SkyColors.textSecondary,
                            ),
                          ),
                          Text(
                            'J2000: ${formatRa(object.meanRa)} ${formatDec(object.meanDec)}',
                            style: const TextStyle(
                              fontSize: 12,
                              color: SkyColors.textSecondary,
                            ),
                          ),
                          Text(
                            'Last seen: ${formatAgo(object.lastMjd)}',
                            style: const TextStyle(
                              fontSize: 12,
                              color: SkyColors.textSecondary,
                            ),
                          ),
                        ],
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
