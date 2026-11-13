import 'package:firebase_core/firebase_core.dart';
import 'package:flutter/material.dart';
import 'package:flutter_web_plugins/url_strategy.dart';

import 'data/firestore_repository.dart';
import 'firebase_options.dart';
import 'ui/router.dart';
import 'ui/theme.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  usePathUrlStrategy();
  await Firebase.initializeApp(options: DefaultFirebaseOptions.currentPlatform);
  final repository = SkyAlertsRepository();
  runApp(SkyAlertsApp(repository: repository));
}

class SkyAlertsApp extends StatefulWidget {
  const SkyAlertsApp({super.key, required this.repository});

  final SkyAlertsRepository repository;

  @override
  State<SkyAlertsApp> createState() => _SkyAlertsAppState();
}

class _SkyAlertsAppState extends State<SkyAlertsApp> {
  late final _router = buildAppRouter(widget.repository);

  @override
  Widget build(BuildContext context) {
    return ValueListenableBuilder<bool>(
      valueListenable: redNightModeNotifier,
      builder: (context, redNightMode, _) {
        return MaterialApp.router(
          title: 'Sky Alerts',
          debugShowCheckedModeBanner: false,
          theme: buildSkyAlertsTheme(redNightMode: redNightMode),
          routerConfig: _router,
        );
      },
    );
  }
}
