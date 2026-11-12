import 'package:flutter/material.dart';

import '../data/firestore_repository.dart';
import '../domain/format.dart';
import '../domain/trends.dart';
import 'theme.dart';

class TrendsScreen extends StatefulWidget {
  const TrendsScreen({super.key, required this.repository});

  final SkyAlertsRepository repository;

  @override
  State<TrendsScreen> createState() => _TrendsScreenState();
}

class _TrendsScreenState extends State<TrendsScreen> {
  TrendsRollup? _trends;
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() => _loading = true);
    final t = await widget.repository.fetchTrends();
    if (!mounted) return;
    setState(() {
      _trends = t;
      _loading = false;
    });
  }

  @override
  Widget build(BuildContext context) {
    final trends = _trends;
    return Scaffold(
      appBar: AppBar(title: const Text('Trends · 90-Day Sky Activity & Survey Blend')),
      body: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 1120),
          child: _loading || trends == null
              ? const Center(child: CircularProgressIndicator())
              : ListView(
                  padding: const EdgeInsets.all(16),
                  children: [
                    Wrap(
                      spacing: 16,
                      runSpacing: 16,
                      children: [
                        _MetricTile(
                          label: 'New Objects (7d)',
                          value: formatCount(trends.newThisWeek),
                          delta: formatChange(trends.newThisWeek, trends.newLastWeek),
                        ),
                        _MetricTile(
                          label: 'Cosmic Explosions (7d)',
                          value: formatCount(trends.transientsThisWeek),
                          delta: formatChange(
                            trends.transientsThisWeek,
                            trends.transientsLastWeek,
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 24),
                    Card(
                      child: Padding(
                        padding: const EdgeInsets.all(16),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            const Text(
                              '12-Week Survey Blend: Rubin Observatory (LSST) vs. ZTF',
                              style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
                            ),
                            const SizedBox(height: 6),
                            const Text(
                              'Weekly share of newly ingested astronomical objects by survey stream.',
                              style: TextStyle(fontSize: 13, color: SkyColors.textSecondary),
                            ),
                            const SizedBox(height: 16),
                            ...weeklySurveyMix(
                              trends.dailySurveyCounts,
                              todayMjd: trends.todayMjd,
                            ).map(
                              (bin) => Padding(
                                padding: const EdgeInsets.only(bottom: 8),
                                child: Row(
                                  children: [
                                    SizedBox(
                                      width: 96,
                                      child: Text(
                                        'MJD ${bin.startMjd}',
                                        style: const TextStyle(
                                          fontSize: 11,
                                          color: SkyColors.textSecondary,
                                        ),
                                      ),
                                    ),
                                    Expanded(
                                      child: ClipRRect(
                                        borderRadius: BorderRadius.circular(4),
                                        child: SizedBox(
                                          height: 16,
                                          child: Row(
                                            children: [
                                              Expanded(
                                                flex: (bin.rubinShare * 1000).round().clamp(1, 1000),
                                                child: Container(color: const Color(0xFF38BDF8)),
                                              ),
                                              Expanded(
                                                flex: (bin.ztfShare * 1000).round().clamp(1, 1000),
                                                child: Container(color: SkyColors.accentAmber),
                                              ),
                                            ],
                                          ),
                                        ),
                                      ),
                                    ),
                                    const SizedBox(width: 12),
                                    SizedBox(
                                      width: 130,
                                      child: Text(
                                        'Rubin ${bin.rubinCount} · ZTF ${bin.ztfCount}',
                                        style: const TextStyle(fontSize: 11),
                                      ),
                                    ),
                                  ],
                                ),
                              ),
                            ),
                          ],
                        ),
                      ),
                    ),
                    const SizedBox(height: 16),
                    ...dailyGroupSeries(trends.dailyCounts, todayMjd: trends.todayMjd)
                        .entries
                        .map((entry) {
                      final total90d = entry.value.fold<int>(0, (a, b) => a + b);
                      return Card(
                        margin: const EdgeInsets.only(bottom: 12),
                        child: ListTile(
                          title: Text(
                            entry.key.label,
                            style: TextStyle(
                              fontWeight: FontWeight.bold,
                              color: SkyColors.forGroup(entry.key),
                            ),
                          ),
                          subtitle: Text('90-day discoveries: ${formatCount(total90d)}'),
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

class _MetricTile extends StatelessWidget {
  const _MetricTile({required this.label, required this.value, required this.delta});

  final String label;
  final String value;
  final String delta;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: 260,
      child: Card(
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(label, style: const TextStyle(fontSize: 12, color: SkyColors.textSecondary)),
              const SizedBox(height: 6),
              Text(value, style: const TextStyle(fontSize: 26, fontWeight: FontWeight.bold)),
              const SizedBox(height: 4),
              Text(delta, style: const TextStyle(fontSize: 12, color: SkyColors.accentAmber)),
            ],
          ),
        ),
      ),
    );
  }
}
