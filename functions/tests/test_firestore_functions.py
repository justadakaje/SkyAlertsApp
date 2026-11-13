"""Unit and integration tests for `skyalerts_functions`."""

from __future__ import annotations

import copy
from datetime import UTC, datetime
from typing import Any

import pytest
from skyalerts_ingest.ingest import Config, Source
from skyalerts_ingest.normalize import (
    ClassificationRow,
    DetectionRow,
    ObjectRow,
)
from skyalerts_ingest.sso import SkyBotHit

from skyalerts_functions.backfill import backfill_neon_to_firestore
from skyalerts_functions.firestore_store import FirestoreStore, object_doc_id
from skyalerts_functions.horizons import parse_horizons
from skyalerts_functions.notifications import (
    NotificationPayload,
    notify_bookmarked_updates,
)
from skyalerts_functions.pipeline import (
    execute_daily_pipeline,
    execute_weekly_digest,
    require_admin_and_audit,
)


class FakeDocSnapshot:
    def __init__(self, doc_id: str, data: dict[str, Any] | None, ref: FakeDocRef) -> None:
        self.id = doc_id
        self._data = copy.deepcopy(data) if data is not None else None
        self.reference = ref

    @property
    def exists(self) -> bool:
        return self._data is not None

    def to_dict(self) -> dict[str, Any] | None:
        return copy.deepcopy(self._data)


class FakeDocRef:
    def __init__(self, db: FakeFirestoreClient, path: tuple[str, ...]) -> None:
        self._db = db
        self._path = path
        self.id = path[-1]

    def get(self) -> FakeDocSnapshot:
        return FakeDocSnapshot(self.id, self._db._storage.get(self._path), self)

    def set(self, data: dict[str, Any], merge: bool = False) -> None:
        if merge and self._path in self._db._storage:
            merged = copy.deepcopy(self._db._storage[self._path])
            merged.update(copy.deepcopy(data))
            self._db._storage[self._path] = merged
        else:
            self._db._storage[self._path] = copy.deepcopy(data)

    def delete(self) -> None:
        self._db._storage.pop(self._path, None)

    def collection(self, name: str) -> FakeCollectionRef:
        return FakeCollectionRef(self._db, (*self._path, name))


class FakeCollectionRef:
    def __init__(self, db: FakeFirestoreClient, path: tuple[str, ...]) -> None:
        self._db = db
        self._path = path

    def document(self, doc_id: str) -> FakeDocRef:
        return FakeDocRef(self._db, (*self._path, doc_id))

    def stream(self) -> list[FakeDocSnapshot]:
        out: list[FakeDocSnapshot] = []
        target_len = len(self._path) + 1
        for k, v in list(self._db._storage.items()):
            if len(k) == target_len and k[: len(self._path)] == self._path:
                ref = FakeDocRef(self._db, k)
                out.append(FakeDocSnapshot(k[-1], v, ref))
        return out


class FakeCollectionGroupRef:
    def __init__(self, db: FakeFirestoreClient, collection_id: str) -> None:
        self._db = db
        self._collection_id = collection_id

    def stream(self) -> list[FakeDocSnapshot]:
        out: list[FakeDocSnapshot] = []
        for k, v in list(self._db._storage.items()):
            if len(k) >= 2 and k[-2] == self._collection_id:
                ref = FakeDocRef(self._db, k)
                out.append(FakeDocSnapshot(k[-1], v, ref))
        return out


class FakeWriteBatch:
    def __init__(self) -> None:
        self._ops: list[tuple[str, FakeDocRef, dict[str, Any] | None, bool]] = []

    def set(self, ref: FakeDocRef, data: dict[str, Any], merge: bool = False) -> None:
        self._ops.append(("set", ref, data, merge))

    def delete(self, ref: FakeDocRef) -> None:
        self._ops.append(("delete", ref, None, False))

    def commit(self) -> None:
        for op, ref, data, merge in self._ops:
            if op == "set" and data is not None:
                ref.set(data, merge=merge)
            elif op == "delete":
                ref.delete()
        self._ops.clear()


class FakeFirestoreClient:
    def __init__(self) -> None:
        self._storage: dict[tuple[str, ...], dict[str, Any]] = {}

    def collection(self, name: str) -> FakeCollectionRef:
        return FakeCollectionRef(self, (name,))

    def collection_group(self, collection_id: str) -> FakeCollectionGroupRef:
        return FakeCollectionGroupRef(self, collection_id)

    def batch(self) -> FakeWriteBatch:
        return FakeWriteBatch()


class FakeAlerceClient:
    """Stubs ALeRCE ZTF & Rubin list_objects, detections, and probabilities."""

    def __init__(self) -> None:
        self.request_count = 0

    def list_objects(
        self,
        survey: str,
        *,
        page: int = 1,
        page_size: int = 100,
        classifier: str | None = None,
        class_name: str | None = None,
    ) -> list[dict[str, Any]]:
        del page_size
        self.request_count += 1
        if page > 1:
            return []
        if survey == "ztf" and classifier == "lc_classifier" and class_name == "SNIa":
            return [
                {
                    "oid": "ZTF26aaabbb",
                    "meanra": 180.5,
                    "meandec": 22.1,
                    "firstmjd": 61350.2,
                    "lastmjd": 61354.8,
                    "ndet": 8,
                    "class": "SNIa",
                    "probability": 0.91,
                    "classifier": "lc_classifier",
                }
            ]
        if survey == "ztf" and classifier == "stamp_classifier" and class_name is None:
            return [
                {
                    "oid": "ZTF26sso001",
                    "meanra": 45.0,
                    "meandec": 12.0,
                    "firstmjd": 61353.0,
                    "lastmjd": 61354.5,
                    "ndet": 4,
                    "class": "asteroid",
                    "probability": 0.95,
                    "classifier": "stamp_classifier",
                }
            ]
        if survey == "lsst" and classifier is None:
            return [
                {
                    "oid": "LSST26xyz999",
                    "meanra": 210.2,
                    "meandec": -15.4,
                    "firstmjd": 61351.0,
                    "lastmjd": 61355.1,
                    "ndet": 6,
                    "class_name": "TDE",
                    "probability": 0.87,
                    "classifier_name": "stamp_classifier_rubin_beta",
                    "classifier_version": "2.1.0",
                }
            ]
        return []

    def detections(self, survey: str, oid: str) -> list[dict[str, Any]]:
        self.request_count += 1
        if survey == "ztf" and oid == "ZTF26aaabbb":
            return [
                {
                    "candid": "1001",
                    "mjd": 61350.2,
                    "fid": 1,
                    "magpsf": 18.4,
                    "sigmapsf": 0.05,
                },
                {
                    "candid": "1002",
                    "mjd": 61354.8,
                    "fid": 2,
                    "magpsf": 17.6,
                    "sigmapsf": 0.04,
                },
            ]
        if survey == "lsst" and oid == "LSST26xyz999":
            return [
                {
                    "measurement_id": "2001",
                    "mjd": 61355.1,
                    "band": "2",
                    "psfFlux": 1_000_000.0,
                    "psfFluxErr": 5000.0,
                }
            ]
        return []

    def probabilities(self, survey: str, oid: str) -> list[dict[str, Any]]:
        self.request_count += 1
        if survey == "ztf" and oid == "ZTF26aaabbb":
            return [
                {
                    "classifier_name": "lc_classifier",
                    "classifier_version": "1.0.0",
                    "class_name": "SNIa",
                    "probability": 0.91,
                    "ranking": 1,
                }
            ]
        if survey == "lsst" and oid == "LSST26xyz999":
            return [
                {
                    "classifier_name": "stamp_classifier_rubin_beta",
                    "classifier_version": "2.1.0",
                    "class_name": "TDE",
                    "probability": 0.87,
                    "ranking": 1,
                }
            ]
        return []

    def close(self) -> None:
        pass


class FakeSkyBotClient:
    timeout_s = 5.0

    def conesearch(self, survey: str, ra: float, dec: float, mjd: float) -> list[SkyBotHit]:
        del survey, ra, dec, mjd
        return [
            SkyBotHit(
                sso_number=9537,
                sso_name="Nolan",
                sso_class="MB>Inner",
                predicted_mag=16.8,
                sep_arcsec=0.42,
                ra_rate_arcsec_h=12.0,
                dec_rate_arcsec_h=-4.1,
                geo_dist_au=1.45,
                helio_dist_au=2.31,
            )
        ]

    def close(self) -> None:
        pass


def test_daily_pipeline_ingest_identify_rollups_and_fcm() -> None:
    db = FakeFirestoreClient()
    # Seed a signed-in user with a custom threshold (min_confidence=0.85, max_peak_mag=19.0)
    db.collection("users").document("user-123").set(
        {
            "fcm_tokens": ["tok-user-123"],
            "notify_transients": True,
            "min_confidence": 0.85,
            "max_peak_mag": 19.0,
        }
    )

    sent_notifications: list[NotificationPayload] = []
    cfg = Config(
        page_size=10,
        max_pages_per_source=1,
        enrich_max_objects=10,
        time_budget_s=60.0,
    )
    sources = (
        Source("lsst", complete=False, max_pages=1),
        Source("ztf", "stamp_classifier", complete=False, max_pages=1),
        Source("ztf", "lc_classifier", "SNIa", max_pages=1),
    )
    fixed_now = datetime(2026, 11, 11, 12, 0, tzinfo=UTC)

    result = execute_daily_pipeline(
        db,
        config=cfg,
        sources=sources,
        alerce_client=FakeAlerceClient(),  # type: ignore[arg-type]
        skybot_client=FakeSkyBotClient(),  # type: ignore[arg-type]
        send_fn=sent_notifications.append,
        ephemerides_fn=lambda: {
            "pluto": {
                "ra": 305.1,
                "dec": -22.8,
                "mag": 14.4,
                "distance_au": 34.8,
                "elongation": 72.0,
                "constellation": "Cap",
            }
        },
        bright_targets_fn=lambda: [],
        now=fixed_now,
    )

    assert result["total_objects"] == 3
    assert result["sso_counts"]["matched"] == 1

    # Verify two-tier object + enrichment documents exist
    ztf_doc = db.collection("objects").document("ztf_ZTF26aaabbb").get().to_dict()
    assert ztf_doc is not None
    assert ztf_doc["top_class"] == "SNIa"
    assert ztf_doc["tier"] == 0
    assert ztf_doc["peak_mag"] == pytest.approx(17.6)

    ztf_detail = (
        db.collection("objects")
        .document("ztf_ZTF26aaabbb")
        .collection("detail")
        .document("enrichment")
        .get()
        .to_dict()
    )
    assert ztf_detail is not None
    assert len(ztf_detail["detections"]) == 2

    sso_doc = db.collection("objects").document("ztf_ZTF26sso001").get().to_dict()
    assert sso_doc is not None
    assert sso_doc["sso"]["status"] == "matched"
    assert sso_doc["sso"]["sso_name"] == "Nolan"
    assert sso_doc["sso"]["sso_number"] == 9537

    # Verify rollups/overview and rollups/trends_90d were materialized
    overview = db.collection("rollups").document("overview").get().to_dict()
    assert overview is not None
    assert overview["total_objects"] == 3
    assert overview["solar_ephemerides"]["pluto"]["constellation"] == "Cap"
    assert len(overview["highlights"]) >= 2

    trends = db.collection("rollups").document("trends_90d").get().to_dict()
    assert trends is not None
    assert trends["totals"]["total"] == 3
    assert len(trends["by_day_survey"]) >= 1

    # Verify FCM notifications: topic `transients`, user token threshold, and `solar_matched`
    topics = [p.topic for p in sent_notifications if p.topic]
    assert "transients" in topics
    assert "solar_matched" in topics
    token_pushes = [p for p in sent_notifications if "tok-user-123" in p.tokens]
    assert len(token_pushes) >= 1


def test_bookmark_update_notification_and_weekly_digest() -> None:
    db = FakeFirestoreClient()
    fixed_now = datetime(2026, 11, 11, 12, 0, tzinfo=UTC)
    fs_store = FirestoreStore(db, now_fn=lambda: fixed_now)

    # Initial upsert of an object
    fs_store.upsert_batch(
        1,
        [
            ObjectRow(
                survey="ztf",
                oid="ZTF26saved1",
                meanra=120.0,
                meandec=15.0,
                firstmjd=59900.0,
                lastmjd=59902.0,
                ndet=3,
                n_forced=0,
                stellar=False,
                top_class="CEP",
                top_classifier="lc_classifier",
                top_classifier_version="1.0.0",
                top_probability=0.75,
                raw={},
            )
        ],
        [],
    )

    # User bookmarks `ztf_ZTF26saved1`
    db.collection("users").document("uid-bookmark").set({"fcm_tokens": ["fcm-bm-1"]})
    db.collection("users").document("uid-bookmark").collection("bookmarks").document(
        "ztf_ZTF26saved1"
    ).set(
        {
            "uid": "uid-bookmark",
            "object_key": "ztf_ZTF26saved1",
            "survey": "ztf",
            "oid": "ZTF26saved1",
        }
    )

    # MJD for 2026-11-10 is ~61354.0 (within 7-day window ending 2026-11-11)
    fs_store.upsert_batch(
        2,
        [
            ObjectRow(
                survey="ztf",
                oid="ZTF26saved1",
                meanra=120.0,
                meandec=15.0,
                firstmjd=61352.0,
                lastmjd=61354.5,
                ndet=7,
                n_forced=0,
                stellar=False,
                top_class="SNIa",
                top_classifier="lc_classifier",
                top_classifier_version="1.0.0",
                top_probability=0.93,
                raw={},
            ),
            ObjectRow(
                survey="lsst",
                oid="LSST26flux1",
                meanra=200.0,
                meandec=-10.0,
                firstmjd=61353.0,
                lastmjd=61354.8,
                ndet=5,
                n_forced=0,
                stellar=False,
                top_class="TDE",
                top_classifier="stamp_classifier_rubin_beta",
                top_classifier_version="2.0",
                top_probability=0.89,
                raw={},
            ),
        ],
        [],
    )
    # Enrich Rubin object with positive flux_njy (1e6 nJy -> AB mag 16.4)
    fs_store.enrich_object(
        survey="lsst",
        oid="LSST26flux1",
        detections=[
            DetectionRow(
                survey="lsst",
                oid="LSST26flux1",
                measurement_id="m1",
                mjd=61354.8,
                band="r",
                mag=None,
                mag_err=None,
                flux_njy=1_000_000.0,
                flux_err_njy=1000.0,
                raw={},
            )
        ],
        classifications=[
            ClassificationRow(
                survey="lsst",
                oid="LSST26flux1",
                classifier_name="stamp_classifier_rubin_beta",
                classifier_version="2.0",
                class_name="TDE",
                probability=0.89,
                ranking=1,
            )
        ],
    )

    bm_sent: list[NotificationPayload] = []
    notify_bookmarked_updates(db, fs_store.last_touched_objects, send_fn=bm_sent.append)
    assert len(bm_sent) == 1
    assert bm_sent[0].tokens == ("fcm-bm-1",)
    assert "ZTF26saved1" in bm_sent[0].title

    # Weekly digest selection & rendering should pick LSST26flux1 (AB mag 16.4) as brightest
    weekly_sent: list[NotificationPayload] = []
    digest_out = execute_weekly_digest(
        db,
        send_email=False,
        send_fcm=True,
        send_fn=weekly_sent.append,
        now=fixed_now,
    )
    assert "LSST26flux1" in digest_out["markdown"]
    assert len(weekly_sent) == 1
    assert weekly_sent[0].topic == "weekly_dispatch"


def test_parse_horizons_valid_and_invalid() -> None:
    sample = """
*******************************************************************************
$$SOE
 2026-Nov-11 00:00, , , 305.12345, -22.54321, 14.42, 6.10, 34.8123, 0.01, 71.5, /T, Cap,
$$EOE
*******************************************************************************
"""
    parsed = parse_horizons(sample)
    assert parsed is not None
    assert parsed["ra"] == pytest.approx(305.12345)
    assert parsed["dec"] == pytest.approx(-22.54321)
    assert parsed["mag"] == pytest.approx(14.42)
    assert parsed["constellation"] == "Cap"
    assert parse_horizons("no markers here") is None


def test_require_admin_and_audit_enforces_claim_and_writes_audit_log() -> None:
    db = FakeFirestoreClient()
    with pytest.raises(PermissionError):
        require_admin_and_audit(db, None, action="ingest.rerun")

    with pytest.raises(PermissionError):
        require_admin_and_audit(
            db,
            {"uid": "u1", "token": {"admin": False}},
            action="ingest.rerun",
        )

    uid = require_admin_and_audit(
        db,
        {"uid": "owner-1", "token": {"admin": True, "email": "ken@henseler.app"}},
        action="identify.rerun",
        target="skybot",
    )
    assert uid == "owner-1"
    audits = [s.to_dict() for s in db.collection("audit_log").stream()]
    assert len(audits) == 1
    assert audits[0] is not None
    assert audits[0]["action"] == "identify.rerun"
    assert audits[0]["actor"] == "ken@henseler.app"


class _FakePgCursor:
    def __init__(self) -> None:
        self._last_sql = ""

    def __enter__(self) -> _FakePgCursor:
        return self

    def __exit__(self, *args: object) -> None:
        pass

    def execute(self, sql: str) -> None:
        self._last_sql = sql

    def fetchall(self) -> list[tuple[Any, ...]]:
        if "FROM sso_identifications" in self._last_sql:
            return [
                (
                    "ztf",
                    "ZTF26backfill",
                    "matched",
                    "Ceres",
                    1,
                    "Dwarf",
                    0.25,
                    7.5,
                    61354.0,
                    datetime(2026, 11, 11, tzinfo=UTC),
                    None,
                )
            ]
        if "FROM detections" in self._last_sql:
            return [("ztf", "ZTF26backfill", "m99", 61354.0, "g", 15.2, 0.03, None, None)]
        if "FROM classifications" in self._last_sql:
            return [("ztf", "ZTF26backfill", "lc_classifier", "1.0", "SNIa", 0.96, 1)]
        if "FROM objects" in self._last_sql:
            return [
                (
                    "ztf",
                    "ZTF26backfill",
                    100.0,
                    20.0,
                    61350.0,
                    61354.0,
                    5,
                    "SNIa",
                    0.96,
                    "lc_classifier",
                    "1.0",
                    False,
                    datetime(2026, 11, 11, tzinfo=UTC),
                    datetime(2026, 11, 11, tzinfo=UTC),
                )
            ]
        if "FROM ingest_runs" in self._last_sql:
            return [
                (
                    1,
                    "alerce:ztf",
                    datetime(2026, 11, 11, tzinfo=UTC),
                    datetime(2026, 11, 11, tzinfo=UTC),
                    "succeeded",
                    10,
                    10,
                    20,
                    10,
                    0,
                    None,
                )
            ]
        if "FROM audit_log" in self._last_sql:
            return [
                (
                    1,
                    datetime(2026, 11, 11, tzinfo=UTC),
                    "github:16056018",
                    "ingest.rerun",
                    "all",
                    "127.0.0.1",
                    "pytest",
                    {"source": "backfill"},
                )
            ]
        return []


class _FakePgConn:
    def cursor(self) -> _FakePgCursor:
        return _FakePgCursor()


def test_backfill_neon_to_firestore_migrates_all_entities() -> None:
    db = FakeFirestoreClient()
    fs_store = FirestoreStore(db)
    summary = backfill_neon_to_firestore(
        _FakePgConn(),
        fs_store,
        now=datetime(2026, 11, 11, 12, 0, tzinfo=UTC),
    )
    assert summary.objects_migrated == 1
    assert summary.details_migrated == 1
    assert summary.sso_migrated == 1
    assert summary.runs_migrated == 1
    assert summary.audit_logs_migrated == 1

    doc = db.collection("objects").document(object_doc_id("ztf", "ZTF26backfill")).get().to_dict()
    assert doc is not None
    assert doc["peak_mag"] == pytest.approx(15.2)
    assert doc["sso"]["sso_name"] == "Ceres"
