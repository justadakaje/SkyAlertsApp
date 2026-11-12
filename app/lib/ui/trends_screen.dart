import 'dart:math' as math;

import 'package:flutter/material.dart';

import '../data/firestore_repository.dart';
import '../domain/classes.dart';
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
      appBar: AppBar(
        title: const Text('Trends · 90-Day Sky Activity & Survey Blend'),
        actions: [
          IconButton(
            onPressed: _load,
            icon: const Icon(Icons.refresh),
            tooltip: 'Refresh trends',
          ),
        ],
      ),
      body: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 1120),
          child: _loading || trends == null
              ? const Center(child: CircularProgressIndicator())
              : RefreshIndicator(
                  onRefresh: _load,
                  child: ListView(
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
                      const SizedBox(height: 20),
                      Card(
                        child: Padding(
                          padding: const EdgeInsets.all(16),
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              const Text(
                                '90-Day Daily Discovery Timeline by Category',
                                style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
                              ),
                              const SizedBox(height: 4),
                              const Text(
                                'Daily newly discovered objects stacked by astronomical category across the past 90 days.',
                                style: TextStyle(fontSize: 12, color: SkyColors.textSecondary),
                              ),
                              const SizedBox(height: 10),
                              Wrap(
                                spacing: 14,
                                runSpacing: 6,
                                children: [
                                  ClassGroup.transients,
                                  ClassGroup.variables,
                                  ClassGroup.agn,
                                  ClassGroup.solar,
                                ].map((g) {
                                  final c = SkyColors.forGroup(g);
                                  return Row(
                                    mainAxisSize: MainAxisSize.min,
                                    children: [
                                      Container(
                                        width: 10,
                                        height: 10,
                                        decoration: BoxDecoration(
                                          color: c,
                                          borderRadius: BorderRadius.circular(2),
                                        ),
                                      ),
                                      const SizedBox(width: 5),
                                      Text(
                                        g.label,
                                        style: const TextStyle(
                                          fontSize: 11,
                                          color: SkyColors.textSecondary,
                                        ),
                                      ),
                                    ],
                                  );
                                }).toList(),
                              ),
                              const SizedBox(height: 14),
                              SizedBox(
                                height: 180,
                                width: double.infinity,
                                child: CustomPaint(
                                  painter: _DailyStackedChartPainter(
                                    series: dailyGroupSeries(
                                      trends.dailyCounts,
                                      todayMjd: trends.todayMjd,
                                    ),
                                    todayMjd: trends.todayMjd,
                                  ),
                                ),
                              ),
                            ],
                          ),
                        ),
                      ),
                      const SizedBox(height: 20),
                      Card(
                        child: Padding(
                          padding: const EdgeInsets.all(16),
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Row(
                                children: [
                                  const Expanded(
                                    child: Text(
                                      '12-Week Survey Blend: Rubin Observatory (LSST) vs. ZTF',
                                      style: TextStyle(
                                        fontSize: 16,
                                        fontWeight: FontWeight.bold,
                                      ),
                                    ),
                                  ),
                                  Container(
                                    width: 10,
                                    height: 10,
                                    color: const Color(0xFF38BDF8),
                                  ),
                                  const SizedBox(width: 4),
                                  const Text('Rubin', style: TextStyle(fontSize: 11)),
                                  const SizedBox(width: 10),
                                  Container(
                                    width: 10,
                                    height: 10,
                                    color: SkyColors.accentAmber,
                                  ),
                                  const SizedBox(width: 4),
                                  const Text('ZTF', style: TextStyle(fontSize: 11)),
                                ],
                              ),
                              const SizedBox(height: 6),
                              const Text(
                                'Weekly share of newly discovered astronomical objects by survey stream.',
                                style: TextStyle(fontSize: 13, color: SkyColors.textSecondary),
                              ),
                              const SizedBox(height: 16),
                              ...weeklySurveyMix(
                                trends.dailySurveyCounts,
                                todayMjd: trends.todayMjd,
                              ).map(
                                (bin) => Padding(
                                  padding: const EdgeInsets.only(bottom: 9),
                                  child: Row(
                                    children: [
                                      SizedBox(
                                        width: 108,
                                        child: Text(
                                          '${formatShortDate(bin.startMjd)}–${formatShortDate(bin.endMjd)}',
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
                                            child: bin.total == 0
                                                ? Container(color: SkyColors.bgElevated)
                                                : Row(
                                                    children: [
                                                      if (bin.rubinCount > 0)
                                                        Expanded(
                                                          flex: bin.rubinCount,
                                                          child: Container(
                                                            color: const Color(0xFF38BDF8),
                                                          ),
                                                        ),
                                                      if (bin.ztfCount > 0)
                                                        Expanded(
                                                          flex: bin.ztfCount,
                                                          child: Container(
                                                            color: SkyColors.accentAmber,
                                                          ),
                                                        ),
                                                    ],
                                                  ),
                                          ),
                                        ),
                                      ),
                                      const SizedBox(width: 12),
                                      SizedBox(
                                        width: 140,
                                        child: Text(
                                          'Rubin ${formatCount(bin.rubinCount)} · ZTF ${formatCount(bin.ztfCount)}',
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
                        final last7d = entry.value.length >= 7
                            ? entry.value.sublist(entry.value.length - 7).fold<int>(0, (a, b) => a + b)
                            : total90d;
                        final grpColor = SkyColors.forGroup(entry.key);
                        return Card(
                          margin: const EdgeInsets.only(bottom: 12),
                          child: Padding(
                            padding: const EdgeInsets.all(14),
                            child: Row(
                              children: [
                                Expanded(
                                  child: Column(
                                    crossAxisAlignment: CrossAxisAlignment.start,
                                    children: [
                                      Text(
                                        entry.key.label,
                                        style: TextStyle(
                                          fontSize: 15,
                                          fontWeight: FontWeight.bold,
                                          color: grpColor,
                                        ),
                                      ),
                                      const SizedBox(height: 4),
                                      Text(
                                        '90-day discoveries: ${formatCount(total90d)} · '
                                        'Last 7 days: ${formatCount(last7d)}',
                                        style: const TextStyle(
                                          fontSize: 12,
                                          color: SkyColors.textSecondary,
                                        ),
                                      ),
                                    ],
                                  ),
                                ),
                                SizedBox(
                                  width: 120,
                                  height: 36,
                                  child: CustomPaint(
                                    painter: _MiniSparklinePainter(
                                      values: entry.value,
                                      color: grpColor,
                                    ),
                                  ),
                                ),
                              ],
                            ),
                          ),
                        );
                      }),
                    ],
                  ),
                ),
        ),
      ),
    );
  }
}

class _DailyStackedChartPainter extends CustomPainter {
  const _DailyStackedChartPainter({required this.series, required this.todayMjd});

  final Map<ClassGroup, List<int>> series;
  final int todayMjd;

  @override
  void paint(Canvas canvas, Size size) {
    const days = 90;
    const padBottom = 20.0;
    final plotH = math.max(1.0, size.height - padBottom);
    final groups = [
      ClassGroup.transients,
      ClassGroup.variables,
      ClassGroup.agn,
      ClassGroup.solar,
    ];

    var maxDayTotal = 1;
    for (var i = 0; i < days; i++) {
      var daySum = 0;
      for (final g in groups) {
        final list = series[g];
        if (list != null && i < list.length) daySum += list[i];
      }
      if (daySum > maxDayTotal) maxDayTotal = daySum;
    }

    final barW = size.width / days;
    for (var i = 0; i < days; i++) {
      var yBottom = plotH;
      for (final g in groups) {
        final val = series[g]?[i] ?? 0;
        if (val <= 0) continue;
        final h = (val / maxDayTotal) * (plotH - 8);
        final rect = Rect.fromLTWH(
          i * barW + 0.5,
          yBottom - h,
          math.max(1.5, barW - 1.0),
          h,
        );
        canvas.drawRect(rect, Paint()..color = SkyColors.forGroup(g));
        yBottom -= h;
      }
    }

    canvas.drawLine(
      Offset(0, plotH),
      Offset(size.width, plotH),
      Paint()..color = SkyColors.borderSubtle,
    );

    final startMjd = todayMjd - days + 1;
    for (final idx in const [0, 44, 89]) {
      final tp = TextPainter(
        text: TextSpan(
          text: formatShortDate(startMjd + idx),
          style: const TextStyle(fontSize: 10, color: SkyColors.textSecondary),
        ),
        textDirection: TextDirection.ltr,
      )..layout();
      final x = (idx / (days - 1)) * (size.width - tp.width);
      tp.paint(canvas, Offset(x, plotH + 4));
    }
  }

  @override
  bool shouldRepaint(covariant _DailyStackedChartPainter oldDelegate) =>
      oldDelegate.todayMjd != todayMjd || oldDelegate.series != series;
}

class _MiniSparklinePainter extends CustomPainter {
  const _MiniSparklinePainter({required this.values, required this.color});

  final List<int> values;
  final Color color;

  @override
  void paint(Canvas canvas, Size size) {
    if (values.isEmpty) return;
    final maxVal = values.fold<int>(1, (a, b) => math.max(a, b));
    final path = Path();
    for (var i = 0; i < values.length; i++) {
      final x = (i / math.max(1, values.length - 1)) * size.width;
      final y = size.height - (values[i] / maxVal) * (size.height - 4) - 2;
      if (i == 0) {
        path.moveTo(x, y);
      } else {
        path.lineTo(x, y);
      }
    }
    canvas.drawPath(
      path,
      Paint()
        ..color = color
        ..style = PaintingStyle.stroke
        ..strokeWidth = 1.6,
    );
  }

  @override
  bool shouldRepaint(covariant _MiniSparklinePainter oldDelegate) =>
      oldDelegate.values != values;
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
