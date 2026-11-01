from __future__ import annotations

import math

import pytest

from skyalerts_ingest.normalize import (
    LSST_RAW_KEYS,
    ZTF_RAW_KEYS,
    normalize_detection,
    normalize_object,
    normalize_probability,
)
from tests.conftest import load_fixture


@pytest.mark.parametrize("survey", ["ztf", "lsst"])
def test_fixture_rows_normalize(survey):
    rows = load_fixture(f"{survey}_objects.json")["items"]
    for row in rows:
        out = normalize_object(survey, row)
        assert out is not None
        obj, cls = out
        assert obj.survey == survey and obj.oid == str(row["oid"])
        if cls is not None:
            assert 0 <= cls.probability <= 1
            assert obj.top_class == cls.class_name


def test_lsst_live_shape():
    row = {
        "oid": 313752245626208263,
        "meanra": 8.0081,
        "meandec": -44.35,
        "firstmjd": 61001.05,
        "lastmjd": 61344.31,
        "n_det": 31,
        "n_forced": 40,
        "stellar": None,
        "class_name": "VS",
        "classifier_name": "stamp_classifier_rubin_beta_20260421",
        "classifier_version": "2.0.2",
        "probability": 0.92,
        "ranking": 1,
    }
    obj, cls = normalize_object("lsst", row)
    assert obj.oid == "313752245626208263"
    assert (obj.ndet, obj.n_forced, obj.stellar) == (31, 40, None)
    assert cls.classifier_version == "2.0.2" and cls.ranking == 1


def test_ztf_without_classifier_has_no_classification():
    row = {
        "oid": "ZTF26acdjxpj",
        "class": None,
        "classifier": None,
        "probability": None,
        "ndethist": "1",
        "ndet": 1,
        "meanra": 189.6,
        "meandec": 12.8,
        "lastmjd": 61342.5,
    }
    obj, cls = normalize_object("ztf", row)
    assert cls is None and obj.top_class is None and obj.ndet == 1


@pytest.mark.parametrize(
    "patch",
    [
        {"oid": None},
        {"oid": ""},
        {"oid": "x" * 65},
    ],
)
def test_rejects_bad_oid(patch):
    assert normalize_object("lsst", {"oid": "1"} | patch) is None


def test_sanitises_untrusted_values():
    row = {
        "oid": "ZTF\x0026abc",
        "meanra": 360.0,
        "meandec": 120,  # out of range -> None
        "lastmjd": math.nan,
        "class": "SN\n<script>" + "A" * 300,
        "classifier": "stamp_classifier",
        "probability": 1.5,  # out of range -> no classification
        "ndet": True,  # bool is not an int
    }
    obj, cls = normalize_object("ztf", row)
    assert obj.oid == "ZTF26abc"
    assert obj.meanra == 0.0 and obj.meandec is None and obj.lastmjd is None
    assert obj.ndet is None
    assert cls is None and obj.top_class is None


def test_unknown_survey_raises():
    with pytest.raises(ValueError):
        normalize_object("ptf", {"oid": "1"})
    with pytest.raises(ValueError):
        normalize_detection("ptf", "1", {"mjd": 60000.0, "candid": "1"})
    with pytest.raises(ValueError):
        normalize_probability(
            "ptf", "1", {"classifier_name": "c", "class_name": "SN", "probability": 0.5}
        )


def test_lsst_detections_live_fixture():
    rows = load_fixture("lsst_detections_live.json")
    assert len(rows) == 20
    oid = "313708285401235521"
    for row in rows:
        det = normalize_detection("lsst", oid, row)
        assert det is not None
        assert det.survey == "lsst" and det.oid == oid
        assert det.measurement_id == str(row["measurement_id"])
        assert det.band in {"u", "g", "r", "i", "z", "y"}
        assert det.flux_njy == pytest.approx(row["psfFlux"])
        assert det.flux_err_njy == pytest.approx(row["psfFluxErr"])
        assert det.mag is not None and 10.0 < det.mag < 30.0
        assert det.mag_err is not None and det.mag_err > 0.0
        assert set(det.raw) == set(LSST_RAW_KEYS)


def test_ztf_detections_live_fixture():
    rows = load_fixture("ztf_detections_live.json")
    assert len(rows) == 32
    oid = "ZTF18acwycia"
    for row in rows:
        det = normalize_detection("ztf", oid, row)
        assert det is not None
        assert det.survey == "ztf" and det.oid == oid
        assert det.measurement_id == row["candid"]
        assert det.band in {"g", "r", "i"}
        assert det.mag == pytest.approx(row["magpsf"])
        assert det.mag_err == pytest.approx(row["sigmapsf"])
        assert det.flux_njy is None and det.flux_err_njy is None
        assert set(det.raw) <= set(ZTF_RAW_KEYS)
        assert "candid" in det.raw and "magap" not in det.raw


def test_lsst_negative_or_zero_flux_gives_mag_none():
    base = dict(load_fixture("lsst_detections_live.json")[0])
    neg = normalize_detection(
        "lsst", 313708285401235521, base | {"psfFlux": -450.25, "isNegative": True}
    )
    assert neg is not None
    assert neg.flux_njy == -450.25
    assert neg.flux_err_njy == pytest.approx(base["psfFluxErr"])
    assert neg.mag is None and neg.mag_err is None
    assert neg.raw["isNegative"] is True

    zero = normalize_detection("lsst", 313708285401235521, base | {"psfFlux": 0.0})
    assert zero is not None and zero.flux_njy == 0.0 and zero.mag is None and zero.mag_err is None


def test_detection_band_mapping_and_slim_raw_cleaning():
    # LSST uses band_map first, then fallback when band_map is absent
    row = {
        "measurement_id": 999,
        "mjd": 61000.5,
        "band": 6,
        "psfFlux": 1000.0,
        "psfFluxErr": 10.0,
        "snr": math.nan,
        "has_stamp": True,
        "extra_bloat": "x" * 5000,
    }
    det = normalize_detection("lsst", 12345, row)
    assert det is not None
    assert det.band == "u"
    assert det.mag == pytest.approx(-2.5 * 3.0 + 31.4)
    assert det.mag_err == pytest.approx(1.0857 * 10.0 / 1000.0)
    assert det.raw == {"band": 6, "snr": None, "has_stamp": True}

    # ZTF fid mapping and out-of-range mag handling
    zrow = {"candid": "c1", "mjd": 61000.0, "fid": 3, "magpsf": 45.0, "sigmapsf": 0.1}
    zdet = normalize_detection("ztf", "ZTF26a", zrow)
    assert zdet is not None
    assert zdet.band == "i"
    assert zdet.mag is None and zdet.mag_err is None


def test_detection_rejects_missing_id_or_mjd():
    assert normalize_detection("ztf", "ZTF26a", {"mjd": 61000.0}) is None
    assert normalize_detection("lsst", "1", {"mjd": 61000.0}) is None
    assert normalize_detection("ztf", "ZTF26a", {"candid": "c1", "mjd": -1.0}) is None
    assert normalize_detection("ztf", "", {"candid": "c1", "mjd": 61000.0}) is None


@pytest.mark.parametrize(
    ("survey", "oid", "fixture"),
    [
        ("lsst", "313708285401235521", "lsst_probabilities_live.json"),
        ("ztf", "ZTF18acwycia", "ztf_probabilities_live.json"),
    ],
)
def test_probabilities_live_fixtures(survey, oid, fixture):
    rows = load_fixture(fixture)
    assert len(rows) > 0
    for row in rows:
        cls = normalize_probability(survey, oid, row)
        assert cls is not None
        assert cls.survey == survey and cls.oid == oid
        assert isinstance(cls.classifier_version, str) and cls.classifier_version == str(
            row["classifier_version"]
        )
        assert 0.0 <= cls.probability <= 1.0
        assert cls.ranking is not None and cls.ranking >= 1


def test_probability_validation():
    assert (
        normalize_probability(
            "lsst", "1", {"classifier_name": "c", "class_name": "SN", "probability": 1.2}
        )
        is None
    )
    cls = normalize_probability(
        "lsst",
        123,
        {
            "classifier_name": "c",
            "classifier_version": None,
            "class_name": "SN",
            "probability": 0.5,
            "ranking": 0,
        },
    )
    assert cls is not None and cls.classifier_version == "" and cls.ranking is None
