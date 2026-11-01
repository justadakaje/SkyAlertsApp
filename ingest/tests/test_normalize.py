from __future__ import annotations

import math

import pytest

from skyalerts_ingest.normalize import normalize_object
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
