import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:cloud_functions/cloud_functions.dart';
import 'package:firebase_auth/firebase_auth.dart';
import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter/foundation.dart';

import '../domain/format.dart';
import '../domain/lightcurve.dart';
import '../domain/trends.dart';

class SsoMatchInfo {
  const SsoMatchInfo({
    required this.status,
    this.ssoName,
    this.ssoNumber,
    this.ssoClass,
    this.sepArcsec,
    this.predictedMag,
    this.obsMjd,
    this.geoDistAu,
    this.helioDistAu,
  });

  factory SsoMatchInfo.fromMap(Map<String, dynamic> map) {
    return SsoMatchInfo(
      status: (map['status'] as String?) ?? 'no_match',
      ssoName: (map['sso_name'] ?? map['object_name']) as String?,
      ssoNumber: ((map['sso_number'] ?? map['object_number']) as num?)?.toInt(),
      ssoClass: (map['sso_class'] ?? map['object_class']) as String?,
      sepArcsec: (map['sep_arcsec'] as num?)?.toDouble(),
      predictedMag: ((map['predicted_mag'] ?? map['v_mag']) as num?)?.toDouble(),
      obsMjd: ((map['obs_mjd'] ?? map['epoch_mjd']) as num?)?.toDouble(),
      geoDistAu: (map['geo_dist_au'] as num?)?.toDouble(),
      helioDistAu: (map['helio_dist_au'] as num?)?.toDouble(),
    );
  }

  final String status;
  final String? ssoName;
  final int? ssoNumber;
  final String? ssoClass;
  final double? sepArcsec;
  final double? predictedMag;
  final double? obsMjd;
  final double? geoDistAu;
  final double? helioDistAu;

  bool get isMatched => status == 'matched' && ssoName != null && ssoName!.isNotEmpty;
}

class CatalogObject {
  const CatalogObject({
    required this.survey,
    required this.oid,
    this.meanRa,
    this.meanDec,
    this.firstMjd,
    this.lastMjd,
    this.nDetections = 0,
    this.topClass,
    this.topClassifier,
    this.topClassifierVersion,
    this.topProbability,
    this.peakMag,
    this.peakBand,
    this.latestMag,
    this.latestBand,
    this.latestMjd,
    this.displayName,
    this.targetKind,
    this.sourceFeed,
    this.magNote,
    this.horizonsUrl,
    this.tier = 1,
    this.isArtifact = false,
    this.sso,
  });

  factory CatalogObject.fromMap(Map<String, dynamic> map) {
    final ssoRaw = map['sso'];
    return CatalogObject(
      survey: (map['survey'] as String?) ?? 'ztf',
      oid: (map['oid'] as String?) ?? '',
      meanRa: _asDouble(map['meanra'] ?? map['ra_deg']),
      meanDec: _asDouble(map['meandec'] ?? map['dec_deg']),
      firstMjd: _asDouble(map['firstmjd'] ?? map['first_mjd']),
      lastMjd: _asDouble(map['lastmjd'] ?? map['last_mjd']),
      nDetections: _asInt(map['ndet'] ?? map['n_detections']) ?? 0,
      topClass: map['top_class'] as String?,
      topClassifier: (map['top_classifier'] ?? map['classifier_name']) as String?,
      topClassifierVersion:
          (map['top_classifier_version'] ?? map['classifier_version']) as String?,
      topProbability: _asDouble(map['top_probability']),
      peakMag: _asDouble(map['peak_mag']),
      peakBand: map['peak_band'] as String?,
      latestMag: _asDouble(map['latest_mag']),
      latestBand: map['latest_band'] as String?,
      latestMjd: _asDouble(map['latest_mjd']),
      displayName: map['display_name'] as String?,
      targetKind: map['target_kind'] as String?,
      sourceFeed: map['source_feed'] as String?,
      magNote: map['mag_note'] as String?,
      horizonsUrl: map['horizons_url'] as String?,
      tier: _parseTier(map['tier']),
      isArtifact: map['is_artifact'] == true,
      sso: ssoRaw is Map ? SsoMatchInfo.fromMap(Map<String, dynamic>.from(ssoRaw)) : null,
    );
  }

  static double? _asDouble(dynamic raw) {
    if (raw is num) return raw.toDouble();
    if (raw is String) return double.tryParse(raw.trim());
    return null;
  }

  static int? _asInt(dynamic raw) {
    if (raw is num) return raw.toInt();
    if (raw is String) return int.tryParse(raw.trim());
    return null;
  }

  static int _parseTier(dynamic raw) {
    if (raw is num) return raw.toInt();
    if (raw is String) {
      if (raw == 'bright') return 0;
      return int.tryParse(raw.trim()) ?? 1;
    }
    return 1;
  }

  final String survey;
  final String oid;
  final double? meanRa;
  final double? meanDec;
  final double? firstMjd;
  final double? lastMjd;
  final int nDetections;
  final String? topClass;
  final String? topClassifier;
  final String? topClassifierVersion;
  final double? topProbability;
  final double? peakMag;
  final String? peakBand;
  final double? latestMag;
  final String? latestBand;
  final double? latestMjd;
  final String? displayName;
  final String? targetKind;
  final String? sourceFeed;
  final String? magNote;
  final String? horizonsUrl;
  final int tier;
  final bool isArtifact;
  final SsoMatchInfo? sso;

  String get docId => '${survey}_$oid';
  double? get effectiveMag => latestMag ?? peakMag;
  String get displayLabel =>
      (displayName != null && displayName!.trim().isNotEmpty) ? displayName!.trim() : oid;
}

/// Deduplicates and sorts split non-artifact and artifact feed queries cleanly.
List<CatalogObject> mergeAndSortCatalogFeed(
  Iterable<CatalogObject> items, {
  required bool newestFirst,
  int? limit,
}) {
  final byId = <String, CatalogObject>{};
  for (final obj in items) {
    byId[obj.docId] = obj;
  }
  final list = byId.values.toList();
  list.sort((a, b) {
    if (!newestFirst) {
      final tierCmp = a.tier.compareTo(b.tier);
      if (tierCmp != 0) return tierCmp;
      final probCmp = (b.topProbability ?? -1.0).compareTo(a.topProbability ?? -1.0);
      if (probCmp != 0) return probCmp;
    }
    final mjdCmp = (b.lastMjd ?? -1.0).compareTo(a.lastMjd ?? -1.0);
    if (mjdCmp != 0) return mjdCmp;
    return a.docId.compareTo(b.docId);
  });
  if (limit != null && list.length > limit) {
    return list.sublist(0, limit);
  }
  return list;
}

class ClassificationEntry {
  const ClassificationEntry({
    required this.classifier,
    required this.version,
    required this.className,
    required this.probability,
    this.ranking,
  });

  factory ClassificationEntry.fromMap(Map<String, dynamic> map) {
    return ClassificationEntry(
      classifier: (map['classifier'] ?? map['classifier_name'] ?? '') as String,
      version: (map['version'] ?? map['classifier_version'] ?? '') as String,
      className: (map['class_name'] ?? '') as String,
      probability: (map['probability'] as num?)?.toDouble() ?? 0.0,
      ranking: (map['ranking'] as num?)?.toInt(),
    );
  }

  final String classifier;
  final String version;
  final String className;
  final double probability;
  final int? ranking;
}

class ObjectDetailBundle {
  const ObjectDetailBundle({
    required this.object,
    required this.detections,
    required this.classifications,
  });

  final CatalogObject object;
  final List<DetectionPoint> detections;
  final List<ClassificationEntry> classifications;
}

class OverviewRollup {
  const OverviewRollup({
    required this.updatedAt,
    required this.todayMjd,
    required this.totalObjects,
    required this.enrichedObjects,
    required this.newThisWeek,
    required this.transientsThisWeek,
    required this.highlights,
    required this.windowClassCounts,
    required this.matchedAsteroids,
    required this.solarEphemerides,
    this.weeklyDispatchSubject,
    this.weeklyDispatchMarkdown,
    this.weeklyDispatchPodcast,
  });

  factory OverviewRollup.fromMap(Map<String, dynamic> map) {
    final totals = map['totals'] is Map
        ? Map<String, dynamic>.from(map['totals'] as Map)
        : <String, dynamic>{};
    final hlRaw = (map['highlights'] as List?) ?? const [];
    final highlightRows = hlRaw
        .whereType<Map>()
        .map((m) => Map<String, dynamic>.from(m))
        .toList();

    final wcRaw = map['window_class_counts'] is Map
        ? Map<String, dynamic>.from(map['window_class_counts'] as Map)
        : <String, dynamic>{};
    final windowCounts = <String, Map<String, int>>{};
    for (final entry in wcRaw.entries) {
      if (entry.value is Map) {
        final inner = <String, int>{};
        for (final ce in (entry.value as Map).entries) {
          inner['${ce.key}'] = (ce.value as num?)?.toInt() ?? 0;
        }
        windowCounts[entry.key] = inner;
      }
    }

    final maRaw = (map['matched_asteroids'] as List?) ?? const [];
    final ephemRaw = map['solar_ephemerides'] is Map
        ? Map<String, dynamic>.from(map['solar_ephemerides'] as Map)
        : <String, dynamic>{};
    final wdRaw = map['weekly_dispatch'] is Map
        ? Map<String, dynamic>.from(map['weekly_dispatch'] as Map)
        : <String, dynamic>{};

    return OverviewRollup(
      updatedAt: (map['updated_at'] as String?) ?? '',
      todayMjd: (map['today_mjd'] as num?)?.toInt() ?? 61355,
      totalObjects: ((map['total_objects'] ?? totals['objects']) as num?)?.toInt() ?? 0,
      enrichedObjects: (totals['enriched_objects'] as num?)?.toInt() ?? 0,
      newThisWeek: (totals['new_this_week'] as num?)?.toInt() ?? 0,
      transientsThisWeek: (totals['transients_this_week'] as num?)?.toInt() ?? 0,
      highlights: pickHomeHighlights(highlightRows),
      windowClassCounts: windowCounts,
      matchedAsteroids: maRaw
          .whereType<Map>()
          .map((m) => Map<String, dynamic>.from(m))
          .toList(),
      solarEphemerides: ephemRaw,
      weeklyDispatchSubject: wdRaw['subject'] as String?,
      weeklyDispatchMarkdown: wdRaw['markdown'] as String?,
      weeklyDispatchPodcast: wdRaw['podcast'] as String?,
    );
  }

  final String updatedAt;
  final int todayMjd;
  final int totalObjects;
  final int enrichedObjects;
  final int newThisWeek;
  final int transientsThisWeek;
  final List<HighlightCardModel> highlights;
  final Map<String, Map<String, int>> windowClassCounts;
  final List<Map<String, dynamic>> matchedAsteroids;
  final Map<String, dynamic> solarEphemerides;
  final String? weeklyDispatchSubject;
  final String? weeklyDispatchMarkdown;
  final String? weeklyDispatchPodcast;
}

class TrendsRollup {
  const TrendsRollup({
    required this.todayMjd,
    required this.newThisWeek,
    required this.newLastWeek,
    required this.transientsThisWeek,
    required this.transientsLastWeek,
    required this.dailyCounts,
    required this.dailySurveyCounts,
  });

  factory TrendsRollup.fromMap(Map<String, dynamic> map) {
    final comp = map['comparison'] is Map
        ? Map<String, dynamic>.from(map['comparison'] as Map)
        : <String, dynamic>{};
    final dcRaw = (map['daily_counts'] as List?) ?? const [];
    final dsRaw = (map['daily_survey_counts'] ?? map['by_day_survey']) as List? ?? const [];

    return TrendsRollup(
      todayMjd: (map['today_mjd'] as num?)?.toInt() ?? 61355,
      newThisWeek: (comp['new_this_week'] as num?)?.toInt() ?? 0,
      newLastWeek: (comp['new_last_week'] as num?)?.toInt() ?? 0,
      transientsThisWeek: (comp['transients_this_week'] as num?)?.toInt() ?? 0,
      transientsLastWeek: (comp['transients_last_week'] as num?)?.toInt() ?? 0,
      dailyCounts: dcRaw
          .whereType<Map>()
          .map((m) => DayClassCount.fromMap(Map<String, dynamic>.from(m)))
          .toList(),
      dailySurveyCounts: dsRaw
          .whereType<Map>()
          .map((m) => DaySurveyCount.fromMap(Map<String, dynamic>.from(m)))
          .toList(),
    );
  }

  final int todayMjd;
  final int newThisWeek;
  final int newLastWeek;
  final int transientsThisWeek;
  final int transientsLastWeek;
  final List<DayClassCount> dailyCounts;
  final List<DaySurveyCount> dailySurveyCounts;
}

class UserAlertPreferences {
  const UserAlertPreferences({
    this.notifyTransients = true,
    this.notifySolarMatched = false,
    this.notifyWeeklyDispatch = true,
    this.minConfidence = 0.80,
    this.maxPeakMag,
  });

  factory UserAlertPreferences.fromMap(Map<String, dynamic> map) {
    final topics = map['topics'] is Map
        ? Map<String, dynamic>.from(map['topics'] as Map)
        : const <String, dynamic>{};
    return UserAlertPreferences(
      notifyTransients: (topics['transients'] ?? map['notify_transients']) != false,
      notifySolarMatched: (topics['solar_matched'] ?? map['notify_solar_matched']) == true,
      notifyWeeklyDispatch: (topics['weekly_dispatch'] ?? map['notify_weekly_dispatch']) != false,
      minConfidence: (map['min_confidence'] as num?)?.toDouble() ?? 0.80,
      maxPeakMag: (map['max_peak_mag'] as num?)?.toDouble(),
    );
  }

  final bool notifyTransients;
  final bool notifySolarMatched;
  final bool notifyWeeklyDispatch;
  final double minConfidence;
  final double? maxPeakMag;

  Map<String, dynamic> toMap() => {
        'topics': {
          'transients': notifyTransients,
          'solar_matched': notifySolarMatched,
          'weekly_dispatch': notifyWeeklyDispatch,
        },
        'min_confidence': minConfidence,
        'max_peak_mag': maxPeakMag,
      };
}

class SkyAlertsRepository {
  SkyAlertsRepository({
    FirebaseFirestore? firestore,
    FirebaseAuth? auth,
    FirebaseMessaging? messaging,
    FirebaseFunctions? functions,
  })  : _db = firestore ?? FirebaseFirestore.instance,
        _auth = auth ?? FirebaseAuth.instance,
        _messaging = messaging ?? FirebaseMessaging.instance,
        _functions = functions ?? FirebaseFunctions.instance;

  final FirebaseFirestore _db;
  final FirebaseAuth _auth;
  final FirebaseMessaging _messaging;
  final FirebaseFunctions _functions;

  User? get currentUser => _auth.currentUser;
  Stream<User?> get authStateChanges => _auth.authStateChanges();

  /// Ensures the client has an anonymous Firebase session (or existing signed-in user).
  Future<User> ensureSignedInAnonymously() async {
    final existing = _auth.currentUser;
    if (existing != null) return existing;
    final cred = await _auth.signInAnonymously();
    return cred.user!;
  }

  Future<UserCredential> signInWithGoogle() async {
    final provider = GoogleAuthProvider();
    if (kIsWeb) {
      return _auth.signInWithPopup(provider);
    }
    return _auth.signInWithProvider(provider);
  }

  /// Links Google to an anonymous session so bookmarks/settings survive upgrade.
  Future<UserCredential> linkOrSignInWithGoogle() async {
    final user = _auth.currentUser;
    final provider = GoogleAuthProvider();
    if (user != null && user.isAnonymous) {
      try {
        return kIsWeb
            ? await user.linkWithPopup(provider)
            : await user.linkWithProvider(provider);
      } on FirebaseAuthException catch (e) {
        if (e.code == 'credential-already-in-use' || e.code == 'email-already-in-use') {
          return signInWithGoogle();
        }
        rethrow;
      }
    }
    return signInWithGoogle();
  }

  /// Links Sign in with Apple (required on iOS, Guideline 4.8) or signs in.
  Future<UserCredential> linkOrSignInWithApple() async {
    final user = _auth.currentUser;
    final provider = AppleAuthProvider();
    if (user != null && user.isAnonymous) {
      try {
        return kIsWeb
            ? await user.linkWithPopup(provider)
            : await user.linkWithProvider(provider);
      } on FirebaseAuthException catch (e) {
        if (e.code == 'credential-already-in-use' || e.code == 'email-already-in-use') {
          return kIsWeb
              ? await _auth.signInWithPopup(provider)
              : await _auth.signInWithProvider(provider);
        }
        rethrow;
      }
    }
    return kIsWeb ? _auth.signInWithPopup(provider) : _auth.signInWithProvider(provider);
  }

  /// Permanently deletes synced bookmarks, user profile doc, and Firebase Auth user.
  Future<void> deleteUserAccountAndData() async {
    final user = _auth.currentUser;
    if (user == null) return;
    final userRef = _db.collection('users').doc(user.uid);
    final bookmarksSnap = await userRef.collection('bookmarks').get();
    for (final doc in bookmarksSnap.docs) {
      await doc.reference.delete();
    }
    await userRef.delete();
    await user.delete();
  }

  Future<UserCredential> signInWithEmail(String email, String password) async {
    try {
      return await _auth.signInWithEmailAndPassword(
        email: email.trim(),
        password: password,
      );
    } on FirebaseAuthException catch (e) {
      if (e.code == 'user-not-found' || e.code == 'invalid-credential') {
        try {
          return await _auth.createUserWithEmailAndPassword(
            email: email.trim(),
            password: password,
          );
        } catch (_) {
          rethrow;
        }
      }
      rethrow;
    }
  }

  Future<void> sendPasswordReset(String email) =>
      _auth.sendPasswordResetEmail(email: email.trim());

  Future<void> signOut() => _auth.signOut();

  /// Single document read (`rollups/overview`) for the Home, Stats, and Solar System screens.
  Future<OverviewRollup> fetchOverview() async {
    final snap = await _db.collection('rollups').doc('overview').get();
    return OverviewRollup.fromMap(snap.data() ?? const {});
  }

  /// Single document read (`rollups/trends_90d`) for the Trends screen.
  Future<TrendsRollup> fetchTrends() async {
    final snap = await _db.collection('rollups').doc('trends_90d').get();
    return TrendsRollup.fromMap(snap.data() ?? const {});
  }

  /// Paginated catalog feed query (always uses indexed `is_artifact` slices so
  /// toggling "Include artifacts" works without waiting on extra composite builds).
  Future<List<CatalogObject>> fetchCatalogFeed({
    String? survey,
    String? topClass,
    bool includeArtifacts = false,
    bool newestFirst = false,
    int limit = 40,
  }) async {
    if (!includeArtifacts) {
      return _fetchCatalogFeedByArtifactFlag(
        isArtifact: false,
        survey: survey,
        topClass: topClass,
        newestFirst: newestFirst,
        limit: limit,
      );
    }
    final slices = await Future.wait([
      _fetchCatalogFeedByArtifactFlag(
        isArtifact: false,
        survey: survey,
        topClass: topClass,
        newestFirst: newestFirst,
        limit: limit,
      ),
      _fetchCatalogFeedByArtifactFlag(
        isArtifact: true,
        survey: survey,
        topClass: topClass,
        newestFirst: newestFirst,
        limit: limit,
      ),
    ]);
    return mergeAndSortCatalogFeed(
      [...slices[0], ...slices[1]],
      newestFirst: newestFirst,
      limit: limit,
    );
  }

  Future<List<CatalogObject>> _fetchCatalogFeedByArtifactFlag({
    required bool isArtifact,
    String? survey,
    String? topClass,
    required bool newestFirst,
    required int limit,
  }) async {
    Query<Map<String, dynamic>> query = _db
        .collection('objects')
        .where('is_artifact', isEqualTo: isArtifact);
    if (survey != null && survey.isNotEmpty) {
      query = query.where('survey', isEqualTo: survey);
    }
    if (topClass != null && topClass.isNotEmpty) {
      query = query.where('top_class', isEqualTo: topClass);
    }
    if (newestFirst) {
      query = query.orderBy('lastmjd', descending: true);
    } else {
      query = query
          .orderBy('tier')
          .orderBy('top_probability', descending: true)
          .orderBy('lastmjd', descending: true);
    }
    final snap = await query.limit(limit).get();
    return snap.docs.map((d) => CatalogObject.fromMap(d.data())).toList();
  }

  /// Fetches bright magnitude-measured targets plus recent non-artifact objects
  /// for the on-device Backyard Planner.
  Future<List<CatalogObject>> fetchBackyardCandidates({
    int brightLimit = 100,
    int recentLimit = 60,
  }) async {
    final results = await Future.wait([
      _db.collection('objects').orderBy('latest_mag').limit(brightLimit).get(),
      fetchCatalogFeed(newestFirst: true, limit: recentLimit),
    ]);
    final brightSnap = results[0] as QuerySnapshot<Map<String, dynamic>>;
    final recentList = results[1] as List<CatalogObject>;

    final byId = <String, CatalogObject>{};
    for (final doc in brightSnap.docs) {
      final obj = CatalogObject.fromMap(doc.data());
      if (!obj.isArtifact) {
        byId[obj.docId] = obj;
      }
    }
    for (final obj in recentList) {
      byId.putIfAbsent(obj.docId, () => obj);
    }
    return byId.values.toList();
  }

  /// 2-document read for the Object Detail page (`objects/{id}` + `detail/enrichment`).
  Future<ObjectDetailBundle?> fetchObjectDetail(String survey, String oid) async {
    final docId = '${survey}_$oid';
    final objRef = _db.collection('objects').doc(docId);
    final results = await Future.wait([
      objRef.get(),
      objRef.collection('detail').doc('enrichment').get(),
    ]);
    final objSnap = results[0];
    if (!objSnap.exists || objSnap.data() == null) return null;
    final catalogObj = CatalogObject.fromMap(objSnap.data()!);

    final enrData = results[1].data() ?? const <String, dynamic>{};
    final detsRaw = (enrData['detections'] as List?) ?? const [];
    final clssRaw = (enrData['classifications'] as List?) ?? const [];

    return ObjectDetailBundle(
      object: catalogObj,
      detections: detsRaw
          .whereType<Map>()
          .map((m) => DetectionPoint.fromMap(Map<String, dynamic>.from(m)))
          .toList(),
      classifications: clssRaw
          .whereType<Map>()
          .map((m) => ClassificationEntry.fromMap(Map<String, dynamic>.from(m)))
          .toList(),
    );
  }

  /// Streams the signed-in user's bookmarked objects (`users/{uid}/bookmarks`).
  Stream<List<Map<String, dynamic>>> watchBookmarks() {
    final user = _auth.currentUser;
    if (user == null) return Stream.value(const []);
    return _db
        .collection('users')
        .doc(user.uid)
        .collection('bookmarks')
        .orderBy('created_at', descending: true)
        .snapshots()
        .map((s) => s.docs.map((d) => d.data()).toList());
  }

  Future<void> toggleBookmark(CatalogObject obj) async {
    await ensureSignedInAnonymously();
    final user = _auth.currentUser;
    if (user == null) return;
    final ref = _db
        .collection('users')
        .doc(user.uid)
        .collection('bookmarks')
        .doc(obj.docId);
    final snap = await ref.get();
    if (snap.exists) {
      await ref.delete();
    } else {
      await ref.set({
        'object_key': obj.docId,
        'survey': obj.survey,
        'oid': obj.oid,
        'top_class': obj.topClass,
        if (obj.sso?.ssoName != null) 'sso_name': obj.sso!.ssoName,
        if (obj.sso?.ssoNumber != null) 'sso_number': obj.sso!.ssoNumber,
        'created_at': FieldValue.serverTimestamp(),
      });
    }
  }

  /// Saves user alert thresholds and updates FCM topic subscriptions on iOS/Android.
  Future<void> saveAlertPreferences(
    UserAlertPreferences prefs, {
    double? roundedLat,
    double? roundedLon,
    String? scopePreset,
  }) async {
    if (!kIsWeb) {
      await _messaging.requestPermission();
      if (prefs.notifyTransients) {
        await _messaging.subscribeToTopic('transients');
      } else {
        await _messaging.unsubscribeFromTopic('transients');
      }
      if (prefs.notifySolarMatched) {
        await _messaging.subscribeToTopic('solar_matched');
      } else {
        await _messaging.unsubscribeFromTopic('solar_matched');
      }
      if (prefs.notifyWeeklyDispatch) {
        await _messaging.subscribeToTopic('weekly_dispatch');
      } else {
        await _messaging.unsubscribeFromTopic('weekly_dispatch');
      }
    }

    final user = _auth.currentUser ?? await ensureSignedInAnonymously();
    String? token;
    try {
      token = await _messaging.getToken();
    } catch (_) {
      token = null;
    }
    await _db.collection('users').doc(user.uid).set(
      {
        ...prefs.toMap(),
        if (roundedLat != null) 'rounded_lat': (roundedLat * 10.0).round() / 10.0,
        if (roundedLon != null) 'rounded_lon': (roundedLon * 10.0).round() / 10.0,
        if (scopePreset != null) 'scope_preset': scopePreset,
        if (token != null) 'fcm_tokens': FieldValue.arrayUnion([token]),
        'updated_at': FieldValue.serverTimestamp(),
      },
      SetOptions(merge: true),
    );
  }

  /// Admin Callable Cloud Functions (require `admin == true` custom claim or owner email).
  Future<Map<String, dynamic>> callAdminFunction(
    String name, [
    Map<String, dynamic>? payload,
  ]) async {
    final callable = _functions.httpsCallable(
      name,
      options: HttpsCallableOptions(timeout: const Duration(seconds: 540)),
    );
    final res = await callable.call<Map<String, dynamic>>(payload ?? const {});
    return Map<String, dynamic>.from(res.data);
  }

  /// Fetches recent ingest runs (`admin_runs`) for signed-in admins.
  Future<List<Map<String, dynamic>>> fetchRecentAdminRuns({int limit = 8}) async {
    final snap = await _db
        .collection('admin_runs')
        .orderBy('id', descending: true)
        .limit(limit)
        .get();
    return snap.docs.map((d) => d.data()).toList();
  }

  /// Fetches recent admin audit logs (`audit_log`) for signed-in admins.
  Future<List<Map<String, dynamic>>> fetchRecentAuditLogs({int limit = 10}) async {
    final snap = await _db
        .collection('audit_log')
        .orderBy('occurred_at', descending: true)
        .limit(limit)
        .get();
    return snap.docs.map((d) => d.data()).toList();
  }
}
