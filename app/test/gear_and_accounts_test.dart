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

  group('mergeAndSortCatalogFeed', () {
    test('orders by tier, probability desc, then lastMjd desc when newestFirst is false', () {
      const a = CatalogObject(
        survey: 'ztf',
        oid: 'ZTF26sn',
        tier: 0,
        topProbability: 0.92,
        lastMjd: 61354.0,
      );
      const b = CatalogObject(
        survey: 'lsst',
        oid: '170001',
        tier: 0,
        topProbability: 0.98,
        lastMjd: 61353.0,
      );
      const art = CatalogObject(
        survey: 'ztf',
        oid: 'ZTF26bogus',
        tier: 2,
        topProbability: 0.99,
        lastMjd: 61355.0,
        isArtifact: true,
      );

      final merged = mergeAndSortCatalogFeed(
        const [a, art, b],
        newestFirst: false,
      );
      expect(merged.map((o) => o.oid), ['170001', 'ZTF26sn', 'ZTF26bogus']);
    });

    test('orders by lastMjd desc, deduplicates by docId, and enforces limit when newestFirst is true', () {
      const older = CatalogObject(
        survey: 'ztf',
        oid: 'ZTF26old',
        tier: 0,
        topProbability: 0.99,
        lastMjd: 61350.0,
      );
      const dup = CatalogObject(
        survey: 'ztf',
        oid: 'ZTF26art',
        tier: 2,
        topProbability: 0.50,
        lastMjd: 61356.0,
        isArtifact: true,
      );
      const mid = CatalogObject(
        survey: 'lsst',
        oid: '170002',
        tier: 1,
        topProbability: 0.70,
        lastMjd: 61354.0,
      );

      final merged = mergeAndSortCatalogFeed(
        const [older, dup, mid, dup],
        newestFirst: true,
        limit: 2,
      );
      expect(merged.map((o) => o.oid), ['ZTF26art', '170002']);
    });
  });
}
