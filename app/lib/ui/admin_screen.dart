import 'package:firebase_auth/firebase_auth.dart';
import 'package:flutter/material.dart';

import '../data/firestore_repository.dart';
import '../domain/format.dart';
import 'sky_media_widgets.dart';
import 'theme.dart';

class AdminScreen extends StatefulWidget {
  const AdminScreen({super.key, required this.repository});

  final SkyAlertsRepository repository;

  @override
  State<AdminScreen> createState() => _AdminScreenState();
}

class _AdminScreenState extends State<AdminScreen> {
  final TextEditingController _emailCtrl = TextEditingController();
  final TextEditingController _passwordCtrl = TextEditingController();
  String _statusMessage =
      'Sign in with your owner account below to run pipeline actions and inspect run logs.';
  bool _busy = false;
  List<Map<String, dynamic>> _runs = const [];
  List<Map<String, dynamic>> _audits = const [];

  @override
  void initState() {
    super.initState();
    _refreshLogs();
  }

  @override
  void dispose() {
    _emailCtrl.dispose();
    _passwordCtrl.dispose();
    super.dispose();
  }

  Future<void> _refreshLogs() async {
    if (widget.repository.currentUser == null) return;
    try {
      final results = await Future.wait([
        widget.repository.fetchRecentAdminRuns(limit: 8),
        widget.repository.fetchRecentAuditLogs(limit: 10),
      ]);
      if (!mounted) return;
      setState(() {
        _runs = results[0];
        _audits = results[1];
      });
    } catch (_) {
      // Ignore if token doesn't have admin access yet.
    }
  }

  Future<void> _signInWithEmail() async {
    final email = _emailCtrl.text.trim();
    final password = _passwordCtrl.text;
    if (email.isEmpty || password.length < 6) {
      setState(() {
        _statusMessage = 'Enter your owner email and a password (at least 6 characters).';
      });
      return;
    }
    setState(() {
      _busy = true;
      _statusMessage = 'Signing in as $email…';
    });
    try {
      await widget.repository.signInWithEmail(email, password);
      await widget.repository.currentUser?.getIdToken(true);
      if (!mounted) return;
      setState(() {
        _busy = false;
        _statusMessage = 'Signed in as $email.';
      });
      await _refreshLogs();
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _busy = false;
        _statusMessage = 'Sign-in failed: $e';
      });
    }
  }

  Future<void> _signInWithGoogle() async {
    setState(() {
      _busy = true;
      _statusMessage = 'Opening Google Sign-In…';
    });
    try {
      final cred = await widget.repository.signInWithGoogle();
      if (!mounted) return;
      setState(() {
        _busy = false;
        _statusMessage = 'Signed in as ${cred.user?.email ?? cred.user?.uid}.';
      });
      await _refreshLogs();
    } on FirebaseAuthException catch (e) {
      if (!mounted) return;
      final msg = switch (e.code) {
        'popup-blocked' =>
          'Popup blocked. Allow popups for this site and retry, or use email & password above.',
        'popup-closed-by-user' || 'cancelled-popup-request' => 'Google sign-in cancelled.',
        'operation-not-allowed' =>
          'Google sign-in is not enabled for this Firebase project.',
        'unauthorized-domain' =>
          'This domain is not authorized for Firebase sign-in.',
        'network-request-failed' => 'Network error during sign-in. Check your connection and retry.',
        _ => 'Google sign-in failed (${e.code}): ${e.message ?? 'no details'}',
      };
      setState(() {
        _busy = false;
        _statusMessage = msg;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _busy = false;
        _statusMessage = 'Google sign-in failed: $e';
      });
    }
  }

  Future<void> _invoke(String callableName, [Map<String, dynamic>? payload]) async {
    if (widget.repository.currentUser == null) {
      setState(() {
        _statusMessage = 'Please sign in with your owner account first.';
      });
      return;
    }
    setState(() {
      _busy = true;
      _statusMessage = 'Running $callableName…';
    });
    try {
      final res = await widget.repository.callAdminFunction(callableName, payload);
      // Refresh ID token in case the backend stamped the admin=true custom claim
      await widget.repository.currentUser?.getIdToken(true);
      if (!mounted) return;
      setState(() {
        _busy = false;
        _statusMessage = '$callableName completed successfully.';
      });
      await _refreshLogs();

      if (callableName == 'preview_digest' && mounted) {
        showSkyDispatchSheet(
          context,
          subject: (res['subject'] as String?) ?? 'Weekly Sky Dispatch Preview',
          podcastScript: (res['podcast'] as String?) ?? '',
          markdownDispatch: (res['markdown'] as String?) ?? '',
        );
      }
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _busy = false;
        _statusMessage = '$callableName failed: $e';
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return StreamBuilder<User?>(
      stream: widget.repository.authStateChanges,
      builder: (context, authSnap) {
        final user = authSnap.data ?? widget.repository.currentUser;
        return Scaffold(
          appBar: AppBar(
            title: const Text('Admin · Pipeline Controls & Observability'),
            actions: [
              if (user != null)
                IconButton(
                  tooltip: 'Refresh run logs',
                  onPressed: _refreshLogs,
                  icon: const Icon(Icons.refresh),
                ),
            ],
          ),
          body: Center(
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 920),
              child: ListView(
                padding: const EdgeInsets.all(16),
                children: [
                  Card(
                    child: Padding(
                      padding: const EdgeInsets.all(16),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Row(
                            children: [
                              Icon(
                                user != null ? Icons.verified_user : Icons.lock_outline,
                                color: user != null
                                    ? const Color(0xFF3DDC97)
                                    : SkyColors.accentAmber,
                              ),
                              const SizedBox(width: 10),
                              Expanded(
                                child: Text(
                                  user != null
                                      ? 'Signed in as ${user.email ?? user.uid}'
                                      : 'Owner Sign-In Required',
                                  style: const TextStyle(
                                    fontSize: 16,
                                    fontWeight: FontWeight.bold,
                                  ),
                                ),
                              ),
                              if (user != null)
                                OutlinedButton.icon(
                                  onPressed: _busy
                                      ? null
                                      : () async {
                                          await widget.repository.signOut();
                                          setState(() {
                                            _runs = const [];
                                            _audits = const [];
                                            _statusMessage = 'Signed out.';
                                          });
                                        },
                                  icon: const Icon(Icons.logout, size: 16),
                                  label: const Text('Sign Out'),
                                ),
                            ],
                          ),
                          const SizedBox(height: 8),
                          Text(
                            _statusMessage,
                            style: const TextStyle(
                              fontSize: 13,
                              color: SkyColors.textSecondary,
                            ),
                          ),
                          if (user == null) ...[
                            const Divider(height: 24),
                            const Text(
                              'Sign in directly (works inside iOS/Android PWA & mobile browsers):',
                              style: TextStyle(
                                fontSize: 12,
                                fontWeight: FontWeight.w600,
                                color: SkyColors.textSecondary,
                              ),
                            ),
                            const SizedBox(height: 10),
                            Wrap(
                              spacing: 12,
                              runSpacing: 10,
                              children: [
                                SizedBox(
                                  width: 280,
                                  child: TextField(
                                    controller: _emailCtrl,
                                    keyboardType: TextInputType.emailAddress,
                                    decoration: const InputDecoration(
                                      labelText: 'Owner Email',
                                      isDense: true,
                                      border: OutlineInputBorder(),
                                    ),
                                  ),
                                ),
                                SizedBox(
                                  width: 220,
                                  child: TextField(
                                    controller: _passwordCtrl,
                                    obscureText: true,
                                    onSubmitted: (_) => _signInWithEmail(),
                                    decoration: const InputDecoration(
                                      labelText: 'Password (min 6 chars)',
                                      isDense: true,
                                      border: OutlineInputBorder(),
                                    ),
                                  ),
                                ),
                                FilledButton.icon(
                                  onPressed: _busy ? null : _signInWithEmail,
                                  icon: const Icon(Icons.login),
                                  label: const Text('Sign In / Initialize'),
                                ),
                                OutlinedButton.icon(
                                  onPressed: _busy ? null : _signInWithGoogle,
                                  icon: const Icon(Icons.account_circle_outlined),
                                  label: const Text('Google Sign-In'),
                                ),
                                TextButton(
                                  onPressed: _busy
                                      ? null
                                      : () async {
                                          final email = _emailCtrl.text.trim();
                                          if (email.isEmpty) return;
                                          try {
                                            await widget.repository
                                                .sendPasswordReset(email);
                                            setState(() {
                                              _statusMessage =
                                                  'Password reset email sent to $email.';
                                            });
                                          } catch (e) {
                                            setState(() {
                                              _statusMessage = 'Reset failed: $e';
                                            });
                                          }
                                        },
                                  child: const Text('Reset Password'),
                                ),
                              ],
                            ),
                          ],
                        ],
                      ),
                    ),
                  ),
                  const SizedBox(height: 16),
                  Card(
                    child: Padding(
                      padding: const EdgeInsets.all(16),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          const Text(
                            'Pipeline Controls & Weekly Dispatch',
                            style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
                          ),
                          const SizedBox(height: 6),
                          const Text(
                            'Trigger an immediate ALeRCE/SkyBoT ingest cycle, preview the Weekly Sky Dispatch (article + podcast script), or broadcast via Resend & FCM.',
                            style: TextStyle(fontSize: 12, color: SkyColors.textSecondary),
                          ),
                          const SizedBox(height: 14),
                          Wrap(
                            spacing: 12,
                            runSpacing: 12,
                            children: [
                              FilledButton.icon(
                                onPressed: (_busy || user == null)
                                    ? null
                                    : () => _invoke('trigger_ingest'),
                                icon: const Icon(Icons.cloud_download_outlined),
                                label: const Text('Run Daily Ingest (Rubin + ZTF)'),
                              ),
                              OutlinedButton.icon(
                                onPressed: (_busy || user == null)
                                    ? null
                                    : () => _invoke('trigger_identify'),
                                icon: const Icon(Icons.radar),
                                label: const Text('Run Asteroid Identification (SkyBoT)'),
                              ),
                              OutlinedButton.icon(
                                onPressed: (_busy || user == null)
                                    ? null
                                    : () => _invoke('preview_digest'),
                                icon: const Icon(Icons.podcasts),
                                label: const Text('Preview Weekly Dispatch & Podcast'),
                              ),
                              OutlinedButton.icon(
                                onPressed: (_busy || user == null)
                                    ? null
                                    : () => _invoke('send_digest'),
                                icon: const Icon(Icons.send_outlined),
                                label: const Text('Send Weekly Digest & Broadcast FCM'),
                              ),
                            ],
                          ),
                        ],
                      ),
                    ),
                  ),
                  if (_runs.isNotEmpty) ...[
                    const SizedBox(height: 20),
                    const Text(
                      'RECENT INGEST RUNS (ADMIN_RUNS)',
                      style: TextStyle(
                        fontSize: 12,
                        fontWeight: FontWeight.bold,
                        letterSpacing: 1.1,
                        color: SkyColors.textSecondary,
                      ),
                    ),
                    const SizedBox(height: 8),
                    ..._runs.map((r) {
                      final status = '${r['status'] ?? 'unknown'}';
                      final seen = (r['objects_seen'] as num?)?.toInt() ?? 0;
                      final enriched = (r['objects_enriched'] as num?)?.toInt() ?? 0;
                      final dets = (r['detections_upserted'] as num?)?.toInt() ?? 0;
                      final durMs = (r['duration_ms'] as num?)?.toInt() ?? 0;
                      final started = '${r['started_at'] ?? ''}';
                      return Card(
                        margin: const EdgeInsets.only(bottom: 8),
                        child: ListTile(
                          leading: Icon(
                            status == 'success'
                                ? Icons.check_circle_outline
                                : Icons.info_outline,
                            color: status == 'success'
                                ? const Color(0xFF3DDC97)
                                : SkyColors.accentAmber,
                          ),
                          title: Text(
                            'Status: ${status.toUpperCase()} · '
                            '${formatCount(seen)} objects · ${formatCount(enriched)} enriched (${formatCount(dets)} detections)',
                            style: const TextStyle(
                              fontSize: 13,
                              fontWeight: FontWeight.bold,
                            ),
                          ),
                          subtitle: Text(
                            '$started · ${(durMs / 1000.0).toStringAsFixed(1)}s · '
                            'trigger: ${r['trigger'] ?? 'cron'}',
                            style: const TextStyle(fontSize: 12),
                          ),
                        ),
                      );
                    }),
                  ],
                  if (_audits.isNotEmpty) ...[
                    const SizedBox(height: 16),
                    const Text(
                      'RECENT ADMIN AUDIT LOG',
                      style: TextStyle(
                        fontSize: 12,
                        fontWeight: FontWeight.bold,
                        letterSpacing: 1.1,
                        color: SkyColors.textSecondary,
                      ),
                    ),
                    const SizedBox(height: 8),
                    ..._audits.map((a) {
                      return Card(
                        margin: const EdgeInsets.only(bottom: 6),
                        child: ListTile(
                          dense: true,
                          leading: const Icon(Icons.history, size: 18),
                          title: Text(
                            '${a['action']} → ${a['target'] ?? 'all'}',
                            style: const TextStyle(fontWeight: FontWeight.w600),
                          ),
                          subtitle: Text('${a['actor']} · ${a['occurred_at']}'),
                        ),
                      );
                    }),
                  ],
                ],
              ),
            ),
          ),
        );
      },
    );
  }
}
