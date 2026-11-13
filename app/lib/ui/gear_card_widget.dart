import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';

import '../domain/gear_affiliate.dart';
import '../ui/theme.dart';

class GearRecommendationCard extends StatelessWidget {
  const GearRecommendationCard({super.key, this.magnitude});

  final double? magnitude;

  @override
  Widget build(BuildContext context) {
    final items = recommendGearForMagnitude(magnitude);
    final isRed = redNightModeNotifier.value;
    final secondary = isRed ? SkyRedColors.textSecondary : SkyColors.textSecondary;
    final primary = Theme.of(context).colorScheme.primary;
    final magNote = magnitude != null
        ? 'Matched for ~${magnitude!.toStringAsFixed(1)} mag'
        : 'Deep-sky & survey sensitivity picks';

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(Icons.camera_outlined, size: 18, color: primary),
                const SizedBox(width: 8),
                const Expanded(
                  child: Text(
                    'Gear That Can Reach This',
                    style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
                  ),
                ),
                Text(
                  magNote,
                  style: TextStyle(fontSize: 12, color: secondary),
                ),
              ],
            ),
            const SizedBox(height: 12),
            ...items.map(
              (gear) => Padding(
                padding: const EdgeInsets.only(bottom: 10),
                child: Container(
                  padding: const EdgeInsets.all(12),
                  decoration: BoxDecoration(
                    borderRadius: BorderRadius.circular(10),
                    border: Border.all(
                      color: isRed ? SkyRedColors.borderSubtle : SkyColors.borderSubtle,
                    ),
                  ),
                  child: Row(
                    children: [
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              gear.categoryBadge,
                              style: TextStyle(
                                fontSize: 11,
                                fontWeight: FontWeight.bold,
                                color: primary,
                              ),
                            ),
                            const SizedBox(height: 2),
                            Text(
                              gear.name,
                              style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 14),
                            ),
                            const SizedBox(height: 2),
                            Text(
                              '${gear.tagline} · ${gear.specsNote}',
                              style: TextStyle(fontSize: 12, color: secondary),
                            ),
                          ],
                        ),
                      ),
                      const SizedBox(width: 12),
                      OutlinedButton.icon(
                        onPressed: () => launchUrl(
                          Uri.parse(gear.url),
                          mode: LaunchMode.externalApplication,
                        ),
                        icon: const Icon(Icons.open_in_new, size: 15),
                        label: const Text('View Gear'),
                      ),
                    ],
                  ),
                ),
              ),
            ),
            const SizedBox(height: 4),
            Text(
              ftcAffiliateDisclosure,
              style: TextStyle(fontSize: 11, color: secondary),
            ),
          ],
        ),
      ),
    );
  }
}
