import 'package:flutter/material.dart';

import 'theme.dart';

class PrivacyPolicyScreen extends StatelessWidget {
  const PrivacyPolicyScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Privacy Policy — Sky Alerts')),
      body: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 820),
          child: ListView(
            padding: const EdgeInsets.all(20),
            children: const [
              _LegalSection(
                title: '1. Approximate Location Privacy',
                body:
                    'Backyard altitude, airmass, twilight, and moon-separation math runs locally on your device. '
                    'When you save an observatory coordinate or subscribe to clear-sky push alerts, coordinates are '
                    'rounded to 0.1° (~10 km grid cell) before syncing to Cloud Firestore. Exact home addresses or GPS '
                    'coordinates are never stored, shared, or sold.',
              ),
              _LegalSection(
                title: '2. Anonymous-First Accounts & Linking',
                body:
                    'You can bookmark objects and save alert preferences using an anonymous Firebase Authentication '
                    'session without providing personal contact details. If you choose to link Google, Sign in with Apple, '
                    'or Email, your existing bookmarks and backyard preferences transfer to your linked account.',
              ),
              _LegalSection(
                title: '3. In-App Account & Data Deletion',
                body:
                    'You can permanently delete your account, synced bookmarks, FCM push tokens, and rounded location '
                    'from the Saved & Alerts screen at any time using the "Delete Account & Data" action.',
              ),
              _LegalSection(
                title: '4. Billing & Subscriptions',
                body:
                    'SkyAlerts Pro subscriptions (Apple App Store, Google Play, and Stripe Web Billing via RevenueCat) '
                    'are tied to your Firebase UID to unlock Pro features across platforms. We do not store payment card numbers.',
              ),
              _LegalSection(
                title: '5. Affiliate Disclosure & Zero Ads',
                body:
                    'Sky Alerts never displays third-party ad networks. Contextual equipment suggestions carry an FTC '
                    'disclosure ("As an Amazon Associate I earn from qualifying purchases") and never alter scientific alert rankings.',
              ),
              _LegalSection(
                title: 'Contact',
                body: 'Questions or data requests: sky@henseler.app · https://sky.henseler.app',
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class TermsOfServiceScreen extends StatelessWidget {
  const TermsOfServiceScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Terms of Service — Sky Alerts')),
      body: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 820),
          child: ListView(
            padding: const EdgeInsets.all(20),
            children: const [
              _LegalSection(
                title: '1. Astronomical Data Sources',
                body:
                    'Sky Alerts aggregates public transient alerts and ephemerides from ALeRCE (ZTF & Vera C. Rubin '
                    'Observatory), IMCCE SkyBoT, NASA/JPL SSD/Horizons, MPC, Rochester Supernovae, Open-Meteo, and 7Timer!. '
                    'Alerts, magnitudes, and visibility forecasts are provided on a best-effort informational basis.',
              ),
              _LegalSection(
                title: '2. SkyAlerts Pro Subscriptions',
                body:
                    'SkyAlerts Pro offers Monthly (\$2.99/mo), Annual (\$24.99/yr with a 7-day free trial), and Lifetime '
                    '(\$49.99 once) plans. Auto-renewing plans can be canceled at any time through your Apple, Google Play, '
                    'or Stripe billing portal before the end of the current period.',
              ),
              _LegalSection(
                title: '3. Acceptable Use',
                body:
                    'You agree not to abuse backend APIs or automated triggers, bypass authentication rules, or redistribute '
                    'private user records.',
              ),
              _LegalSection(
                title: 'Contact',
                body: 'Support & billing inquiries: sky@henseler.app · https://sky.henseler.app',
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _LegalSection extends StatelessWidget {
  const _LegalSection({required this.title, required this.body});

  final String title;
  final String body;

  @override
  Widget build(BuildContext context) {
    final secondary = redNightModeNotifier.value
        ? SkyRedColors.textSecondary
        : SkyColors.textSecondary;
    return Card(
      margin: const EdgeInsets.only(bottom: 12),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(title, style: const TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
            const SizedBox(height: 6),
            Text(body, style: TextStyle(fontSize: 13, height: 1.45, color: secondary)),
          ],
        ),
      ),
    );
  }
}
