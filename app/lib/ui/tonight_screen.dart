import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:go_router/go_router.dart';

import '../data/firestore_repository.dart';
import '../domain/astro_weather.dart';
import '../domain/backyard_planner.dart';
import '../domain/classes.dart';
import '../domain/pro_entitlement.dart';
import 'gear_card_widget.dart';
import 'pro_paywall_sheet.dart';
import 'theme.dart';
import 'tonight_arc_chart.dart';

final ValueNotifier<ObservatoryLocation> backyardLocationNotifier =
    ValueNotifier<ObservatoryLocation>(ObservatoryLocation.presets.first);

final ValueNotifier<ScopePreset> backyardScopeNotifier =
    ValueNotifier<ScopePreset>(ScopePreset.seestarS50);

final ValueNotifier<double> backyardMinAltNotifier = ValueNotifier<double>(30.0);

class TonightScreen extends StatefulWidget {
  const TonightScreen({super.key, required this.repository});

  final SkyAlertsRepository repository;

  @override
  State<TonightScreen> createState() => _TonightScreenState();
}

class _TonightScreenState extends State<TonightScreen> {
  bool _loading = true;
  String? _error;
  List<CatalogObject> _candidates = const [];
  SevenNightOutlook? _weather;
  bool _weatherLoading = false;
  bool _onlyReachable = false;
  String? _expandedArcId;

  late final TextEditingController _latCtrl;
  late final TextEditingController _lonCtrl;

  @override
  void initState() {
    super.initState();
    final loc = backyardLocationNotifier.value;
    _latCtrl = TextEditingController(text: loc.latitudeDeg.toStringAsFixed(1));
    _lonCtrl = TextEditingController(text: loc.longitudeDeg.toStringAsFixed(1));
    _load();
  }

  @override
  void dispose() {
    _latCtrl.dispose();
    _lonCtrl.dispose();
    super.dispose();
  }

  Future<void> _loadWeather() async {
    setState(() => _weatherLoading = true);
    try {
      final outlook = await fetchSevenNightOutlook(backyardLocationNotifier.value);
      if (!mounted) return;
      setState(() {
        _weather = outlook;
        _weatherLoading = false;
      });
    } catch (_) {
      if (!mounted) return;
      setState(() => _weatherLoading = false);
    }
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    _loadWeather();
    try {
      final list = await widget.repository.fetchBackyardCandidates();
      if (!mounted) return;
      setState(() {
        _candidates = list;
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

  void _applyCoords() {
    final lat = double.tryParse(_latCtrl.text.trim());
    final lon = double.tryParse(_lonCtrl.text.trim());
    if (lat == null || lon == null || lat < -90 || lat > 90 || lon < -180 || lon > 180) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Enter valid latitude (-90..90) and longitude (-180..180).')),
      );
      return;
    }
    final rounded = ObservatoryLocation(latitudeDeg: lat, longitudeDeg: lon).roundedToTenth;
    backyardLocationNotifier.value = rounded;
    _latCtrl.text = rounded.latitudeDeg.toStringAsFixed(1);
    _lonCtrl.text = rounded.longitudeDeg.toStringAsFixed(1);
    setState(() {});
    _loadWeather();
  }

  void _copyCoords(CatalogObject obj) {
    final text = formatCoordinatesForRig(obj);
    Clipboard.setData(ClipboardData(text: text));
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text('Copied J2000 coordinates: $text')),
    );
  }

  void _copyCsv(List<PlannedTarget> targets) {
    final csv = exportPlannedTargetsCsv(targets);
    Clipboard.setData(ClipboardData(text: csv));
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text('Copied ${targets.length} targets as CSV (N.I.N.A./sheet ready).')),
    );
  }

  @override
  Widget build(BuildContext context) {
    final loc = backyardLocationNotifier.value;
    final scope = backyardScopeNotifier.value;
    final minAlt = backyardMinAltNotifier.value;
    final night = summarizeTonight(loc);
    final ranked = rankBackyardTargets(
      _candidates,
      loc,
      scope,
      minAltDeg: minAlt,
      onlyReachable: _onlyReachable,
    );
    final reachableCount = ranked.where((t) => t.reachable).length;

    return Scaffold(
      appBar: AppBar(
        title: const Text('Tonight From My Backyard'),
        actions: [
          ValueListenableBuilder<bool>(
            valueListenable: redNightModeNotifier,
            builder: (context, isRed, _) {
              return IconButton(
                onPressed: () => redNightModeNotifier.value = !isRed,
                tooltip: isRed ? 'Disable Red Night Mode' : 'Enable Red Night Mode (OLED)',
                icon: Icon(
                  isRed ? Icons.nights_stay : Icons.nights_stay_outlined,
                  color: isRed ? SkyRedColors.accentRed : null,
                ),
              );
            },
          ),
          ValueListenableBuilder<ProEntitlementState>(
            valueListenable: proEntitlementNotifier,
            builder: (context, proState, _) {
              return Padding(
                padding: const EdgeInsets.symmetric(vertical: 8),
                child: TextButton.icon(
                  onPressed: () => showProPaywallSheet(context),
                  style: TextButton.styleFrom(
                    foregroundColor: proState.isPro
                        ? const Color(0xFF3DDC97)
                        : SkyColors.accentAmber,
                  ),
                  icon: Icon(
                    proState.isPro
                        ? Icons.verified_outlined
                        : Icons.auto_awesome,
                    size: 18,
                  ),
                  label: Text(proState.isPro ? 'Pro Active' : 'Pro'),
                ),
              );
            },
          ),
          IconButton(
            onPressed: ranked.isEmpty ? null : () => _copyCsv(ranked.take(25).toList()),
            tooltip: 'Copy Target List (CSV)',
            icon: const Icon(Icons.download_outlined),
          ),
          IconButton(
            onPressed: _load,
            tooltip: 'Refresh targets',
            icon: const Icon(Icons.refresh),
          ),
        ],
      ),
      body: RefreshIndicator(
        onRefresh: _load,
        child: ListView(
          padding: const EdgeInsets.all(16),
          children: [
            _buildSetupCard(context, loc, scope, minAlt),
            const SizedBox(height: 12),
            _buildNightSummaryCard(context, night, reachableCount, ranked.length, scope),
            const SizedBox(height: 12),
            _buildWeatherOutlookCard(context),
            const SizedBox(height: 14),
            if (_loading)
              const Padding(
                padding: EdgeInsets.all(32),
                child: Center(child: CircularProgressIndicator()),
              )
            else if (_error != null)
              Card(
                child: Padding(
                  padding: const EdgeInsets.all(16),
                  child: Text('Error loading targets: $_error'),
                ),
              )
            else if (ranked.isEmpty)
              const Card(
                child: Padding(
                  padding: EdgeInsets.all(20),
                  child: Text(
                    'No targets match your current altitude/scope filters tonight. Try lowering minimum altitude or unchecking "Reachable only".',
                  ),
                ),
              )
            else
              ...ranked.take(40).map((t) => _buildTargetCard(context, t, minAlt)),
            const SizedBox(height: 16),
            GearRecommendationCard(magnitude: scope.limitingMag),
          ],
        ),
      ),
    );
  }

  Widget _buildSetupCard(
    BuildContext context,
    ObservatoryLocation loc,
    ScopePreset scope,
    double minAlt,
  ) {
    final secondary = redNightModeNotifier.value
        ? SkyRedColors.textSecondary
        : SkyColors.textSecondary;

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              'Backyard Rig & Location',
              style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
            ),
            const SizedBox(height: 10),
            Wrap(
              spacing: 12,
              runSpacing: 12,
              crossAxisAlignment: WrapCrossAlignment.center,
              children: [
                SizedBox(
                  width: 240,
                  child: DropdownButtonFormField<ScopePreset>(
                    initialValue: scope,
                    isExpanded: true,
                    decoration: const InputDecoration(
                      labelText: 'Telescope / Rig',
                      border: OutlineInputBorder(),
                      isDense: true,
                    ),
                    items: ScopePreset.values
                        .map(
                          (s) => DropdownMenuItem(
                            value: s,
                            child: Text('${s.shortLabel} (≤${s.limitingMag.toStringAsFixed(1)}m)'),
                          ),
                        )
                        .toList(),
                    onChanged: (val) {
                      if (val != null) {
                        backyardScopeNotifier.value = val;
                        setState(() {});
                      }
                    },
                  ),
                ),
                SizedBox(
                  width: 220,
                  child: DropdownButtonFormField<ObservatoryLocation>(
                    initialValue: ObservatoryLocation.presets.any(
                      (p) =>
                          (p.latitudeDeg - loc.latitudeDeg).abs() < 0.05 &&
                          (p.longitudeDeg - loc.longitudeDeg).abs() < 0.05,
                    )
                        ? ObservatoryLocation.presets.firstWhere(
                            (p) =>
                                (p.latitudeDeg - loc.latitudeDeg).abs() < 0.05 &&
                                (p.longitudeDeg - loc.longitudeDeg).abs() < 0.05,
                          )
                        : null,
                    isExpanded: true,
                    decoration: const InputDecoration(
                      labelText: 'Quick Region',
                      border: OutlineInputBorder(),
                      isDense: true,
                    ),
                    hint: const Text('Custom coordinates'),
                    items: ObservatoryLocation.presets
                        .map((p) => DropdownMenuItem(value: p, child: Text(p.label)))
                        .toList(),
                    onChanged: (val) {
                      if (val != null) {
                        backyardLocationNotifier.value = val.roundedToTenth;
                        _latCtrl.text = val.latitudeDeg.toStringAsFixed(1);
                        _lonCtrl.text = val.longitudeDeg.toStringAsFixed(1);
                        setState(() {});
                        _loadWeather();
                      }
                    },
                  ),
                ),
                SizedBox(
                  width: 105,
                  child: TextField(
                    controller: _latCtrl,
                    keyboardType: const TextInputType.numberWithOptions(signed: true, decimal: true),
                    decoration: const InputDecoration(
                      labelText: 'Lat (°)',
                      border: OutlineInputBorder(),
                      isDense: true,
                    ),
                    onSubmitted: (_) => _applyCoords(),
                  ),
                ),
                SizedBox(
                  width: 105,
                  child: TextField(
                    controller: _lonCtrl,
                    keyboardType: const TextInputType.numberWithOptions(signed: true, decimal: true),
                    decoration: const InputDecoration(
                      labelText: 'Lon (°)',
                      border: OutlineInputBorder(),
                      isDense: true,
                    ),
                    onSubmitted: (_) => _applyCoords(),
                  ),
                ),
                OutlinedButton(
                  onPressed: _applyCoords,
                  child: const Text('Apply'),
                ),
              ],
            ),
            const SizedBox(height: 10),
            Row(
              children: [
                Text('Min Alt: ${minAlt.round()}°', style: const TextStyle(fontSize: 13)),
                Expanded(
                  child: Slider(
                    value: minAlt,
                    min: 15,
                    max: 60,
                    divisions: 9,
                    label: '${minAlt.round()}°',
                    onChanged: (v) {
                      backyardMinAltNotifier.value = v;
                      setState(() {});
                    },
                  ),
                ),
                FilterChip(
                  selected: _onlyReachable,
                  label: const Text('Reachable only'),
                  onSelected: (v) => setState(() => _onlyReachable = v),
                ),
              ],
            ),
            Text(
              '${scope.fovNote} · Privacy: location rounded to 0.1° (~10 km) and computed on-device.',
              style: TextStyle(fontSize: 11, color: secondary),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildNightSummaryCard(
    BuildContext context,
    NightWindowSummary night,
    int reachableCount,
    int totalCount,
    ScopePreset scope,
  ) {
    final primary = Theme.of(context).colorScheme.primary;
    String fmtHm(DateTime? dt) {
      if (dt == null) return '—';
      final u = dt.toUtc();
      return '${u.hour.toString().padLeft(2, '0')}:${u.minute.toString().padLeft(2, '0')}Z';
    }

    return Card(
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
        child: Wrap(
          spacing: 18,
          runSpacing: 8,
          crossAxisAlignment: WrapCrossAlignment.center,
          children: [
            Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                Icon(Icons.auto_awesome, size: 18, color: primary),
                const SizedBox(width: 6),
                Text(
                  '$reachableCount reachable for ${scope.shortLabel} ($totalCount ranked)',
                  style: TextStyle(fontWeight: FontWeight.bold, color: primary),
                ),
              ],
            ),
            Text(
              night.hasDarkSky
                  ? 'Dark sky: ${fmtHm(night.darkStartUtc)} – ${fmtHm(night.darkEndUtc)}'
                  : 'No full nautical night at this latitude tonight',
              style: const TextStyle(fontSize: 13),
            ),
            Text(
              'Moon: ${night.moonIllumPercent}% lit',
              style: const TextStyle(fontSize: 13),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildWeatherOutlookCard(BuildContext context) {
    final secondary = redNightModeNotifier.value
        ? SkyRedColors.textSecondary
        : SkyColors.textSecondary;
    final primary = Theme.of(context).colorScheme.primary;
    final weather = _weather;
    if (_weatherLoading && weather == null) {
      return const Card(
        child: Padding(
          padding: EdgeInsets.all(14),
          child: Row(
            children: [
              SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2)),
              SizedBox(width: 10),
              Text('Loading 7-night clear-sky & seeing forecast...'),
            ],
          ),
        ),
      );
    }
    if (weather == null || weather.nights.isEmpty) {
      return const SizedBox.shrink();
    }
    final tonight = weather.tonight!;
    final best = weather.bestNight;

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Expanded(
                  child: Text(
                    '7-Night Clear-Sky Forecast · ${tonight.verdict} (${tonight.clearSkyScore}/100)',
                    style: TextStyle(
                      fontSize: 15,
                      fontWeight: FontWeight.bold,
                      color: tonight.isClearNight ? primary : null,
                    ),
                  ),
                ),
                Text(
                  weather.sourceSummary,
                  style: TextStyle(fontSize: 11, color: secondary),
                ),
              ],
            ),
            const SizedBox(height: 6),
            Text(
              'Tonight clouds: Low ${tonight.cloudLowPct}% · Mid ${tonight.cloudMidPct}% · '
              'High ${tonight.cloudHighPct}% · Seeing: ${tonight.seeingLabel}'
              '${best != null ? ' · Best night: ${best.date.substring(5)} (${best.clearSkyScore}/100)' : ''}',
              style: TextStyle(fontSize: 12, color: secondary),
            ),
            const SizedBox(height: 10),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: weather.nights.map((n) {
                final isBest = best != null && n.date == best.date;
                return Container(
                  padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                  decoration: BoxDecoration(
                    borderRadius: BorderRadius.circular(8),
                    border: Border.all(
                      color: isBest
                          ? primary
                          : (redNightModeNotifier.value
                              ? SkyRedColors.borderSubtle
                              : SkyColors.borderSubtle),
                    ),
                    color: n.isClearNight ? primary.withValues(alpha: 0.1) : null,
                  ),
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          if (isBest) ...[
                            Icon(Icons.star, size: 12, color: primary),
                            const SizedBox(width: 3),
                          ],
                          Text(
                            n.date.length >= 10 ? n.date.substring(5) : n.date,
                            style: const TextStyle(fontSize: 11, fontWeight: FontWeight.bold),
                          ),
                        ],
                      ),
                      Text(
                        '${n.clearSkyScore}/100 · ${n.cloudTotalPct}% cld',
                        style: TextStyle(fontSize: 11, color: secondary),
                      ),
                    ],
                  ),
                );
              }).toList(),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildTargetCard(BuildContext context, PlannedTarget plan, double minAlt) {
    final obj = plan.object;
    final info = classInfo(obj.topClass);
    final isExpanded = _expandedArcId == obj.docId;
    final magStr = plan.effectiveMag != null
        ? '${plan.effectiveMag!.toStringAsFixed(1)} mag'
        : 'mag —';
    final primary = Theme.of(context).colorScheme.primary;
    final secondary = redNightModeNotifier.value
        ? SkyRedColors.textSecondary
        : SkyColors.textSecondary;

    return Card(
      margin: const EdgeInsets.only(bottom: 10),
      child: InkWell(
        borderRadius: BorderRadius.circular(12),
        onTap: () => context.push('/objects/${obj.survey}/${obj.oid}'),
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
                      color: (plan.reachable ? primary : secondary).withValues(alpha: 0.15),
                      borderRadius: BorderRadius.circular(6),
                    ),
                    child: Text(
                      plan.reachable ? 'REACHABLE · $magStr' : magStr,
                      style: TextStyle(
                        fontSize: 11,
                        fontWeight: FontWeight.bold,
                        color: plan.reachable ? primary : secondary,
                      ),
                    ),
                  ),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      obj.displayLabel,
                      style: const TextStyle(fontSize: 15, fontWeight: FontWeight.bold),
                      overflow: TextOverflow.ellipsis,
                    ),
                  ),
                  IconButton(
                    onPressed: () => _copyCoords(obj),
                    tooltip: 'Copy J2000 RA/Dec for Seestar / ASIAIR / N.I.N.A.',
                    icon: const Icon(Icons.copy, size: 18),
                    visualDensity: VisualDensity.compact,
                  ),
                  IconButton(
                    onPressed: () => setState(() {
                      _expandedArcId = isExpanded ? null : obj.docId;
                    }),
                    tooltip: isExpanded ? 'Hide Tonight\'s Arc' : 'Show Tonight\'s Arc',
                    icon: Icon(
                      isExpanded ? Icons.expand_less : Icons.show_chart,
                      size: 20,
                    ),
                    visualDensity: VisualDensity.compact,
                  ),
                ],
              ),
              const SizedBox(height: 4),
              Text(
                '${info.label} · ${obj.survey.toUpperCase()} · ${plan.statusLine}',
                style: TextStyle(
                  fontSize: 13,
                  color: plan.reachable ? null : secondary,
                ),
              ),
              const SizedBox(height: 4),
              Text(
                'RA ${formatRaColon(obj.meanRa)} · Dec ${formatDecColon(obj.meanDec)} · Moon ${plan.moonSepDeg.round()}°',
                style: TextStyle(fontSize: 12, color: secondary),
              ),
              if (isExpanded) ...[
                const SizedBox(height: 12),
                TonightArcChart(plan: plan, minAltDeg: minAlt, height: 140),
              ],
            ],
          ),
        ),
      ),
    );
  }
}
