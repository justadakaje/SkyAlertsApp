from __future__ import annotations

import json

import httpx

from skyalerts_ingest import explore
from tests.conftest import load_fixture


def router(lsst_status: int = 200, ztf_status: int = 200):
    def handler(req: httpx.Request) -> httpx.Response:
        host, path = req.url.host, req.url.path
        if host == "ztf.test":
            if ztf_status != 200:
                return httpx.Response(ztf_status)
            if path == "/ztf/v1/objects/":
                return httpx.Response(200, json=load_fixture("ztf_objects.json"))
            if path.endswith("/probabilities"):
                return httpx.Response(200, json=load_fixture("ztf_probabilities.json"))
            if path == "/ztf/v1/classifiers/":
                return httpx.Response(200, json=load_fixture("ztf_classifiers.json"))
        if host == "lsst.test":
            if lsst_status != 200:
                return httpx.Response(lsst_status)
            if path == "/object_api/list_objects":
                return httpx.Response(200, json=load_fixture("lsst_objects.json"))
            if path == "/probability_api/probability":
                return httpx.Response(200, json=load_fixture("ztf_probabilities.json"))
        return httpx.Response(404)

    return handler


def test_explore_both_surveys_writes_outputs(make_client, tmp_path, capsys):
    client, seen = make_client(router())
    md_path = tmp_path / "summary.md"
    rc = explore.main(
        [
            "--limit",
            "10",
            "--probabilities",
            "2",
            "--out",
            str(tmp_path),
            "--markdown",
            str(md_path),
        ],
        client=client,
    )
    assert rc == 0
    for name in (
        "ztf_objects.json",
        "lsst_objects.json",
        "ztf_probabilities.json",
        "lsst_probabilities.json",
        "ztf_classifiers.json",
    ):
        assert (tmp_path / name).exists(), name
    assert len(json.loads((tmp_path / "ztf_probabilities.json").read_text())) == 2
    md = md_path.read_text()
    assert "## ZTF" in md and "## LSST" in md
    assert "## ZTF" in capsys.readouterr().out
    # 2 list calls + 2+2 probability calls + 1 classifiers call
    assert len(seen) == 7


def test_one_survey_down_still_succeeds(make_client, tmp_path):
    client, _ = make_client(router(lsst_status=404))
    rc = explore.main(["--out", str(tmp_path), "--probabilities", "0"], client=client)
    assert rc == 0
    assert not (tmp_path / "lsst_objects.json").exists()


def test_all_surveys_down_fails(make_client, tmp_path):
    client, _ = make_client(router(lsst_status=404, ztf_status=404))
    rc = explore.main(["--probabilities", "0"], client=client)
    assert rc == 1
