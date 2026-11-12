import 'package:flutter/material.dart';

import '../data/firestore_repository.dart';
import 'theme.dart';

class AdminScreen extends StatefulWidget {
  const AdminScreen({super.key, required this.repository});

  final SkyAlertsRepository repository;

  @override
  State<AdminScreen> createState() => _AdminScreenState();
}

class _AdminScreenState extends State<AdminScreen> {
  String _statusMessage = 'Ready. Actions require an owner account with the admin=true claim.';
  bool _busy = false;

  Future<void> _invoke(String callableName, [Map<String, dynamic>? payload]) async {
    setState(() {
      _busy = true;
      _statusMessage = 'Running $callableName…';
    });
    try {
      final res = await widget.repository.callAdminFunction(callableName, payload);
      if (!mounted) return;
      setState(() {
        _busy = false;
        _statusMessage = '$callableName succeeded: $res';
      });
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
    final user = widget.repository.currentUser;
    return Scaffold(
      appBar: AppBar(title: const Text('Admin · Pipeline Controls & Digest Dispatch')),
      body: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 880),
          child: ListView(
            padding: const EdgeInsets.all(16),
            children: [
              Card(
                child: Padding(
                  padding: const EdgeInsets.all(16),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        user != null
                            ? 'Signed in as ${user.email ?? user.uid}'
                            : 'Not signed in (admin callables require owner authentication)',
                        style: const TextStyle(fontWeight: FontWeight.bold),
                      ),
                      const SizedBox(height: 8),
                      Text(
                        _statusMessage,
                        style: const TextStyle(fontSize: 13, color: SkyColors.textSecondary),
                      ),
                      const SizedBox(height: 16),
                      Wrap(
                        spacing: 12,
                        runSpacing: 12,
                        children: [
                          FilledButton.icon(
                            onPressed: _busy ? null : () => _invoke('trigger_ingest'),
                            icon: const Icon(Icons.cloud_download_outlined),
                            label: const Text('Run Daily Ingest (Rubin + ZTF)'),
                          ),
                          OutlinedButton.icon(
                            onPressed: _busy ? null : () => _invoke('trigger_identify'),
                            icon: const Icon(Icons.radar),
                            label: const Text('Run Asteroid Identification (SkyBoT)'),
                          ),
                          OutlinedButton.icon(
                            onPressed: _busy ? null : () => _invoke('preview_digest'),
                            icon: const Icon(Icons.preview_outlined),
                            label: const Text('Preview Weekly Digest'),
                          ),
                          OutlinedButton.icon(
                            onPressed: _busy ? null : () => _invoke('send_digest'),
                            icon: const Icon(Icons.send_outlined),
                            label: const Text('Send Weekly Digest & Broadcast FCM'),
                          ),
                        ],
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
  }
}
