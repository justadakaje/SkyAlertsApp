import '../data/json_http.dart';
import 'backyard_planner.dart';

class NightWeatherForecast {
  const NightWeatherForecast({
    required this.date,
    required this.cloudTotalPct,
    required this.cloudLowPct,
    required this.cloudMidPct,
    required this.cloudHighPct,
    required this.seeingIndex,
    required this.seeingLabel,
    required this.clearSkyScore,
    required this.verdict,
  });

  final String date;
  final int cloudTotalPct;
  final int cloudLowPct;
  final int cloudMidPct;
  final int cloudHighPct;
  final int seeingIndex;
  final String seeingLabel;
  final int clearSkyScore;
  final String verdict;

  bool get isClearNight => clearSkyScore >= 65;
}

class SevenNightOutlook {
  const SevenNightOutlook({
    required this.nights,
    required this.bestNight,
    required this.sourceSummary,
  });

  final List<NightWeatherForecast> nights;
  final NightWeatherForecast? bestNight;
  final String sourceSummary;

  NightWeatherForecast? get tonight => nights.isNotEmpty ? nights.first : null;
}

Uri buildOpenMeteoUri(double latDeg, double lonDeg) {
  final lat = ((latDeg * 10.0).round() / 10.0).toStringAsFixed(1);
  final lon = ((lonDeg * 10.0).round() / 10.0).toStringAsFixed(1);
  return Uri.parse(
    'https://api.open-meteo.com/v1/forecast'
    '?latitude=$lat&longitude=$lon'
    '&hourly=cloud_cover,cloud_cover_low,cloud_cover_mid,cloud_cover_high'
    '&forecast_days=7&timezone=auto',
  );
}

Uri buildSevenTimerUri(double latDeg, double lonDeg) {
  final lat = ((latDeg * 10.0).round() / 10.0).toStringAsFixed(1);
  final lon = ((lonDeg * 10.0).round() / 10.0).toStringAsFixed(1);
  return Uri.parse(
    'https://www.7timer.info/bin/astro.php'
    '?lon=$lon&lat=$lat&ac=0&unit=metric&output=json&tzshift=0',
  );
}

String seeingLabelForIndex(int seeingIndex) {
  if (seeingIndex <= 2) return 'Excellent (<0.8″)';
  if (seeingIndex <= 4) return 'Good (~1.2″)';
  if (seeingIndex <= 6) return 'Fair (~1.8″)';
  return 'Poor (>2.2″)';
}

String _verdictForScore(int score) {
  if (score >= 75) return 'Go Image (Clear)';
  if (score >= 45) return 'Patchy Clouds';
  return 'Clouded Out';
}

int _meanRounded(List<num> values) {
  if (values.isEmpty) return 0;
  final sum = values.fold<double>(0.0, (a, b) => a + b.toDouble());
  return (sum / values.length).round().clamp(0, 100);
}

SevenNightOutlook parseAstroWeather({
  required Map<String, dynamic> openMeteoJson,
  Map<String, dynamic>? sevenTimerJson,
}) {
  final hourly = openMeteoJson['hourly'];
  if (hourly is! Map) {
    return const SevenNightOutlook(
      nights: [],
      bestNight: null,
      sourceSummary: 'Open-Meteo unavailable',
    );
  }

  final times = (hourly['time'] as List?)?.cast<String>() ?? const [];
  final totalList = (hourly['cloud_cover'] as List?) ?? const [];
  final lowList = (hourly['cloud_cover_low'] as List?) ?? const [];
  final midList = (hourly['cloud_cover_mid'] as List?) ?? const [];
  final highList = (hourly['cloud_cover_high'] as List?) ?? const [];

  final sevenSeries = sevenTimerJson?['dataseries'] as List?;
  final sevenSeeings = <int>[];
  if (sevenSeries != null) {
    for (final entry in sevenSeries) {
      if (entry is Map && entry['seeing'] is num) {
        sevenSeeings.add((entry['seeing'] as num).toInt().clamp(1, 8));
      }
    }
  }

  final allByDate = <String, List<int>>{};
  final nightByDate = <String, List<int>>{};

  for (var i = 0; i < times.length; i++) {
    final t = times[i];
    if (t.length < 13) continue;
    final date = t.substring(0, 10);
    final hour = int.tryParse(t.substring(11, 13)) ?? 12;
    allByDate.putIfAbsent(date, () => []).add(i);
    if (hour >= 20 || hour <= 4) {
      nightByDate.putIfAbsent(date, () => []).add(i);
    }
  }

  final dates = allByDate.keys.toList()..sort();
  final nights = <NightWeatherForecast>[];

  for (var dIdx = 0; dIdx < dates.length && nights.length < 7; dIdx++) {
    final date = dates[dIdx];
    final indices = (nightByDate[date]?.isNotEmpty ?? false)
        ? nightByDate[date]!
        : allByDate[date]!;

    final tot = <num>[];
    final low = <num>[];
    final mid = <num>[];
    final high = <num>[];
    for (final idx in indices) {
      if (idx < totalList.length && totalList[idx] is num) {
        tot.add(totalList[idx] as num);
      }
      if (idx < lowList.length && lowList[idx] is num) {
        low.add(lowList[idx] as num);
      }
      if (idx < midList.length && midList[idx] is num) {
        mid.add(midList[idx] as num);
      }
      if (idx < highList.length && highList[idx] is num) {
        high.add(highList[idx] as num);
      }
    }

    final cTot = _meanRounded(tot);
    final cLow = low.isNotEmpty ? _meanRounded(low) : cTot;
    final cMid = mid.isNotEmpty ? _meanRounded(mid) : cTot;
    final cHigh = high.isNotEmpty ? _meanRounded(high) : 0;

    final int seeingIdx;
    if (sevenSeeings.isNotEmpty) {
      final sliceStart = (dIdx * 4).clamp(0, sevenSeeings.length - 1);
      final sliceEnd = ((dIdx + 1) * 4).clamp(sliceStart + 1, sevenSeeings.length);
      final slice = sevenSeeings.sublist(sliceStart, sliceEnd);
      seeingIdx = (slice.reduce((a, b) => a + b) / slice.length).round().clamp(1, 8);
    } else {
      seeingIdx = cTot <= 25 ? 2 : (cTot <= 60 ? 4 : 6);
    }

    final cloudPenalty = 0.50 * cLow + 0.35 * cMid + 0.15 * cHigh;
    final seeingPenalty = ((seeingIdx - 1) / 7.0) * 15.0;
    final score = (100.0 - cloudPenalty - seeingPenalty).round().clamp(0, 100);

    nights.add(
      NightWeatherForecast(
        date: date,
        cloudTotalPct: cTot,
        cloudLowPct: cLow,
        cloudMidPct: cMid,
        cloudHighPct: cHigh,
        seeingIndex: seeingIdx,
        seeingLabel: seeingLabelForIndex(seeingIdx),
        clearSkyScore: score,
        verdict: _verdictForScore(score),
      ),
    );
  }

  NightWeatherForecast? best;
  for (final n in nights) {
    if (best == null || n.clearSkyScore > best.clearSkyScore) {
      best = n;
    }
  }

  final has7T = sevenSeeings.isNotEmpty;
  return SevenNightOutlook(
    nights: nights,
    bestNight: best,
    sourceSummary: has7T ? 'Open-Meteo + 7Timer! ASTRO' : 'Open-Meteo Cloud Layers',
  );
}

Future<SevenNightOutlook> fetchSevenNightOutlook(
  ObservatoryLocation loc, {
  Future<Map<String, dynamic>> Function(Uri uri)? httpGet,
}) async {
  final getter = httpGet ?? fetchJsonMap;
  final rounded = loc.roundedToTenth;
  final meteoUri = buildOpenMeteoUri(rounded.latitudeDeg, rounded.longitudeDeg);
  final sevenUri = buildSevenTimerUri(rounded.latitudeDeg, rounded.longitudeDeg);

  final meteoFuture = getter(meteoUri);
  final sevenFuture = getter(sevenUri).then<Map<String, dynamic>?>(
    (v) => v,
    onError: (_, __) => null,
  );

  final results = await Future.wait([meteoFuture, sevenFuture]);
  return parseAstroWeather(
    openMeteoJson: results[0]!,
    sevenTimerJson: results[1],
  );
}
