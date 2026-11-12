import 'package:skyalerts_app/domain/astro.dart';
import 'package:skyalerts_app/domain/classes.dart';
import 'package:skyalerts_app/domain/format.dart';
import 'package:skyalerts_app/domain/lightcurve.dart';
import 'package:skyalerts_app/domain/solar.dart';
import 'package:skyalerts_app/domain/trends.dart';
import 'package:test/test.dart';

void main() {
  group('astro', () {
    test('mjdToDate and dateToMjd round-trip', () {
      final dt = DateTime.utc(2026, 11, 11, 0, 0, 0);
      final mjd = dateToMjd(dt);
      expect(mjdToDate(mjd), equals(dt));
    });

    test('formatRa and formatDec format J2000 coordinates cleanly', () {
      expect(formatRa(180.0), equals('12h 00m 00.0s'));
      expect(formatDec(-22.5), equals('−22° 30′ 00″'));
    });

    test('skyRegion identifies galactic plane and ~40°N hemisphere notes', () {
      final note = skyRegion(180.0, 60.0);
      expect(note, isNotNull);
      expect(note, contains('circumpolar from ~40°N'));
    });
  });

  group('classes & format', () {
    test('classInfo maps SNIa to transients group', () {
      final info = classInfo('SNIa');
      expect(info.group, equals(ClassGroup.transients));
      expect(info.label, contains('Type Ia Supernova'));
    });

    test('humanBrightness explains naked-eye vs research telescope magnitudes', () {
      expect(humanBrightness(5.2, band: 'V'), contains('naked eye'));
      expect(humanBrightness(18.5, band: 'r'), contains('fainter than the naked-eye limit'));
    });

    test('pickHomeHighlights selects explosion, active, and solar cards without duplicates', () {
      final cards = pickHomeHighlights([
        {
          'survey': 'ztf',
          'oid': 'ZTF26expl001',
          'top_class': 'SNIa',
          'top_probability': 0.94,
          'ndet': 6,
          'lastmjd': 61354.0,
        },
        {
          'survey': 'lsst',
          'oid': 'LSST26act001',
          'top_class': 'CEP',
          'top_probability': 0.88,
          'ndet': 42,
          'lastmjd': 61354.5,
        },
        {
          'survey': 'ztf',
          'oid': 'ZTF26sol001',
          'top_class': 'asteroid',
          'top_probability': 0.97,
          'ndet': 4,
          'lastmjd': 61354.2,
          'sso': {
            'status': 'matched',
            'sso_name': 'Nolan',
            'sso_number': 9537,
          },
        },
      ]);
      expect(cards.length, equals(3));
      expect(cards[0].kind, equals('explosion'));
      expect(cards[1].kind, equals('active'));
      expect(cards[2].kind, equals('solar'));
      expect(cards[2].headline, contains('(9537) Nolan'));
    });
  });

  group('lightcurve & ZTF stamps', () {
    test('DetectionPoint computes AB mag from positive Rubin fluxNjy', () {
      const pt = DetectionPoint(
        measurementId: 'm1',
        mjd: 61354.0,
        band: 'r',
        fluxNjy: 1000000.0,
      );
      expect(pt.effectiveAbMag, closeTo(16.4, 0.01));
    });

    test('buildZtfStamps validates ZTF oid and candid format', () {
      final stamps = buildZtfStamps('ztf', 'ZTF26aaabbbc', const [
        DetectionPoint(
          measurementId: '1234567890123',
          mjd: 61354.0,
          band: 'g',
          candid: '1234567890123',
          hasStamp: true,
        ),
      ]);
      expect(stamps, isNotNull);
      expect(stamps!.scienceUrl, contains('type=science'));
    });
  });

  group('solar & trends', () {
    test('formatSsoLabel and jplSbdbUrl format minor planet identifiers', () {
      expect(formatSsoLabel(9537, 'Nolan'), equals('(9537) Nolan'));
      expect(jplSbdbUrl(9537, 'Nolan'), contains('sstr=9537'));
    });

    test('weeklySurveyMix aggregates 12 weeks of Rubin vs ZTF counts', () {
      final bins = weeklySurveyMix(
        const [
          DaySurveyCount(day: 61354, survey: 'lsst', n: 30),
          DaySurveyCount(day: 61354, survey: 'ztf', n: 20),
        ],
        todayMjd: 61355,
      );
      expect(bins.length, equals(12));
      expect(bins.last.rubinCount, equals(30));
      expect(bins.last.ztfCount, equals(20));
      expect(bins.last.rubinShare, closeTo(0.6, 0.001));
    });
  });
}
