import 'package:skyalerts_app/domain/astro_weather.dart';
import 'package:skyalerts_app/domain/backyard_planner.dart';
import 'package:test/test.dart';

void main() {
  group('astro_weather', () {
    test('filters to nighttime hours and ignores daytime clouds', () {
      final openMeteo = <String, dynamic>{
        'hourly': {
          'time': [
            '2026-11-13T12:00',
            '2026-11-13T22:00',
            '2026-11-13T23:00',
            '2026-11-14T12:00',
            '2026-11-14T22:00',
          ],
          'cloud_cover': [100, 10, 10, 20, 90],
          'cloud_cover_low': [100, 5, 5, 10, 85],
          'cloud_cover_mid': [100, 10, 10, 10, 80],
          'cloud_cover_high': [100, 15, 15, 0, 50],
        },
      };
      final sevenTimer = <String, dynamic>{
        'dataseries': [
          {'seeing': 2},
          {'seeing': 2},
          {'seeing': 2},
          {'seeing': 2},
          {'seeing': 6},
          {'seeing': 6},
          {'seeing': 6},
          {'seeing': 6},
        ],
      };

      final outlook = parseAstroWeather(
        openMeteoJson: openMeteo,
        sevenTimerJson: sevenTimer,
      );
      expect(outlook.nights.length, 2);
      final night1 = outlook.nights[0];
      final night2 = outlook.nights[1];

      expect(night1.date, '2026-11-13');
      expect(night1.cloudTotalPct, 10);
      expect(night1.clearSkyScore, greaterThanOrEqualTo(85));
      expect(night1.isClearNight, isTrue);
      expect(night1.verdict, 'Go Image (Clear)');

      expect(night2.date, '2026-11-14');
      expect(night2.cloudTotalPct, 90);
      expect(night2.clearSkyScore, lessThan(45));
      expect(outlook.bestNight?.date, '2026-11-13');
    });

    test('falls back gracefully when 7Timer! JSON is null', () {
      final openMeteo = <String, dynamic>{
        'hourly': {
          'time': ['2026-11-13T21:00', '2026-11-13T22:00'],
          'cloud_cover': [15, 25],
          'cloud_cover_low': [10, 10],
          'cloud_cover_mid': [15, 25],
          'cloud_cover_high': [20, 20],
        },
      };
      final outlook = parseAstroWeather(openMeteoJson: openMeteo, sevenTimerJson: null);
      expect(outlook.nights.length, 1);
      expect(outlook.nights.first.seeingIndex, 2);
      expect(outlook.sourceSummary, 'Open-Meteo Cloud Layers');
    });

    test('fetchSevenNightOutlook rounds coordinates to 0.1 deg and handles 7Timer error', () async {
      final seenUris = <Uri>[];
      final outlook = await fetchSevenNightOutlook(
        const ObservatoryLocation(latitudeDeg: 40.149, longitudeDeg: -75.162),
        httpGet: (uri) async {
          seenUris.add(uri);
          if (uri.host.contains('7timer')) {
            throw StateError('7Timer timeout');
          }
          return {
            'hourly': {
              'time': ['2026-11-13T22:00'],
              'cloud_cover': [12],
              'cloud_cover_low': [4],
              'cloud_cover_mid': [8],
              'cloud_cover_high': [10],
            },
          };
        },
      );
      expect(seenUris.length, 2);
      expect(seenUris[0].toString(), contains('latitude=40.1&longitude=-75.2'));
      expect(seenUris[1].toString(), contains('lon=-75.2&lat=40.1'));
      expect(outlook.tonight?.clearSkyScore, greaterThan(80));
    });
  });
}
