import 'package:firebase_auth/firebase_auth.dart';
import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../data/firestore_repository.dart';
import '../domain/pro_entitlement.dart';
import 'pro_paywall_sheet.dart';
import 'theme.dart';
import 'tonight_screen.dart';

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
  bool _authBusy = false;

  Future<void> _savePreferences() async {
    final roundedLoc = backyardLocationNotifier.value.roundedToTenth;
    final scopePreset = backyardScopeNotifier.value.id;
    await widget.repository.saveAlertPreferences(
      UserAlertPreferences(
        notifyTransients: _notifyTransients,
        notifySolarMatched: _notifySolarMatched,
        notifyWeeklyDispatch: _notifyWeeklyDispatch,
        minConfidence: _minConfidence,
      ),
      roundedLat: roundedLoc.latitudeDeg,
      roundedLon: roundedLoc.longitudeDeg,
      scopePreset: scopePreset,
    );
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(
        content: Text('Alert & rounded backyard sync preferences updated.'),
      ),
    );
  }

  Future<void> _runAuthAction(
    Future<void> Function() action,
    String successMessage,
  ) async {
    if (_authBusy) return;
    setState(() => _authBusy = true);
    try {
      await action();
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(successMessage)),
      );
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Account action failed: $e')),
      );
    } finally {
      if (mounted) {
        setState(() => _authBusy = false);
      }
    }
  }

  Future<void> _confirmDeleteAccount() async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Delete Account & Data?'),
        content: const Text(
          'This permanently deletes your synced bookmarks, alert preferences, and Firebase Auth account. This action cannot be undone.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(false),
            child: const Text('Cancel'),
          ),
          FilledButton(
            style: FilledButton.styleFrom(
              backgroundColor: const Color(0xFFFF6B4A),
            ),
            onPressed: () => Navigator.of(ctx).pop(true),
            child: const Text('Delete Permanently'),
          ),
        ],
      ),
    );
    if (confirmed == true) {
      await _runAuthAction(
        widget.repository.deleteUserAccountAndData,
        'Account and synced data deleted.',
      );
    }
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
                  Card(
                    margin: const EdgeInsets.only(bottom: 16),
                    child: Padding(
                      padding: const EdgeInsets.all(16),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Row(
                            children: [
                              Icon(
                                user == null
                                    ? Icons.cloud_off_outlined
                                    : (user.isAnonymous
                                          ? Icons.verified_user_outlined
                                          : Icons.cloud_done_outlined),
                                color: user == null
                                    ? SkyColors.accentAmber
                                    : const Color(0xFF3DDC97),
                              ),
                              const SizedBox(width: 10),
                              Expanded(
                                child: Column(
                                  crossAxisAlignment: CrossAxisAlignment.start,
                                  children: [
                                    const Text(
                                      'Account, Sync & Privacy',
                                      style: TextStyle(
                                        fontSize: 16,
                                        fontWeight: FontWeight.bold,
                                      ),
                                    ),
                                    const SizedBox(height: 2),
                                    Text(
                                      user == null
                                          ? 'Not signed in — start an anonymous session or link an account to sync bookmarks and alerts.'
                                          : (user.isAnonymous
                                                ? 'Anonymous sync active (${user.uid.substring(0, 8)}…) — link Google or Apple to keep data across devices.'
                                                : 'Synced as ${user.email ?? user.uid}'),
                                      style: const TextStyle(
                                        fontSize: 13,
                                        color: SkyColors.textSecondary,
                                      ),
                                    ),
                                  ],
                                ),
                              ),
                            ],
                          ),
                          const SizedBox(height: 12),
                          Wrap(
                            spacing: 8,
                            runSpacing: 8,
                            children: [
                              if (user == null)
                                FilledButton.icon(
                                  onPressed: _authBusy
                                      ? null
                                      : () => _runAuthAction(
                                          widget.repository.ensureSignedInAnonymously,
                                          'Anonymous sync started.',
                                        ),
                                  icon: const Icon(Icons.bolt, size: 18),
                                  label: const Text('Start Anonymous Sync'),
                                ),
                              if (user == null || user.isAnonymous) ...[
                                OutlinedButton.icon(
                                  onPressed: _authBusy
                                      ? null
                                      : () => _runAuthAction(
                                          widget.repository.linkOrSignInWithGoogle,
                                          user?.isAnonymous == true
                                              ? 'Google account linked.'
                                              : 'Signed in with Google.',
                                        ),
                                  icon: const Icon(Icons.g_mobiledata, size: 20),
                                  label: Text(
                                    user?.isAnonymous == true
                                        ? 'Link Google Account'
                                        : 'Continue with Google',
                                  ),
                                ),
                                OutlinedButton.icon(
                                  onPressed: _authBusy
                                      ? null
                                      : () => _runAuthAction(
                                          widget.repository.linkOrSignInWithApple,
                                          user?.isAnonymous == true
                                              ? 'Apple account linked.'
                                              : 'Signed in with Apple.',
                                        ),
                                  icon: const Icon(Icons.apple, size: 18),
                                  label: Text(
                                    user?.isAnonymous == true
                                        ? 'Link Apple Account'
                                        : 'Sign in with Apple',
                                  ),
                                ),
                              ],
                              if (user != null) ...[
                                OutlinedButton.icon(
                                  onPressed: _authBusy
                                      ? null
                                      : () => _runAuthAction(
                                          FirebaseAuth.instance.signOut,
                                          'Signed out.',
                                        ),
                                  icon: const Icon(Icons.logout, size: 16),
                                  label: const Text('Sign Out'),
                                ),
                                TextButton.icon(
                                  style: TextButton.styleFrom(
                                    foregroundColor: const Color(0xFFFF6B4A),
                                  ),
                                  onPressed: _authBusy ? null : _confirmDeleteAccount,
                                  icon: const Icon(Icons.delete_forever_outlined, size: 18),
                                  label: const Text('Delete Account & Data'),
                                ),
                              ],
                            ],
                          ),
                        ],
                      ),
                    ),
                  ),
                  ValueListenableBuilder<ProEntitlementState>(
                    valueListenable: proEntitlementNotifier,
                    builder: (context, proState, _) {
                      return Card(
                        margin: const EdgeInsets.only(bottom: 16),
                        child: ListTile(
                          leading: Icon(
                            proState.isPro
                                ? Icons.verified_outlined
                                : Icons.auto_awesome,
                            color: proState.isPro
                                ? const Color(0xFF3DDC97)
                                : SkyColors.accentAmber,
                          ),
                          title: Text(
                            proState.isPro
                                ? 'SkyAlerts Pro Active (${proState.activeOption?.title ?? "Preview"})'
                                : 'SkyAlerts Pro — Clear-Sky Backyard Push Alerts',
                            style: const TextStyle(fontWeight: FontWeight.bold),
                          ),
                          subtitle: Text(
                            proState.isPro
                                ? 'Clear-sky + bright-target push matching is preview-enabled for your rounded backyard profile.'
                                : r'Match clear local skies with bright transients for your rig ($2.99/mo, $24.99/yr 7-day trial, or $49.99 lifetime).',
                          ),
                          trailing: FilledButton.tonal(
                            onPressed: () => showProPaywallSheet(context),
                            child: Text(proState.isPro ? 'Manage' : 'View Plans'),
                          ),
                        ),
                      );
                    },
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
                  const SizedBox(height: 24),
                  Card(
                    child: Padding(
                      padding: const EdgeInsets.symmetric(
                        horizontal: 16,
                        vertical: 12,
                      ),
                      child: Wrap(
                        spacing: 12,
                        runSpacing: 8,
                        crossAxisAlignment: WrapCrossAlignment.center,
                        children: [
                          const Text(
                            'Legal & Privacy',
                            style: TextStyle(
                              fontSize: 13,
                              fontWeight: FontWeight.w600,
                              color: SkyColors.textSecondary,
                            ),
                          ),
                          TextButton.icon(
                            onPressed: () => context.push('/privacy'),
                            icon: const Icon(Icons.privacy_tip_outlined, size: 16),
                            label: const Text('Privacy Policy'),
                          ),
                          TextButton.icon(
                            onPressed: () => context.push('/terms'),
                            icon: const Icon(Icons.description_outlined, size: 16),
                            label: const Text('Terms of Service'),
                          ),
                        ],
                      ),
                    ),
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
