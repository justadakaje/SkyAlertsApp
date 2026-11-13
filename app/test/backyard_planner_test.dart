import 'package:skyalerts_app/data/firestore_repository.dart';
import 'package:skyalerts_app/domain/backyard_planner.dart';
import 'package:test/test.dart';

void main() {
  group('equatorialToHorizontal', () {
    test('puts target near zenith when RA equals LST and Dec equals latitude', () {
      final utc = DateTime.utc(2026, 6, 15, 4, 0);
      final lst = lstDeg(utc, -75.0);
      final horiz = equatorialToHorizontal(
        raDeg: lst,
        decDeg: 40.0,
        latitudeDeg: 40.0,
        longitudeDeg: -75.0,
        utc: utc,
      );
      expect(horiz.altDeg, closeTo(90.0, 0.01));
      expect(horiz.airmass, closeTo(1.0, 0.01));
    });

    test('puts far-southern target below horizon from 40N', () {
      final utc = DateTime.utc(2026, 11, 13, 4, 0);
      final horiz = equatorialToHorizontal(
        raDeg: 180.0,
        decDeg: -70.0,
        latitudeDeg: 40.0,
        longitudeDeg: -75.0,
        utc: utc,
      );
      expect(horiz.altDeg, lessThan(0.0));
      expect(horiz.airmass, isNull);
    });
  });

  group('angularSeparationDeg', () {
    test('returns 0 for identical coordinates and 90 for orthogonal', () {
      expect(angularSeparationDeg(120.0, 25.0, 120.0, 25.0), closeTo(0.0, 1e-6));
      expect(angularSeparationDeg(0.0, 0.0, 90.0, 0.0), closeTo(90.0, 1e-6));
      expect(angularSeparationDeg(0.0, 0.0, 0.0, 90.0), closeTo(90.0, 1e-6));
    });
  });

  group('sun and moon ephemerides', () {
    test('produce valid coordinates and illumination in [0, 1]', () {
      final utc = DateTime.utc(2026, 11, 13, 5, 0);
      final sun = sunEquatorial(utc);
      final moon = moonEquatorialAndPhase(utc);
      expect(sun.raDeg, inInclusiveRange(0.0, 360.0));
      expect(sun.decDeg, inInclusiveRange(-24.0, 24.0));
      expect(moon.raDeg, inInclusiveRange(0.0, 360.0));
      expect(moon.decDeg, inInclusiveRange(-30.0, 30.0));
      expect(moon.illumFraction, inInclusiveRange(0.0, 1.0));
    });
  });

  group('ObservatoryLocation & coordinate formatting', () {
    test('rounds to 0.1 degree for privacy', () {
      const loc = ObservatoryLocation(latitudeDeg: 40.14, longitudeDeg: -75.16);
      final rounded = loc.roundedToTenth;
      expect(rounded.latitudeDeg, closeTo(40.1, 1e-9));
      expect(rounded.longitudeDeg, closeTo(-75.2, 1e-9));
    });

    test('formats Seestar/ASIAIR/NINA RA and Dec colon strings', () {
      expect(formatRaColon(180.0), '12:00:00.0');
      expect(formatDecColon(-23.5), '-23:30:00');
      expect(formatDecColon(45.25), '+45:15:00');
    });
  });

  group('rankBackyardTargets', () {
    test('ranks reachable bright northern target above faint or far-southern target', () {
      const loc = ObservatoryLocation(latitudeDeg: 40.0, longitudeDeg: -75.0);
      final now = DateTime.utc(2026, 11, 13, 2, 0);
      // Pick RA near midnight LST so target transits high in the dark sky.
      final midLst = lstDeg(DateTime.utc(2026, 11, 13, 5, 0), loc.longitudeDeg);

      final brightVisible = CatalogObject(
        survey: 'bright_sn',
        oid: 'SN2026abc',
        displayName: 'SN 2026abc',
        meanRa: midLst,
        meanDec: 35.0,
        latestMag: 13.5,
      );
      final tooFaint = CatalogObject(
        survey: 'ztf',
        oid: 'ZTF26faint',
        meanRa: midLst,
        meanDec: 35.0,
        latestMag: 20.1,
      );
      final farSouth = CatalogObject(
        survey: 'bright_var',
        oid: 'VarSouth',
        meanRa: midLst,
        meanDec: -75.0,
        latestMag: 6.0,
      );

      final ranked = rankBackyardTargets(
        [farSouth, tooFaint, brightVisible],
        loc,
        ScopePreset.seestarS50,
        nowUtc: now,
      );
      expect(ranked.length, 3);
      expect(ranked.first.object.oid, 'SN2026abc');
      expect(ranked.first.reachable, isTrue);
      expect(ranked.first.windowMinutes, greaterThan(60));
      expect(ranked.any((t) => t.object.oid == 'ZTF26faint' && !t.reachable), isTrue);
      expect(ranked.any((t) => t.object.oid == 'VarSouth' && !t.visibleTonight), isTrue);

      final csv = exportPlannedTargetsCsv([ranked.first]);
      expect(csv, contains('SN 2026abc,bright_sn,SN2026abc'));
    });
  });
}
