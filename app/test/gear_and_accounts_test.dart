import 'package:flutter_test/flutter_test.dart';
import 'package:skyalerts_app/data/firestore_repository.dart';
import 'package:skyalerts_app/domain/gear_affiliate.dart';

void main() {
  group('recommendGearForMagnitude', () {
    test('recommends binoculars and Seestar S30 for bright targets <= 10.5 mag', () {
      final recs = recommendGearForMagnitude(8.2);
      expect(recs, hasLength(2));
      expect(recs[0].id, 'celestron_10x50');
      expect(recs[1].id, 'zwo_seestar_s30');
    });

    test('recommends Seestar S50 and DWARF 3 for backyard targets 10.5-16.5 mag', () {
      final recs = recommendGearForMagnitude(14.8);
      expect(recs, hasLength(2));
      expect(recs.any((r) => r.id == 'zwo_seestar_s50'), isTrue);
      expect(recs.any((r) => r.id == 'dwarflab_dwarf_3'), isTrue);
    });

    test('recommends deeper aperture for >16.5 mag or unknown magnitude', () {
      final faint = recommendGearForMagnitude(18.9);
      expect(faint.any((r) => r.id == 'unistellar_odyssey'), isTrue);
      expect(faint.any((r) => r.id == '8in_f4_astrograph'), isTrue);

      final unknown = recommendGearForMagnitude(null);
      expect(unknown.map((r) => r.id), equals(faint.map((r) => r.id)));
    });

    test('provides FTC disclosure text', () {
      expect(ftcAffiliateDisclosure, contains('Amazon Associate'));
    });
  });

  group('UserAlertPreferences', () {
    test('round-trips Firestore topics map', () {
      const prefs = UserAlertPreferences(
        notifyTransients: true,
        notifySolarMatched: false,
        notifyWeeklyDispatch: true,
        minConfidence: 0.9,
      );

      final map = prefs.toMap();
      expect(map['topics'], {
        'transients': true,
        'solar_matched': false,
        'weekly_dispatch': true,
      });

      final parsed = UserAlertPreferences.fromMap({
        ...map,
        'min_confidence': 0.9,
      });
      expect(parsed.notifyTransients, isTrue);
      expect(parsed.notifySolarMatched, isFalse);
      expect(parsed.notifyWeeklyDispatch, isTrue);
      expect(parsed.minConfidence, closeTo(0.9, 1e-6));
    });
  });
}
