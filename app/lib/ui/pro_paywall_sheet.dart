import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../domain/pro_entitlement.dart';
import 'theme.dart';

Future<void> showProPaywallSheet(BuildContext context) {
  return showModalBottomSheet<void>(
    context: context,
    isScrollControlled: true,
    backgroundColor: SkyColors.bgSurface,
    shape: const RoundedRectangleBorder(
      borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
    ),
    builder: (sheetCtx) => _ProPaywallSheet(parentContext: context),
  );
}

class _ProPaywallSheet extends StatefulWidget {
  const _ProPaywallSheet({required this.parentContext});

  final BuildContext parentContext;

  @override
  State<_ProPaywallSheet> createState() => _ProPaywallSheetState();
}

class _ProPaywallSheetState extends State<_ProPaywallSheet> {
  ProPlanTier _selectedTier = ProPlanTier.annual;

  ProPlanOption get _selectedOption => proPlanOptions.firstWhere(
        (o) => o.tier == _selectedTier,
        orElse: () => proPlanOptions.first,
      );

  void _activatePreview() {
    proEntitlementNotifier.unlockPreviewPro(_selectedTier);
    Navigator.of(context).pop();
    ScaffoldMessenger.of(widget.parentContext).showSnackBar(
      SnackBar(
        content: Text(
          'SkyAlerts Pro preview enabled (${_selectedOption.title} · ${_selectedOption.priceLabel}).',
        ),
      ),
    );
  }

  Future<void> _restore() async {
    final restored = await proEntitlementNotifier.restorePurchases();
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(
          restored
              ? 'SkyAlerts Pro entitlement restored.'
              : 'No previous App Store / Play / Stripe purchase found in this session.',
        ),
      ),
    );
  }

  void _openLegalRoute(String path) {
    Navigator.of(context).pop();
    widget.parentContext.push(path);
  }

  @override
  Widget build(BuildContext context) {
    return SafeArea(
      child: ValueListenableBuilder<ProEntitlementState>(
        valueListenable: proEntitlementNotifier,
        builder: (context, proState, _) {
          final maxHeight = MediaQuery.of(context).size.height * 0.9;
          return ConstrainedBox(
            constraints: BoxConstraints(maxHeight: maxHeight),
            child: SingleChildScrollView(
              padding: const EdgeInsets.fromLTRB(20, 14, 20, 24),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                mainAxisSize: MainAxisSize.min,
                children: [
                  Center(
                    child: Container(
                      width: 40,
                      height: 4,
                      decoration: BoxDecoration(
                        color: SkyColors.borderSubtle,
                        borderRadius: BorderRadius.circular(2),
                      ),
                    ),
                  ),
                  const SizedBox(height: 16),
                  Row(
                    children: [
                      Container(
                        padding: const EdgeInsets.symmetric(
                          horizontal: 10,
                          vertical: 4,
                        ),
                        decoration: BoxDecoration(
                          color: SkyColors.accentAmber.withValues(alpha: 0.16),
                          borderRadius: BorderRadius.circular(20),
                          border: Border.all(
                            color: SkyColors.accentAmber.withValues(alpha: 0.5),
                          ),
                        ),
                        child: const Text(
                          'SKYALERTS PRO · BACKYARD OBSERVER PASS',
                          style: TextStyle(
                            fontSize: 11,
                            fontWeight: FontWeight.bold,
                            letterSpacing: 0.8,
                            color: SkyColors.accentAmber,
                          ),
                        ),
                      ),
                      const Spacer(),
                      IconButton(
                        onPressed: () => Navigator.of(context).pop(),
                        icon: const Icon(Icons.close),
                        tooltip: 'Close',
                      ),
                    ],
                  ),
                  const SizedBox(height: 8),
                  const Text(
                    'Never miss a clear sky with a bright target overhead.',
                    style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold),
                  ),
                  const SizedBox(height: 6),
                  const Text(
                    'Scientific transient feeds, Tonight planner, and 7-night weather stay free forever. Upgrade for server-side clear-sky push alerts matched to your backyard rig.',
                    style: TextStyle(
                      fontSize: 13,
                      color: SkyColors.textSecondary,
                    ),
                  ),
                  if (proState.isPro) ...[
                    const SizedBox(height: 12),
                    Container(
                      padding: const EdgeInsets.all(12),
                      decoration: BoxDecoration(
                        color: const Color(0xFF3DDC97).withValues(alpha: 0.12),
                        borderRadius: BorderRadius.circular(12),
                        border: Border.all(
                          color: const Color(0xFF3DDC97).withValues(alpha: 0.45),
                        ),
                      ),
                      child: Row(
                        children: [
                          const Icon(
                            Icons.verified_outlined,
                            color: Color(0xFF3DDC97),
                          ),
                          const SizedBox(width: 10),
                          Expanded(
                            child: Text(
                              'Pro active (${proState.activeOption?.title ?? "Preview"}) — Preview mode',
                              style: const TextStyle(fontWeight: FontWeight.w600),
                            ),
                          ),
                          TextButton(
                            onPressed: proEntitlementNotifier.resetProStatus,
                            child: const Text('Reset'),
                          ),
                        ],
                      ),
                    ),
                  ],
                  const SizedBox(height: 16),
                  Container(
                    padding: const EdgeInsets.all(14),
                    decoration: BoxDecoration(
                      color: SkyColors.bgElevated,
                      borderRadius: BorderRadius.circular(12),
                      border: Border.all(color: SkyColors.borderSubtle),
                    ),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Text(
                          'FREE FOREVER',
                          style: TextStyle(
                            fontSize: 11,
                            fontWeight: FontWeight.bold,
                            letterSpacing: 1.0,
                            color: SkyColors.textSecondary,
                          ),
                        ),
                        const SizedBox(height: 6),
                        ...freeForeverFeatures.map(
                          (f) => Padding(
                            padding: const EdgeInsets.only(bottom: 4),
                            child: Row(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                const Icon(
                                  Icons.check,
                                  size: 16,
                                  color: SkyColors.textSecondary,
                                ),
                                const SizedBox(width: 8),
                                Expanded(
                                  child: Text(
                                    f,
                                    style: const TextStyle(
                                      fontSize: 13,
                                      color: SkyColors.textSecondary,
                                    ),
                                  ),
                                ),
                              ],
                            ),
                          ),
                        ),
                        const Divider(height: 20),
                        const Text(
                          'SKYALERTS PRO',
                          style: TextStyle(
                            fontSize: 11,
                            fontWeight: FontWeight.bold,
                            letterSpacing: 1.0,
                            color: SkyColors.accentAmber,
                          ),
                        ),
                        const SizedBox(height: 6),
                        ...proObserverFeatures.map(
                          (f) => Padding(
                            padding: const EdgeInsets.only(bottom: 5),
                            child: Row(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                const Icon(
                                  Icons.auto_awesome,
                                  size: 16,
                                  color: SkyColors.accentAmber,
                                ),
                                const SizedBox(width: 8),
                                Expanded(
                                  child: Text(
                                    f,
                                    style: const TextStyle(fontSize: 13),
                                  ),
                                ),
                              ],
                            ),
                          ),
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(height: 16),
                  ...proPlanOptions.map((option) {
                    final selected = option.tier == _selectedTier;
                    return Padding(
                      padding: const EdgeInsets.only(bottom: 10),
                      child: InkWell(
                        borderRadius: BorderRadius.circular(12),
                        onTap: () => setState(() => _selectedTier = option.tier),
                        child: Container(
                          padding: const EdgeInsets.all(14),
                          decoration: BoxDecoration(
                            color: selected
                                ? SkyColors.accentAmber.withValues(alpha: 0.12)
                                : SkyColors.bgElevated,
                            borderRadius: BorderRadius.circular(12),
                            border: Border.all(
                              color: selected
                                  ? SkyColors.accentAmber
                                  : SkyColors.borderSubtle,
                              width: selected ? 1.5 : 1,
                            ),
                          ),
                          child: Row(
                            children: [
                              Icon(
                                selected
                                    ? Icons.radio_button_checked
                                    : Icons.radio_button_off,
                                color: selected
                                    ? SkyColors.accentAmber
                                    : SkyColors.textSecondary,
                              ),
                              const SizedBox(width: 12),
                              Expanded(
                                child: Column(
                                  crossAxisAlignment: CrossAxisAlignment.start,
                                  children: [
                                    Wrap(
                                      spacing: 8,
                                      crossAxisAlignment:
                                          WrapCrossAlignment.center,
                                      children: [
                                        Text(
                                          option.title,
                                          style: const TextStyle(
                                            fontWeight: FontWeight.bold,
                                            fontSize: 15,
                                          ),
                                        ),
                                        if (option.badge != null)
                                          Container(
                                            padding: const EdgeInsets.symmetric(
                                              horizontal: 6,
                                              vertical: 2,
                                            ),
                                            decoration: BoxDecoration(
                                              color: SkyColors.accentAmber,
                                              borderRadius:
                                                  BorderRadius.circular(4),
                                            ),
                                            child: Text(
                                              option.badge!,
                                              style: const TextStyle(
                                                color: Colors.black,
                                                fontSize: 10,
                                                fontWeight: FontWeight.bold,
                                              ),
                                            ),
                                          ),
                                      ],
                                    ),
                                    if (option.trialLabel != null) ...[
                                      const SizedBox(height: 2),
                                      Text(
                                        option.trialLabel!,
                                        style: const TextStyle(
                                          fontSize: 12,
                                          color: Color(0xFF3DDC97),
                                        ),
                                      ),
                                    ],
                                  ],
                                ),
                              ),
                              Column(
                                crossAxisAlignment: CrossAxisAlignment.end,
                                children: [
                                  Text(
                                    option.priceLabel,
                                    style: const TextStyle(
                                      fontSize: 17,
                                      fontWeight: FontWeight.bold,
                                    ),
                                  ),
                                  Text(
                                    option.cadenceLabel,
                                    style: const TextStyle(
                                      fontSize: 11,
                                      color: SkyColors.textSecondary,
                                    ),
                                  ),
                                ],
                              ),
                            ],
                          ),
                        ),
                      ),
                    );
                  }),
                  const SizedBox(height: 6),
                  FilledButton.icon(
                    onPressed: _activatePreview,
                    icon: const Icon(Icons.auto_awesome),
                    label: Text(
                      _selectedOption.trialLabel != null
                          ? 'Start 7-Day Free Trial (Preview Unlock)'
                          : 'Unlock SkyAlerts Pro (Preview)',
                    ),
                  ),
                  const SizedBox(height: 6),
                  Row(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      TextButton(
                        onPressed: _restore,
                        child: const Text('Restore Purchases'),
                      ),
                      const Text('·', style: TextStyle(color: SkyColors.textSecondary)),
                      TextButton(
                        onPressed: () => _openLegalRoute('/terms'),
                        child: const Text('Terms'),
                      ),
                      const Text('·', style: TextStyle(color: SkyColors.textSecondary)),
                      TextButton(
                        onPressed: () => _openLegalRoute('/privacy'),
                        child: const Text('Privacy'),
                      ),
                    ],
                  ),
                ],
              ),
            ),
          );
        },
      ),
    );
  }
}
