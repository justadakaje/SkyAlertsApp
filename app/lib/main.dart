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

class SkyAlertsApp extends StatelessWidget {
  const SkyAlertsApp({super.key, required this.repository});

  final SkyAlertsRepository repository;

  @override
  Widget build(BuildContext context) {
    final router = buildAppRouter(repository);
    return MaterialApp.router(
      title: 'Sky Alerts',
      debugShowCheckedModeBanner: false,
      theme: buildSkyAlertsTheme(),
      routerConfig: router,
    );
  }
}
