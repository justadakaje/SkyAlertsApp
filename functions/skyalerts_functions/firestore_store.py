"""Cloud Firestore persistence for Sky Alerts ingest, SkyBoT, digest, and 1-read rollups.

Designed so that:
- `objects/{survey}_{oid}` holds the ~1 KB catalog document (including `tier`, `peak_mag`,
  `peak_band`, and embedded `sso` SkyBoT match fields).
- `objects/{survey}_{oid}/detail/enrichment` holds the up-to-200 `detections` and top
  `classifications` arrays (fetched only on the object detail screen).
- `rollups/overview` and `rollups/trends_90d` hold pre-aggregated home highlights, class
  counts, 90-day daily/weekly series, and matched asteroids so `/`, `/trends`, `/stats`,
  and `/solar-system` each load in 1–2 document reads.
"""

from __future__ import annotations

import math
import sys
import time
from collections.abc import Callable, Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

# Allow importing pure domain modules from ../ingest and ../digest locally or in CI.
_REPO_ROOT = Path(__file__).resolve().parents[2]
for _sub in ("ingest", "digest"):
    _p = str(_REPO_ROOT / _sub)
    if _p not in sys.path:
        sys.path.insert(0, _p)

from skyalerts_digest.classes import (  # noqa: E402
    ARTIFACT_CLASS,
    ASTEROID_CLASS,
    GROUPS,
    LOW_PRIORITY_CLASSES,
    TRANSIENT_CLASSES,
    ClassGroup,
    group_of,
)
from skyalerts_digest.podcast import render_podcast  # noqa: E402
from skyalerts_digest.render import render_markdown  # noqa: E402
from skyalerts_digest.select import (  # noqa: E402
    BRIGHTEST_LIMIT,
    HEADLINER_LIMIT,
    SOLAR_EXAMPLE_LIMIT,
    Digest,
    DigestObject,
    GroupCount,
    SolarSystemSection,
    WeekStats,
    datetime_to_mjd,
    normalize_utc,
)
from skyalerts_digest.send import format_subject  # noqa: E402
from skyalerts_ingest.normalize import (  # noqa: E402
    ClassificationRow,
    DetectionRow,
    ObjectRow,
)
from skyalerts_ingest.sso import (  # noqa: E402
    DEFAULT_IDENTIFY_MAX,
    DEFAULT_TIME_BUDGET_S,
    MAX_SEP_ARCSEC,
    IdentifyResult,
    SkyBotClient,
    SkyBotError,
    SkyBotHit,
)
from skyalerts_ingest.store import (  # noqa: E402
    LEASE_SECONDS,
    SKIP_CLASSES,
    TIER1_CLASSES,
    TIER3_CLASSES,
)

BATCH_LIMIT = 400


def object_doc_id(survey: str, oid: str) -> str:
    return f"{survey}_{oid}"


def tier_for_class(top_class: str | None) -> int:
    if top_class in TRANSIENT_CLASSES:
        return 0
    if top_class in LOW_PRIORITY_CLASSES:
        return 2
    if top_class is None:
        return 3
    return 1


def effective_ab_mag(
    mag: float | None,
    flux_njy: float | None,
    *,
    negative: bool = False,
) -> float | None:
    if mag is not None and math.isfinite(mag) and not negative:
        return float(mag)
    if flux_njy is not None and math.isfinite(flux_njy) and flux_njy > 0:
        return float(-2.5 * math.log10(flux_njy) + 31.4)
    return None


def compute_peak_photometry(
    detections: Sequence[DetectionRow],
) -> tuple[float | None, str | None]:
    best_mag: float | None = None
    best_band: str | None = None
    for d in detections:
        raw = d.raw or {}
        corrected = raw.get("corrected") is True
        magpsf_corr = raw.get("magpsf_corr")
        eff_mag_val = (
            float(magpsf_corr) if corrected and isinstance(magpsf_corr, (int, float)) else d.mag
        )
        isdiffpos = raw.get("isdiffpos")
        negative = isdiffpos in (-1, "-1", "f") and not corrected
        cand = effective_ab_mag(eff_mag_val, d.flux_njy, negative=negative)
        if cand is not None and (best_mag is None or cand < best_mag):
            best_mag = round(cand, 4)
            best_band = d.band
    return best_mag, best_band


def compute_latest_photometry(
    detections: Sequence[DetectionRow],
) -> tuple[float | None, str | None]:
    """Returns `(latest_mag, latest_band)` from the most recent valid detection."""
    latest_mjd: float | None = None
    latest_mag: float | None = None
    latest_band: str | None = None
    for d in detections:
        raw = d.raw or {}
        corrected = raw.get("corrected") is True
        magpsf_corr = raw.get("magpsf_corr")
        eff_mag_val = (
            float(magpsf_corr) if corrected and isinstance(magpsf_corr, (int, float)) else d.mag
        )
        isdiffpos = raw.get("isdiffpos")
        negative = isdiffpos in (-1, "-1", "f") and not corrected
        cand = effective_ab_mag(eff_mag_val, d.flux_njy, negative=negative)
        if cand is not None and (latest_mjd is None or d.mjd >= latest_mjd):
            latest_mjd = d.mjd
            latest_mag = round(cand, 4)
            latest_band = d.band
    return latest_mag, latest_band


def serialize_detection(d: DetectionRow) -> dict[str, Any]:
    raw = d.raw or {}
    corrected = raw.get("corrected") is True
    magpsf_corr = raw.get("magpsf_corr")
    sigmapsf_corr = raw.get("sigmapsf_corr")
    mag = float(magpsf_corr) if corrected and isinstance(magpsf_corr, (int, float)) else d.mag
    mag_err = (
        float(sigmapsf_corr) if corrected and isinstance(sigmapsf_corr, (int, float)) else d.mag_err
    )
    isdiffpos = raw.get("isdiffpos")
    negative = isdiffpos in (-1, "-1", "f") and not corrected
    candid = raw.get("candid")
    has_stamp = raw.get("has_stamp")
    return {
        "measurement_id": d.measurement_id,
        "mjd": d.mjd,
        "band": d.band,
        "mag": mag,
        "mag_err": mag_err,
        "flux_njy": d.flux_njy,
        "flux_err_njy": d.flux_err_njy,
        "negative": bool(negative),
        "candid": str(candid) if candid is not None else None,
        "has_stamp": bool(has_stamp) if isinstance(has_stamp, bool) else None,
    }


def serialize_classification(c: ClassificationRow) -> dict[str, Any]:
    return {
        "classifier": c.classifier_name,
        "version": c.classifier_version,
        "class_name": c.class_name,
        "probability": c.probability,
        "ranking": c.ranking,
    }


class FirestoreStore:
    """Drop-in replacement for `skyalerts_ingest.store.Store` backed by Cloud Firestore."""

    def __init__(self, db: Any, *, now_fn: Callable[[], datetime] | None = None) -> None:
        self.db = db
        self._now = now_fn or (lambda: datetime.now(UTC))
        # Keep in-memory index of objects touched in the active run so enrichment_candidates
        # and notification triggers don't need extra Firestore scans.
        self._touched_in_run: dict[int, set[str]] = {}
        self.last_touched_objects: list[dict[str, Any]] = []
        self.newly_matched_asteroids: list[dict[str, Any]] = []

    @property
    def last_matched_asteroids(self) -> list[dict[str, Any]]:
        return self.newly_matched_asteroids

    def close(self) -> None:
        pass

    # -- runs / lease ------------------------------------------------------
    def start_run(self, trigger: str, surveys: Sequence[str]) -> int | None:
        now = self._now()
        now_ts = int(now.timestamp())
        lease_ref = self.db.collection("rollups").document("ingest_lease")
        lease_snap = lease_ref.get()
        if lease_snap.exists:
            data = lease_snap.to_dict() or {}
            if (
                data.get("status") == "running"
                and isinstance(data.get("started_at_unix"), (int, float))
                and now_ts - int(data["started_at_unix"]) < LEASE_SECONDS
            ):
                return None
            if data.get("status") == "running" and data.get("run_id") is not None:
                old_id = int(data["run_id"])
                self.db.collection("admin_runs").document(str(old_id)).set(
                    {
                        "status": "failed",
                        "finished_at": now.isoformat(),
                        "finished_at_unix": now_ts,
                        "error_count": 1,
                        "errors": [{"source": "lease", "error": "abandoned run"}],
                    },
                    merge=True,
                )

        run_id = int(now.timestamp() * 1000)
        run_doc = {
            "id": run_id,
            "started_at": now.isoformat(),
            "started_at_unix": now_ts,
            "finished_at": None,
            "finished_at_unix": None,
            "status": "running",
            "trigger": trigger,
            "surveys": list(surveys),
            "objects_seen": 0,
            "objects_upserted": 0,
            "classifications_upserted": 0,
            "objects_enriched": 0,
            "detections_upserted": 0,
            "requests": 0,
            "error_count": 0,
            "errors": [],
            "duration_ms": None,
            "coverage": {},
        }
        self.db.collection("admin_runs").document(str(run_id)).set(run_doc)
        lease_ref.set(
            {
                "run_id": run_id,
                "status": "running",
                "started_at_unix": now_ts,
            }
        )
        self._touched_in_run[run_id] = set()
        return run_id

    def finish_run(
        self,
        run_id: int,
        *,
        status: str,
        objects_seen: int,
        objects_upserted: int,
        classifications_upserted: int,
        objects_enriched: int = 0,
        detections_upserted: int = 0,
        requests: int,
        errors: list[dict[str, Any]],
        duration_ms: int,
        coverage: dict[str, Any] | None = None,
    ) -> None:
        now = self._now()
        now_ts = int(now.timestamp())
        cov = coverage or {}
        self.db.collection("admin_runs").document(str(run_id)).set(
            {
                "finished_at": now.isoformat(),
                "finished_at_unix": now_ts,
                "status": status,
                "objects_seen": objects_seen,
                "objects_upserted": objects_upserted,
                "classifications_upserted": classifications_upserted,
                "objects_enriched": objects_enriched,
                "detections_upserted": detections_upserted,
                "requests": requests,
                "error_count": len(errors),
                "errors": errors[:50],
                "duration_ms": duration_ms,
                "coverage": cov,
            },
            merge=True,
        )
        self.db.collection("rollups").document("ingest_lease").set(
            {
                "run_id": run_id,
                "status": status,
                "finished_at_unix": now_ts,
            },
            merge=True,
        )
        if status in ("success", "partial"):
            wm_updates: dict[str, float] = {}
            for src_key, src_cov in cov.items():
                if (
                    isinstance(src_cov, dict)
                    and src_cov.get("advances") is True
                    and isinstance(src_cov.get("newest_mjd"), (int, float))
                ):
                    wm_updates[src_key] = float(src_cov["newest_mjd"])
            if wm_updates:
                self.db.collection("rollups").document("watermarks").set(wm_updates, merge=True)

    def source_watermark(self, source: str) -> float | None:
        snap = self.db.collection("rollups").document("watermarks").get()
        if not snap.exists:
            return None
        val = (snap.to_dict() or {}).get(source)
        return float(val) if isinstance(val, (int, float)) else None

    # -- data --------------------------------------------------------------
    def upsert_batch(
        self,
        run_id: int,
        objects: Sequence[ObjectRow],
        classifications: Sequence[ClassificationRow],
    ) -> tuple[int, int]:
        if not objects:
            return 0, 0
        now_iso = self._now().isoformat()
        touched = self._touched_in_run.setdefault(run_id, set())

        # Merge duplicate (survey, oid) rows in the same batch applying lc_classifier precedence.
        merged_by_key: dict[str, dict[str, Any]] = {}
        for o in objects:
            doc_id = object_doc_id(o.survey, o.oid)
            touched.add(doc_id)
            existing_snap = self.db.collection("objects").document(doc_id).get()
            cur = (
                merged_by_key.get(doc_id)
                or (existing_snap.to_dict() if existing_snap.exists else None)
                or {}
            )

            cur_first = cur.get("firstmjd")
            firstmjd = (
                min(cur_first, o.firstmjd)
                if cur_first is not None and o.firstmjd is not None
                else (o.firstmjd if o.firstmjd is not None else cur_first)
            )
            cur_last = cur.get("lastmjd")
            lastmjd = (
                max(cur_last, o.lastmjd)
                if cur_last is not None and o.lastmjd is not None
                else (o.lastmjd if o.lastmjd is not None else cur_last)
            )

            take_top = o.top_class is not None and (
                cur.get("top_classifier") != "lc_classifier" or o.top_classifier == "lc_classifier"
            )
            top_class = o.top_class if take_top else cur.get("top_class")
            top_classifier = o.top_classifier if take_top else cur.get("top_classifier")
            top_version = (
                o.top_classifier_version if take_top else cur.get("top_classifier_version")
            )
            top_prob = o.top_probability if take_top else cur.get("top_probability")

            merged_by_key[doc_id] = {
                "survey": o.survey,
                "oid": o.oid,
                "meanra": o.meanra if o.meanra is not None else cur.get("meanra"),
                "meandec": o.meandec if o.meandec is not None else cur.get("meandec"),
                "firstmjd": firstmjd,
                "lastmjd": lastmjd,
                "ndet": o.ndet if o.ndet is not None else cur.get("ndet"),
                "n_forced": o.n_forced if o.n_forced is not None else cur.get("n_forced"),
                "stellar": o.stellar if o.stellar is not None else cur.get("stellar"),
                "top_class": top_class,
                "top_classifier": top_classifier,
                "top_classifier_version": top_version,
                "top_probability": top_prob,
                "tier": tier_for_class(top_class),
                "is_artifact": top_class == ARTIFACT_CLASS,
                "last_ingested_at": now_iso,
                "last_ingest_run_id": run_id,
            }
            prev_ndet = cur.get("ndet")
            new_ndet = merged_by_key[doc_id]["ndet"]
            prev_class = cur.get("top_class")
            self.last_touched_objects = [
                t for t in self.last_touched_objects if t.get("doc_id") != doc_id
            ]
            self.last_touched_objects.append(
                {
                    "doc_id": doc_id,
                    "survey": o.survey,
                    "oid": o.oid,
                    "is_new": not existing_snap.exists,
                    "is_artifact": top_class == ARTIFACT_CLASS,
                    "top_class": top_class,
                    "top_probability": top_prob,
                    "peak_mag": cur.get("peak_mag"),
                    "n_detections": new_ndet,
                    "ndet_increased": (
                        isinstance(new_ndet, int)
                        and isinstance(prev_ndet, int)
                        and new_ndet > prev_ndet
                    ),
                    "class_changed": (
                        existing_snap.exists and top_class is not None and top_class != prev_class
                    ),
                }
            )

        batch = self.db.batch()
        count = 0
        for doc_id, payload in merged_by_key.items():
            ref = self.db.collection("objects").document(doc_id)
            batch.set(ref, payload, merge=True)
            count += 1
            if count % BATCH_LIMIT == 0:
                batch.commit()
                batch = self.db.batch()
        if count % BATCH_LIMIT != 0:
            batch.commit()

        return len(objects), len(classifications)

    def enrichment_candidates(self, run_id: int, limit: int) -> list[tuple[str, str]]:
        if limit <= 0:
            return []
        touched_ids = self._touched_in_run.get(run_id, set())
        candidates: list[tuple[int, float, float, str, str]] = []
        for doc_id in touched_ids:
            snap = self.db.collection("objects").document(doc_id).get()
            if not snap.exists:
                continue
            d = snap.to_dict() or {}
            top_class = d.get("top_class")
            if top_class in SKIP_CLASSES:
                continue
            lastmjd = d.get("lastmjd")
            enriched_lastmjd = d.get("enriched_lastmjd")
            if enriched_lastmjd is not None and lastmjd is not None and lastmjd <= enriched_lastmjd:
                continue
            prio = 1 if top_class in TIER1_CLASSES else (3 if top_class in TIER3_CLASSES else 2)
            prob = float(d.get("top_probability") or 0.0)
            lmjd = float(lastmjd or 0.0)
            candidates.append((prio, -prob, -lmjd, str(d["survey"]), str(d["oid"])))

        candidates.sort()
        return [(survey, oid) for _, _, _, survey, oid in candidates[:limit]]

    def enrich_object(
        self,
        survey: str,
        oid: str,
        detections: Sequence[DetectionRow],
        classifications: Sequence[ClassificationRow],
    ) -> tuple[int, int]:
        doc_id = object_doc_id(survey, oid)
        obj_ref = self.db.collection("objects").document(doc_id)
        obj_snap = obj_ref.get()
        lastmjd = (obj_snap.to_dict() or {}).get("lastmjd") if obj_snap.exists else None
        peak_mag, peak_band = compute_peak_photometry(detections)
        latest_mag, latest_mag_band = compute_latest_photometry(detections)

        detail_ref = obj_ref.collection("detail").document("enrichment")
        detail_ref.set(
            {
                "survey": survey,
                "oid": oid,
                "updated_at": self._now().isoformat(),
                "detections": [serialize_detection(d) for d in detections],
                "classifications": [serialize_classification(c) for c in classifications],
            }
        )
        obj_ref.set(
            {
                "enriched_at": self._now().isoformat(),
                "enriched_lastmjd": lastmjd,
                "peak_mag": peak_mag,
                "peak_band": peak_band,
                "latest_mag": latest_mag,
                "latest_mag_band": latest_mag_band,
            },
            merge=True,
        )
        for t in self.last_touched_objects:
            if t.get("doc_id") == doc_id:
                t["peak_mag"] = peak_mag
                t["peak_band"] = peak_band
                t["latest_mag"] = latest_mag
                t["latest_mag_band"] = latest_mag_band
        return len(detections), len(classifications)

    def upsert_bright_targets(self, targets: Sequence[dict[str, Any]]) -> int:
        """Upserts bright supernovae, comets, NEOs, and evergreen variables into `objects/`."""
        if not targets:
            return 0
        now_iso = self._now().isoformat()
        count = 0
        batch = self.db.batch()
        ops = 0
        for item in targets:
            doc_id = str(item.get("doc_id") or "")
            if not doc_id:
                continue
            payload = dict(item)
            payload["updated_at"] = now_iso
            ref = self.db.collection("objects").document(doc_id)
            batch.set(ref, payload, merge=True)
            ops += 1
            count += 1
            if ops >= 400:
                batch.commit()
                batch = self.db.batch()
                ops = 0
        if ops > 0:
            batch.commit()
        return count

    def prune_artifacts(self, *, max_age_days: float = 30.0, ref_mjd: float | None = None) -> int:
        if max_age_days < 7.0:
            raise ValueError("max_age_days must be at least 7.0")
        wall_mjd = datetime_to_mjd(self._now())
        eff_ref = min(ref_mjd, wall_mjd) if ref_mjd is not None else wall_mjd
        cutoff_mjd = eff_ref - max_age_days

        pruned = 0
        for snap in self.db.collection("objects").stream():
            d = snap.to_dict() or {}
            if (
                d.get("top_class") == ARTIFACT_CLASS
                and d.get("enriched_at") is None
                and isinstance(d.get("lastmjd"), (int, float))
                and float(d["lastmjd"]) < cutoff_mjd
            ):
                snap.reference.delete()
                pruned += 1
        return pruned

    # -- SkyBoT asteroid identification ------------------------------------
    def identify_asteroids(
        self,
        client: SkyBotClient,
        *,
        max_objects: int = DEFAULT_IDENTIFY_MAX,
        time_budget_s: float = DEFAULT_TIME_BUDGET_S,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> IdentifyResult:
        res = IdentifyResult()
        if max_objects <= 0:
            return res

        now = self._now()
        retry_cutoff = (now - timedelta(days=1)).isoformat()
        candidates: list[tuple[int, float, float, str, str, float, float, float]] = []
        for snap in self.db.collection("objects").stream():
            d = snap.to_dict() or {}
            if d.get("top_class") != ASTEROID_CLASS:
                continue
            ra, dec, firstmjd = d.get("meanra"), d.get("meandec"), d.get("firstmjd")
            if ra is None or dec is None or firstmjd is None:
                continue
            sso = d.get("sso")
            if isinstance(sso, dict):
                st = sso.get("status")
                if st in ("matched", "no_match"):
                    continue
                if st == "error" and str(sso.get("queried_at") or "") >= retry_cutoff:
                    continue
            survey = str(d["survey"])
            oid = str(d["oid"])
            survey_rank = 0 if survey == "ztf" else 1
            prob = float(d.get("top_probability") or 0.0)
            lastmjd = float(d.get("lastmjd") or 0.0)
            candidates.append(
                (survey_rank, -prob, -lastmjd, survey, oid, float(ra), float(dec), float(firstmjd))
            )

        candidates.sort()
        started = monotonic()
        for _, _, _, survey, oid, ra, dec, firstmjd in candidates[:max_objects]:
            if monotonic() - started + client.timeout_s > time_budget_s:
                res.budget_hit = True
                break
            res.queried += 1
            doc_ref = self.db.collection("objects").document(object_doc_id(survey, oid))
            queried_at = self._now().isoformat()
            try:
                hits = client.conesearch(survey, ra, dec, firstmjd)
            except SkyBotError as exc:
                doc_ref.set(
                    {
                        "sso": {
                            "status": "error",
                            "obs_mjd": firstmjd,
                            "queried_at": queried_at,
                            "error": str(exc)[:200],
                        }
                    },
                    merge=True,
                )
                res.errors += 1
                continue

            best: SkyBotHit | None = (
                hits[0] if hits and hits[0].sep_arcsec <= MAX_SEP_ARCSEC else None
            )
            if best is not None:
                sso_payload = {
                    "status": "matched",
                    "obs_mjd": firstmjd,
                    "queried_at": queried_at,
                    "sso_number": best.sso_number,
                    "sso_name": best.sso_name,
                    "sso_class": best.sso_class,
                    "predicted_mag": best.predicted_mag,
                    "sep_arcsec": best.sep_arcsec,
                    "ra_rate_arcsec_h": best.ra_rate_arcsec_h,
                    "dec_rate_arcsec_h": best.dec_rate_arcsec_h,
                    "geo_dist_au": best.geo_dist_au,
                    "helio_dist_au": best.helio_dist_au,
                }
                doc_ref.set({"sso": sso_payload}, merge=True)
                self.newly_matched_asteroids.append({"survey": survey, "oid": oid, **sso_payload})
                res.matched += 1
            else:
                doc_ref.set(
                    {
                        "sso": {
                            "status": "no_match",
                            "obs_mjd": firstmjd,
                            "queried_at": queried_at,
                        }
                    },
                    merge=True,
                )
                res.no_match += 1
        return res

    # -- Weekly digest selection from Firestore ----------------------------
    def select_digest(self, week_end: datetime) -> Digest:
        end_dt = normalize_utc(week_end)
        start_dt = end_dt - timedelta(days=7)
        end_mjd = datetime_to_mjd(end_dt)
        start_mjd = end_mjd - 7.0

        all_non_bogus: list[dict[str, Any]] = []
        week_non_bogus: list[dict[str, Any]] = []
        total_detections = 0

        for snap in self.db.collection("objects").stream():
            d = snap.to_dict() or {}
            if d.get("top_class") == ARTIFACT_CLASS:
                continue
            all_non_bogus.append(d)
            enr_snap = snap.reference.collection("detail").document("enrichment").get()
            if enr_snap.exists:
                dets = (enr_snap.to_dict() or {}).get("detections") or []
                total_detections += len(dets)
            fmjd = d.get("firstmjd")
            if isinstance(fmjd, (int, float)) and start_mjd <= float(fmjd) <= end_mjd:
                week_non_bogus.append(d)

        def _to_digest_obj(d: dict[str, Any]) -> DigestObject:
            sso = d.get("sso") if isinstance(d.get("sso"), dict) else {}
            matched = sso.get("status") == "matched"
            return DigestObject(
                survey=str(d["survey"]),
                oid=str(d["oid"]),
                top_class=d.get("top_class"),
                top_probability=float(d["top_probability"])
                if d.get("top_probability") is not None
                else None,
                firstmjd=float(d["firstmjd"]) if d.get("firstmjd") is not None else None,
                lastmjd=float(d["lastmjd"]) if d.get("lastmjd") is not None else None,
                ndet=int(d["ndet"]) if d.get("ndet") is not None else None,
                peak_mag=float(d["peak_mag"]) if d.get("peak_mag") is not None else None,
                peak_band=str(d["peak_band"]) if d.get("peak_band") is not None else None,
                sso_name=str(sso["sso_name"])
                if matched and sso.get("sso_name") is not None
                else None,
                sso_number=int(sso["sso_number"])
                if matched and sso.get("sso_number") is not None
                else None,
                sep_arcsec=float(sso["sep_arcsec"])
                if matched and sso.get("sep_arcsec") is not None
                else None,
            )

        hl_candidates = [d for d in week_non_bogus if d.get("top_class") in TRANSIENT_CLASSES]
        hl_candidates.sort(
            key=lambda d: (
                -(float(d.get("top_probability") or -1.0)),
                -(float(d.get("lastmjd") or -1.0)),
                str(d.get("survey") or ""),
                str(d.get("oid") or ""),
            )
        )
        headliners = tuple(_to_digest_obj(d) for d in hl_candidates[:HEADLINER_LIMIT])

        br_candidates = [
            d
            for d in week_non_bogus
            if d.get("top_class") != ASTEROID_CLASS and isinstance(d.get("peak_mag"), (int, float))
        ]
        br_candidates.sort(
            key=lambda d: (
                float(d["peak_mag"]),
                -(float(d.get("top_probability") or -1.0)),
                -(float(d.get("lastmjd") or -1.0)),
                str(d.get("survey") or ""),
                str(d.get("oid") or ""),
            )
        )
        brightest = tuple(_to_digest_obj(d) for d in br_candidates[:BRIGHTEST_LIMIT])

        solar_candidates = [d for d in week_non_bogus if d.get("top_class") == ASTEROID_CLASS]
        solar_candidates.sort(
            key=lambda d: (
                not (
                    isinstance(d.get("sso"), dict)
                    and d["sso"].get("status") == "matched"
                    and d["sso"].get("sso_name") is not None
                ),
                -(float(d.get("top_probability") or -1.0)),
                -(float(d.get("lastmjd") or -1.0)),
                str(d.get("survey") or ""),
                str(d.get("oid") or ""),
            )
        )
        solar_examples = tuple(_to_digest_obj(d) for d in solar_candidates[:SOLAR_EXAMPLE_LIMIT])

        counts_by_group: dict[ClassGroup, int] = {g.id: 0 for g in GROUPS}
        for d in week_non_bogus:
            grp = group_of(d.get("top_class"))
            counts_by_group[grp] = counts_by_group.get(grp, 0) + 1
        new_by_group = tuple(
            GroupCount(group=g.id, label=g.label, count=counts_by_group[g.id]) for g in GROUPS
        )

        return Digest(
            week_start=start_dt,
            week_end=end_dt,
            start_mjd=start_mjd,
            end_mjd=end_mjd,
            headliners=headliners,
            brightest=brightest,
            solar_system=SolarSystemSection(
                asteroid_count=len(solar_candidates),
                examples=solar_examples,
            ),
            stats=WeekStats(
                new_by_group=new_by_group,
                total_objects=len(all_non_bogus),
                total_detections=total_detections,
            ),
        )

    # -- 1-read Rollups (`rollups/overview` & `rollups/trends_90d`) --------
    def compute_and_save_rollups(
        self,
        *,
        now: datetime | None = None,
        solar_ephemerides: dict[str, dict[str, Any] | None] | None = None,
    ) -> dict[str, Any]:
        ref_dt = normalize_utc(now or self._now())
        now_mjd = datetime_to_mjd(ref_dt)
        today_mjd = int(math.floor(now_mjd))
        week_ago_mjd = now_mjd - 7.0
        two_weeks_ago_mjd = now_mjd - 14.0

        windows = {"1d": 1.0, "3d": 3.0, "7d": 7.0, "30d": 30.0}
        class_counts: dict[str, dict[str, int]] = {w: {} for w in windows}
        matched_asteroids: list[dict[str, Any]] = []
        recent_7d_rows: list[dict[str, Any]] = []
        week_non_bogus: list[dict[str, Any]] = []

        total_objects = 0
        new_this_week = 0
        new_last_week = 0
        transients_this_week = 0
        transients_last_week = 0
        enriched_objects = 0

        daily_class_counts: dict[tuple[int, str], int] = {}
        daily_survey_counts: dict[tuple[int, str], int] = {}

        for snap in self.db.collection("objects").stream():
            d = snap.to_dict() or {}
            top_class = d.get("top_class")
            is_artifact = top_class == ARTIFACT_CLASS
            lastmjd = d.get("lastmjd")
            firstmjd = d.get("firstmjd")
            survey = str(d.get("survey") or "ztf")

            if d.get("enriched_at") is not None:
                enriched_objects += 1

            if isinstance(lastmjd, (int, float)):
                for w_key, w_days in windows.items():
                    if float(lastmjd) >= now_mjd - w_days:
                        cls_key = str(top_class) if top_class is not None else "__null__"
                        class_counts[w_key][cls_key] = class_counts[w_key].get(cls_key, 0) + 1
                if not is_artifact and float(lastmjd) >= now_mjd - 3.0:
                    recent_7d_rows.append(d)

            if is_artifact:
                continue

            total_objects += 1
            sso = d.get("sso")
            if isinstance(sso, dict) and sso.get("status") == "matched" and sso.get("sso_name"):
                matched_asteroids.append(
                    {
                        "survey": survey,
                        "oid": str(d["oid"]),
                        "obs_mjd": float(sso.get("obs_mjd") or firstmjd or 0.0),
                        "sso_number": sso.get("sso_number"),
                        "sso_name": str(sso["sso_name"]),
                        "sso_class": sso.get("sso_class"),
                        "predicted_mag": sso.get("predicted_mag"),
                        "sep_arcsec": float(sso.get("sep_arcsec") or 0.0),
                        "geo_dist_au": sso.get("geo_dist_au"),
                        "helio_dist_au": sso.get("helio_dist_au"),
                    }
                )

            if isinstance(firstmjd, (int, float)):
                fmjd = float(firstmjd)
                if fmjd >= week_ago_mjd:
                    new_this_week += 1
                    week_non_bogus.append(d)
                    if top_class in TRANSIENT_CLASSES:
                        transients_this_week += 1
                elif fmjd >= two_weeks_ago_mjd:
                    new_last_week += 1
                    if top_class in TRANSIENT_CLASSES:
                        transients_last_week += 1

                day_int = int(math.floor(fmjd))
                if day_int >= today_mjd - 90:
                    cls_key = str(top_class) if top_class is not None else "__null__"
                    daily_class_counts[(day_int, cls_key)] = (
                        daily_class_counts.get((day_int, cls_key), 0) + 1
                    )
                    daily_survey_counts[(day_int, survey)] = (
                        daily_survey_counts.get((day_int, survey), 0) + 1
                    )

        matched_asteroids.sort(
            key=lambda m: (-float(m["obs_mjd"]), float(m["sep_arcsec"]), m["survey"], m["oid"])
        )

        # Build the 3-card "What stood out" home highlight strip
        highlights: list[dict[str, Any]] = []
        used_hl_ids: set[str] = set()
        transient_pool = [r for r in recent_7d_rows if r.get("top_class") in TRANSIENT_CLASSES]
        transient_pool.sort(
            key=lambda r: (
                -float(r.get("top_probability") or 0.0),
                -float(r.get("lastmjd") or 0.0),
            )
        )
        if transient_pool:
            top_t = transient_pool[0]
            tid = object_doc_id(str(top_t["survey"]), str(top_t["oid"]))
            used_hl_ids.add(tid)
            highlights.append({"kind": "explosion", **top_t})

        active_pool = [
            r
            for r in recent_7d_rows
            if object_doc_id(str(r["survey"]), str(r["oid"])) not in used_hl_ids
            and isinstance(r.get("ndet"), int)
        ]
        active_pool.sort(key=lambda r: (-int(r.get("ndet") or 0), -float(r.get("lastmjd") or 0.0)))
        if active_pool:
            top_a = active_pool[0]
            aid = object_doc_id(str(top_a["survey"]), str(top_a["oid"]))
            used_hl_ids.add(aid)
            highlights.append({"kind": "active", **top_a})

        solar_pool = [
            r
            for r in recent_7d_rows
            if object_doc_id(str(r["survey"]), str(r["oid"])) not in used_hl_ids
            and r.get("top_class") == ASTEROID_CLASS
        ]
        solar_pool.sort(
            key=lambda r: (
                not (isinstance(r.get("sso"), dict) and r["sso"].get("status") == "matched"),
                -float(r.get("top_probability") or 0.0),
            )
        )
        if solar_pool:
            highlights.append({"kind": "solar", **solar_pool[0]})

        def _to_digest_obj_inline(d: dict[str, Any]) -> DigestObject:
            sso_d = d.get("sso") if isinstance(d.get("sso"), dict) else {}
            matched_d = sso_d.get("status") == "matched"
            return DigestObject(
                survey=str(d["survey"]),
                oid=str(d["oid"]),
                top_class=d.get("top_class"),
                top_probability=float(d["top_probability"])
                if d.get("top_probability") is not None
                else None,
                firstmjd=float(d["firstmjd"]) if d.get("firstmjd") is not None else None,
                lastmjd=float(d["lastmjd"]) if d.get("lastmjd") is not None else None,
                ndet=int(d["ndet"]) if d.get("ndet") is not None else None,
                peak_mag=float(d["peak_mag"]) if d.get("peak_mag") is not None else None,
                peak_band=str(d["peak_band"]) if d.get("peak_band") is not None else None,
                sso_name=str(sso_d["sso_name"])
                if matched_d and sso_d.get("sso_name") is not None
                else None,
                sso_number=int(sso_d["sso_number"])
                if matched_d and sso_d.get("sso_number") is not None
                else None,
                sep_arcsec=float(sso_d["sep_arcsec"])
                if matched_d and sso_d.get("sep_arcsec") is not None
                else None,
            )

        hl_cand = [d for d in week_non_bogus if d.get("top_class") in TRANSIENT_CLASSES]
        hl_cand.sort(
            key=lambda d: (
                -(float(d.get("top_probability") or -1.0)),
                -(float(d.get("lastmjd") or -1.0)),
                str(d.get("survey") or ""),
                str(d.get("oid") or ""),
            )
        )
        br_cand = [
            d
            for d in week_non_bogus
            if d.get("top_class") != ASTEROID_CLASS and isinstance(d.get("peak_mag"), (int, float))
        ]
        br_cand.sort(
            key=lambda d: (
                float(d["peak_mag"]),
                -(float(d.get("top_probability") or -1.0)),
                -(float(d.get("lastmjd") or -1.0)),
                str(d.get("survey") or ""),
                str(d.get("oid") or ""),
            )
        )
        sol_cand = [d for d in week_non_bogus if d.get("top_class") == ASTEROID_CLASS]
        sol_cand.sort(
            key=lambda d: (
                not (
                    isinstance(d.get("sso"), dict)
                    and d["sso"].get("status") == "matched"
                    and d["sso"].get("sso_name") is not None
                ),
                -(float(d.get("top_probability") or -1.0)),
                -(float(d.get("lastmjd") or -1.0)),
                str(d.get("survey") or ""),
                str(d.get("oid") or ""),
            )
        )
        counts_by_grp: dict[ClassGroup, int] = {g.id: 0 for g in GROUPS}
        for d in week_non_bogus:
            grp_id = group_of(d.get("top_class"))
            counts_by_grp[grp_id] = counts_by_grp.get(grp_id, 0) + 1
        inline_digest = Digest(
            week_start=ref_dt - timedelta(days=7),
            week_end=ref_dt,
            start_mjd=week_ago_mjd,
            end_mjd=now_mjd,
            headliners=tuple(_to_digest_obj_inline(d) for d in hl_cand[:HEADLINER_LIMIT]),
            brightest=tuple(_to_digest_obj_inline(d) for d in br_cand[:BRIGHTEST_LIMIT]),
            solar_system=SolarSystemSection(
                asteroid_count=len(sol_cand),
                examples=tuple(_to_digest_obj_inline(d) for d in sol_cand[:SOLAR_EXAMPLE_LIMIT]),
            ),
            stats=WeekStats(
                new_by_group=tuple(
                    GroupCount(group=g.id, label=g.label, count=counts_by_grp[g.id]) for g in GROUPS
                ),
                total_objects=total_objects,
                total_detections=enriched_objects * 50,
            ),
        )
        weekly_dispatch = {
            "subject": format_subject(inline_digest),
            "markdown": render_markdown(inline_digest),
            "podcast": render_podcast(inline_digest),
        }

        overview_doc = {
            "updated_at": ref_dt.isoformat(),
            "updated_at_unix": int(ref_dt.timestamp()),
            "today_mjd": today_mjd,
            "total_objects": total_objects,
            "totals": {
                "objects": total_objects,
                "enriched_objects": enriched_objects,
                "new_this_week": new_this_week,
                "transients_this_week": transients_this_week,
            },
            "highlights": highlights,
            "window_class_counts": class_counts,
            "matched_asteroids": matched_asteroids[:40],
            "solar_ephemerides": solar_ephemerides or {},
            "weekly_dispatch": weekly_dispatch,
        }
        trends_doc = {
            "updated_at": ref_dt.isoformat(),
            "today_mjd": today_mjd,
            "totals": {
                "total": total_objects,
                "new_this_week": new_this_week,
                "new_last_week": new_last_week,
                "transients_this_week": transients_this_week,
                "transients_last_week": transients_last_week,
            },
            "comparison": {
                "new_this_week": new_this_week,
                "new_last_week": new_last_week,
                "transients_this_week": transients_this_week,
                "transients_last_week": transients_last_week,
            },
            "daily_counts": [
                {
                    "day": day,
                    "top_class": None if cls_key == "__null__" else cls_key,
                    "n": cnt,
                }
                for (day, cls_key), cnt in sorted(daily_class_counts.items())
            ],
            "by_day_survey": [
                {"day": day, "survey": survey, "n": cnt}
                for (day, survey), cnt in sorted(daily_survey_counts.items())
            ],
            "daily_survey_counts": [
                {"day": day, "survey": survey, "n": cnt}
                for (day, survey), cnt in sorted(daily_survey_counts.items())
            ],
        }
        self.db.collection("rollups").document("overview").set(overview_doc)
        self.db.collection("rollups").document("trends_90d").set(trends_doc)
        return {"overview": overview_doc, "trends_90d": trends_doc}
