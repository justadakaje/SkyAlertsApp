import 'package:firebase_core/firebase_core.dart' show FirebaseOptions;
import 'package:flutter/foundation.dart'
    show defaultTargetPlatform, kIsWeb, TargetPlatform;

class DefaultFirebaseOptions {
  static FirebaseOptions get currentPlatform {
    if (kIsWeb) {
      return web;
    }
    switch (defaultTargetPlatform) {
      case TargetPlatform.android:
        return android;
      case TargetPlatform.iOS:
        return ios;
      default:
        return web;
    }
  }

  static const FirebaseOptions web = FirebaseOptions(
    apiKey: 'AIzaSyDaz54Bg08_Ctb4-hyFOmSTz35mb9QCfsQ',
    appId: '1:792163391320:web:aadd2e08a009252eaa372d',
    messagingSenderId: '792163391320',
    projectId: 'skyalerts-app',
    authDomain: 'sky.henseler.app',
    storageBucket: 'skyalerts-app.firebasestorage.app',
  );

  static const FirebaseOptions android = FirebaseOptions(
    apiKey: 'AIzaSyC_Goyx8S-pa4MRUi_mNnMh5heAtdTXts4',
    appId: '1:792163391320:android:4a426d2c50f1ae4faa372d',
    messagingSenderId: '792163391320',
    projectId: 'skyalerts-app',
    storageBucket: 'skyalerts-app.firebasestorage.app',
  );

  static const FirebaseOptions ios = FirebaseOptions(
    apiKey: 'AIzaSyAeK9Kl0sJ3R04jPBzCS9ilawHwJ7Royfs',
    appId: '1:792163391320:ios:821869b171a9f9c1aa372d',
    messagingSenderId: '792163391320',
    projectId: 'skyalerts-app',
    storageBucket: 'skyalerts-app.firebasestorage.app',
    iosBundleId: 'app.henseler.skyalerts',
  );
}
