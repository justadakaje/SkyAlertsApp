import 'package:flutter/foundation.dart';

enum ProPlanTier {
  monthly,
  annual,
  lifetime,
}

class ProPlanOption {
  const ProPlanOption({
    required this.tier,
    required this.id,
    required this.title,
    required this.priceLabel,
    required this.cadenceLabel,
    this.badge,
    this.trialLabel,
  });

  final ProPlanTier tier;
  final String id;
  final String title;
  final String priceLabel;
  final String cadenceLabel;
  final String? badge;
  final String? trialLabel;
}

const List<ProPlanOption> proPlanOptions = [
  ProPlanOption(
    tier: ProPlanTier.annual,
    id: 'skyalerts_pro_annual',
    title: 'Annual Observer',
    priceLabel: r'$24.99',
    cadenceLabel: '/ year',
    badge: 'BEST VALUE · SAVE 30%',
    trialLabel: '7-day free trial',
  ),
  ProPlanOption(
    tier: ProPlanTier.monthly,
    id: 'skyalerts_pro_monthly',
    title: 'Monthly',
    priceLabel: r'$2.99',
    cadenceLabel: '/ month',
  ),
  ProPlanOption(
    tier: ProPlanTier.lifetime,
    id: 'skyalerts_pro_lifetime',
    title: 'Lifetime Pass',
    priceLabel: r'$49.99',
    cadenceLabel: 'one-time',
    badge: 'FOUNDING OBSERVER',
  ),
];

const List<String> freeForeverFeatures = [
  'Live Rubin + ZTF Sky Feed, Solar System & Trends',
  'Weekly Sky Dispatch & audio briefing notes',
  'Tonight From My Backyard planner & 7-night weather outlook',
  '1-tap RA/Dec coordinate copy & Red Night Mode',
];

const List<String> proObserverFeatures = [
  'Server-side Clear-Sky + Bright-Target Backyard Push Alerts',
  'Multi-night target window notifications matched to your rig',
  'Unlimited custom rig & location presets synced across devices',
  'Priority CSV & observation log exports (no ads, ever)',
];

class ProEntitlementState {
  const ProEntitlementState({
    this.isPro = false,
    this.activePlan,
    this.isPreviewUnlock = false,
  });

  final bool isPro;
  final ProPlanTier? activePlan;
  final bool isPreviewUnlock;

  ProPlanOption? get activeOption {
    if (activePlan == null) return null;
    for (final option in proPlanOptions) {
      if (option.tier == activePlan) return option;
    }
    return null;
  }
}

class ProEntitlementController extends ValueNotifier<ProEntitlementState> {
  ProEntitlementController([
    super.value = const ProEntitlementState(),
  ]);

  ProPlanTier? _lastUnlockedTier;

  void unlockPreviewPro(ProPlanTier tier) {
    _lastUnlockedTier = tier;
    value = ProEntitlementState(
      isPro: true,
      activePlan: tier,
      isPreviewUnlock: true,
    );
  }

  /// Attempts to restore an active or preview entitlement in this session.
  Future<bool> restorePurchases() async {
    if (value.isPro) return true;
    final previous = _lastUnlockedTier;
    if (previous != null) {
      value = ProEntitlementState(
        isPro: true,
        activePlan: previous,
        isPreviewUnlock: true,
      );
      return true;
    }
    return false;
  }

  void resetProStatus() {
    value = const ProEntitlementState();
  }
}

final ProEntitlementController proEntitlementNotifier =
    ProEntitlementController();
