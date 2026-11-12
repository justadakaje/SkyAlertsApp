# Firebase + Flutter Migration & Cutover Guide

This document covers the architecture, backfill procedure, deployment commands, and DNS cutover checklist for migrating **Sky Alerts (`sky.henseler.app`)** from Vercel + Neon Postgres + Next.js to **Firebase Hosting + Cloud Firestore + Cloud Functions (2nd Gen, Python 3.12) + Unified Flutter (iOS, Android, Web)** on a **$0/month permanent free tier**.

---

## 1. Architecture Summary

| Layer | Component | Path | Free-Tier Budget Guardrail |
|---|---|---|---|
| **Database** | Cloud Firestore | `firestore.rules`, `firestore.indexes.json` | Two-tier documents (`objects/{id}` ~1 KB + `detail/enrichment` ~25 KB) and 1-read rollups (`rollups/overview`, `rollups/trends_90d`) keep reads well under 50,000/day and storage under 1 GiB. |
| **Backend Jobs** | Cloud Functions (2nd Gen, Python 3.12) | `functions/` | Consolidated into **2 Cloud Scheduler jobs** (`daily_ingest_and_identify` at `06:17 UTC` and `weekly_digest_and_broadcast` at `14:23 UTC` Sundays), staying within Google Cloud Scheduler's 3-free-jobs/month allowance. |
| **Push Alerts** | Firebase Cloud Messaging (FCM) | `functions/skyalerts_functions/notifications.py` | Unlimited free topic (`transients`, `solar_matched`, `weekly_dispatch`) & per-user token notifications (`bookmarks` + custom confidence/magnitude thresholds). |
| **Client App** | Unified Flutter (iOS, Android, Web) | `app/` | Single codebase compiled to iOS, Android, and static Web (`app/build/web`) served from Firebase Hosting. |

---

## 2. Step-by-Step Deployment & Backfill

### Step 1 — Link Firebase Project & Deploy Firestore Rules/Indexes
```bash
firebase login
firebase use skyalerts-app
firebase deploy --only firestore:rules,firestore:indexes
```

### Step 2 — Run Idempotent Neon Postgres → Cloud Firestore Backfill
Before switching traffic, migrate all existing objects, detections, classifications, IMCCE SkyBoT matches, ingest run history, and audit logs from Neon Postgres into Cloud Firestore:
```bash
cd functions
DATABASE_URL="postgresql://..." GCLOUD_PROJECT="skyalerts-app" \
  uv run python -m skyalerts_functions.backfill
```
This script is idempotent (`merge=True`) and immediately computes `rollups/overview` and `rollups/trends_90d`.

### Step 3 — Deploy Python 3.12 Cloud Functions
Vendor or install `ingest` and `digest` alongside `functions` and deploy:
```bash
firebase deploy --only functions
```

### Step 4 — Build & Deploy Flutter Web to Firebase Hosting
```bash
cd app
flutter pub get
flutter test
flutter build web --release
cd ..
firebase deploy --only hosting
```

### Step 5 — DNS Cutover (`sky.henseler.app`)
1. Verify the Firebase Hosting preview URL (`https://skyalerts-app.web.app`) renders `/`, `/objects/:survey/:oid`, `/solar-system`, `/trends`, `/saved`, and `/admin`.
2. In Firebase Console → Hosting → Add custom domain `sky.henseler.app` and update DNS records from Vercel to Firebase Hosting.
3. Once DNS propagation completes and `daily_ingest_and_identify` has succeeded for 7 consecutive days, decommission the Vercel project and Neon database.
