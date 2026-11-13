import 'package:flutter_test/flutter_test.dart';
import 'package:skyalerts_app/domain/pro_entitlement.dart';

void main() {
  group('proPlanOptions', () {
    test('defines monthly, annual 7-day trial, and lifetime observer tiers', () {
      expect(proPlanOptions, hasLength(3));

      final monthly = proPlanOptions.firstWhere(
        (o) => o.tier == ProPlanTier.monthly,
      );
      expect(monthly.priceLabel, r'$2.99');
      expect(monthly.cadenceLabel, '/ month');

      final annual = proPlanOptions.firstWhere(
        (o) => o.tier == ProPlanTier.annual,
      );
      expect(annual.priceLabel, r'$24.99');
      expect(annual.trialLabel, '7-day free trial');

      final lifetime = proPlanOptions.firstWhere(
        (o) => o.tier == ProPlanTier.lifetime,
      );
      expect(lifetime.priceLabel, r'$49.99');
      expect(lifetime.cadenceLabel, 'one-time');
    });
  });

  group('ProEntitlementController', () {
    test('unlockPreviewPro, resetProStatus, and restorePurchases transition cleanly', () async {
      final controller = ProEntitlementController();
      expect(controller.value.isPro, isFalse);
      expect(controller.value.activePlan, isNull);

      expect(await controller.restorePurchases(), isFalse);

      controller.unlockPreviewPro(ProPlanTier.annual);
      expect(controller.value.isPro, isTrue);
      expect(controller.value.activePlan, ProPlanTier.annual);
      expect(controller.value.isPreviewUnlock, isTrue);
      expect(controller.value.activeOption?.id, 'skyalerts_pro_annual');

      controller.resetProStatus();
      expect(controller.value.isPro, isFalse);

      expect(await controller.restorePurchases(), isTrue);
      expect(controller.value.isPro, isTrue);
      expect(controller.value.activePlan, ProPlanTier.annual);
    });
  });
}
