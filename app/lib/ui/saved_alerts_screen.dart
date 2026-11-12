import 'package:firebase_auth/firebase_auth.dart';
import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../data/firestore_repository.dart';
import 'theme.dart';

class SavedAlertsScreen extends StatefulWidget {
  const SavedAlertsScreen({super.key, required this.repository});

  final SkyAlertsRepository repository;

  @override
  State<SavedAlertsScreen> createState() => _SavedAlertsScreenState();
}

class _SavedAlertsScreenState extends State<SavedAlertsScreen> {
  bool _notifyTransients = true;
  bool _notifySolarMatched = true;
  bool _notifyWeeklyDispatch = true;
  double _minConfidence = 0.80;

  Future<void> _savePreferences() async {
    await widget.repository.saveAlertPreferences(
      UserAlertPreferences(
        notifyTransients: _notifyTransients,
        notifySolarMatched: _notifySolarMatched,
        notifyWeeklyDispatch: _notifyWeeklyDispatch,
        minConfidence: _minConfidence,
      ),
    );
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(content: Text('Push notification preferences updated.')),
    );
  }

  @override
  Widget build(BuildContext context) {
    return StreamBuilder<User?>(
      stream: widget.repository.authStateChanges,
      builder: (context, authSnap) {
        final user = authSnap.data ?? widget.repository.currentUser;
        return Scaffold(
          appBar: AppBar(title: const Text('Saved Objects & Push Notification Alerts')),
          body: Center(
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 880),
              child: ListView(
                padding: const EdgeInsets.all(16),
                children: [
                  if (user == null)
                    Card(
                      margin: const EdgeInsets.only(bottom: 16),
                      child: ListTile(
                        leading: const Icon(
                          Icons.person_outline,
                          color: SkyColors.accentAmber,
                        ),
                        title: const Text(
                          'Sign in to sync saved bookmarks across devices',
                          style: TextStyle(fontWeight: FontWeight.bold),
                        ),
                        subtitle: const Text(
                          'Use the Admin tab to sign in with your account.',
                        ),
                        trailing: OutlinedButton(
                          onPressed: () => context.go('/admin'),
                          child: const Text('Sign In'),
                        ),
                      ),
                    ),
                  Card(
                    child: Padding(
                      padding: const EdgeInsets.all(16),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          const Text(
                            'Push Notification Topics & Custom Thresholds (FCM)',
                            style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
                          ),
                          const SizedBox(height: 8),
                          SwitchListTile(
                            title: const Text('New cosmic explosions & outbursts'),
                            subtitle: const Text(
                              'Supernovae (SNIa, SLSN), Tidal Disruption Events (TDE), and Kilonovae (KN).',
                            ),
                            value: _notifyTransients,
                            onChanged: (v) => setState(() => _notifyTransients = v),
                          ),
                          SwitchListTile(
                            title: const Text('Named Solar System catches (IMCCE SkyBoT)'),
                            subtitle: const Text(
                              'Alerts when a survey detection matches a numbered/named asteroid.',
                            ),
                            value: _notifySolarMatched,
                            onChanged: (v) => setState(() => _notifySolarMatched = v),
                          ),
                          SwitchListTile(
                            title: const Text('Weekly Sky Dispatch (Sundays)'),
                            subtitle: const Text(
                              'Summary of the week’s brightest transients and Solar System catches.',
                            ),
                            value: _notifyWeeklyDispatch,
                            onChanged: (v) => setState(() => _notifyWeeklyDispatch = v),
                          ),
                          const Divider(height: 24),
                          Text(
                            'Minimum ML classification confidence: ${(_minConfidence * 100).round()}%',
                            style: const TextStyle(
                              fontSize: 13,
                              color: SkyColors.textSecondary,
                            ),
                          ),
                          Slider(
                            value: _minConfidence,
                            min: 0.50,
                            max: 0.95,
                            divisions: 9,
                            label: '${(_minConfidence * 100).round()}%',
                            onChanged: (v) => setState(() => _minConfidence = v),
                          ),
                          Align(
                            alignment: Alignment.centerRight,
                            child: FilledButton.icon(
                              onPressed: _savePreferences,
                              icon: const Icon(Icons.save_outlined),
                              label: const Text('Save Alert Preferences'),
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
                  const SizedBox(height: 20),
                  const Text(
                    'BOOKMARKED OBJECTS (FOLLOWING FOR LIGHT-CURVE UPDATES)',
                    style: TextStyle(
                      fontSize: 12,
                      fontWeight: FontWeight.bold,
                      letterSpacing: 1.1,
                      color: SkyColors.textSecondary,
                    ),
                  ),
                  const SizedBox(height: 8),
                  StreamBuilder<List<Map<String, dynamic>>>(
                    stream: widget.repository.watchBookmarks(),
                    builder: (context, snapshot) {
                      final items = snapshot.data ?? const [];
                      if (items.isEmpty) {
                        return const Card(
                          child: Padding(
                            padding: EdgeInsets.all(16),
                            child: Text(
                              'No bookmarked objects yet. Tap the bookmark icon on any object detail page to receive push notifications when new detections arrive.',
                              style: TextStyle(color: SkyColors.textSecondary),
                            ),
                          ),
                        );
                      }
                      return Column(
                        children: items.map((b) {
                          final survey = (b['survey'] as String?) ?? 'ztf';
                          final oid = (b['oid'] as String?) ?? '';
                          final cls = (b['top_class'] as String?) ?? 'Unclassified';
                          return Card(
                            child: ListTile(
                              onTap: () => context.go('/objects/$survey/$oid'),
                              title: Text(
                                oid,
                                style: const TextStyle(fontWeight: FontWeight.bold),
                              ),
                              subtitle: Text('${survey.toUpperCase()} · $cls'),
                              trailing: const Icon(Icons.chevron_right),
                            ),
                          );
                        }).toList(),
                      );
                    },
                  ),
                ],
              ),
            ),
          ),
        );
      },
    );
  }
}
