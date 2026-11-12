import 'classes.dart';

class DayClassCount {
  const DayClassCount({required this.day, required this.topClass, required this.n});

  factory DayClassCount.fromMap(Map<String, dynamic> map) {
    return DayClassCount(
      day: (map['day'] as num).toInt(),
      topClass: map['top_class'] as String?,
      n: (map['n'] as num).toInt(),
    );
  }

  final int day;
  final String? topClass;
  final int n;
}

class DaySurveyCount {
  const DaySurveyCount({required this.day, required this.survey, required this.n});

  factory DaySurveyCount.fromMap(Map<String, dynamic> map) {
    return DaySurveyCount(
      day: (map['day'] as num).toInt(),
      survey: (map['survey'] as String?) ?? 'ztf',
      n: (map['n'] as num).toInt(),
    );
  }

  final int day;
  final String survey;
  final int n;
}

class WeeklySurveyBin {
  const WeeklySurveyBin({
    required this.weekIndex,
    required this.startMjd,
    required this.endMjd,
    required this.rubinCount,
    required this.ztfCount,
  });

  final int weekIndex;
  final int startMjd;
  final int endMjd;
  final int rubinCount;
  final int ztfCount;

  int get total => rubinCount + ztfCount;
  double get rubinShare => total > 0 ? rubinCount / total : 0.0;
  double get ztfShare => total > 0 ? ztfCount / total : 0.0;
}

/// Computes 12 weekly bins of Rubin (LSST) vs ZTF survey counts ending at `todayMjd`.
List<WeeklySurveyBin> weeklySurveyMix(
  List<DaySurveyCount> rows, {
  required int todayMjd,
  int weeks = 12,
}) {
  final bins = <WeeklySurveyBin>[];
  for (var w = weeks - 1; w >= 0; w--) {
    final endDay = todayMjd - w * 7;
    final startDay = endDay - 6;
    var rubin = 0;
    var ztf = 0;
    for (final r in rows) {
      if (r.day >= startDay && r.day <= endDay) {
        if (r.survey == 'lsst' || r.survey == 'rubin') {
          rubin += r.n;
        } else {
          ztf += r.n;
        }
      }
    }
    bins.add(
      WeeklySurveyBin(
        weekIndex: weeks - 1 - w,
        startMjd: startDay,
        endMjd: endDay,
        rubinCount: rubin,
        ztfCount: ztf,
      ),
    );
  }
  return bins;
}

/// Computes daily totals per `ClassGroup` across `[todayMjd - days + 1 .. todayMjd]`.
Map<ClassGroup, List<int>> dailyGroupSeries(
  List<DayClassCount> rows, {
  required int todayMjd,
  int days = 90,
}) {
  final startDay = todayMjd - days + 1;
  final out = <ClassGroup, List<int>>{
    for (final g in ClassGroup.values)
      if (g != ClassGroup.other) g: List<int>.filled(days, 0),
  };
  for (final r in rows) {
    final idx = r.day - startDay;
    if (idx < 0 || idx >= days) continue;
    final grp = groupOf(r.topClass);
    final list = out[grp];
    if (list != null) {
      list[idx] += r.n;
    }
  }
  return out;
}

String formatChange(int current, int previous) {
  if (previous <= 0) {
    return current > 0 ? '+$current vs prior week' : 'No change vs prior week';
  }
  final pct = (((current - previous) / previous) * 100.0).round();
  if (pct == 0) return 'Flat vs prior week';
  return pct > 0 ? '+$pct% vs prior week' : '$pct% vs prior week';
}
