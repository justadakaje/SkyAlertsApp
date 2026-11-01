from __future__ import annotations

import httpx
import pytest

from skyalerts_ingest.alerce_client import USER_AGENT, AlerceError, AlerceSchemaError
from tests.conftest import load_fixture


def ok(json_body):
    return lambda req: httpx.Response(200, json=json_body)


def test_ztf_list_objects_routes_and_params(make_client):
    client, seen = make_client(ok(load_fixture("ztf_objects.json")))
    items = client.list_objects("ztf", page_size=10, class_name="SNIa", classifier="lc_classifier")
    req = seen[0]
    assert req.url.host == "ztf.test"
    assert req.url.path == "/ztf/v1/objects"
    q = dict(req.url.params)
    assert q["class"] == "SNIa"  # legacy API name
    assert "class_name" not in q
    assert q["page_size"] == "10"
    assert q["order_by"] == "lastmjd" and q["order_mode"] == "DESC"
    assert "probability" not in q  # None params dropped
    assert req.headers["User-Agent"] == USER_AGENT
    assert len(items) == len(load_fixture("ztf_objects.json")["items"])


def test_lsst_list_objects_routes_and_params(make_client):
    client, seen = make_client(ok(load_fixture("lsst_objects.json")))
    client.list_objects("lsst", page_size=5, class_name="SN")
    req = seen[0]
    assert req.url.host == "lsst.test"
    assert req.url.path == "/object_api/list_objects"
    q = dict(req.url.params)
    assert q["survey"] == "lsst"
    assert q["class_name"] == "SN"
    assert "class" not in q


def test_rejects_unknown_survey_and_bad_page_size(make_client):
    client, _ = make_client(ok({"items": []}))
    with pytest.raises(ValueError):
        client.list_objects("ptf")  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        client.list_objects("ztf", page_size=0)
    with pytest.raises(ValueError):
        client.list_objects("ztf", page_size=101)


def test_retries_on_429_honouring_retry_after(make_client, fake_time):
    responses = iter(
        [
            httpx.Response(429, headers={"Retry-After": "7"}),
            httpx.Response(503),
            httpx.Response(200, json={"items": []}),
        ]
    )
    client, seen = make_client(lambda req: next(responses))
    assert client.list_objects("ztf") == []
    assert len(seen) == 3
    assert fake_time.sleeps[0] == 7.0  # Retry-After honoured
    assert 2.0 <= fake_time.sleeps[1] <= 3.0  # attempt 2: 2^1 + jitter(<=1)


def test_retry_after_is_capped(make_client, fake_time):
    responses = iter(
        [httpx.Response(429, headers={"Retry-After": "86400"}), httpx.Response(200, json=[])]
    )
    client, _ = make_client(lambda req: next(responses), max_backoff=60.0)
    client.ztf_classifiers()
    assert fake_time.sleeps == [60.0]


def test_gives_up_after_max_attempts(make_client, fake_time):
    client, seen = make_client(lambda req: httpx.Response(502), max_attempts=3)
    with pytest.raises(AlerceError, match="Gave up after 3 attempts"):
        client.list_objects("ztf")
    assert len(seen) == 3
    assert len(fake_time.sleeps) == 2  # no sleep after the final attempt


def test_transport_errors_are_retried(make_client):
    calls = {"n": 0}

    def handler(req):
        calls["n"] += 1
        if calls["n"] == 1:
            raise httpx.ConnectTimeout("boom", request=req)
        return httpx.Response(200, json={"items": []})

    client, _ = make_client(handler)
    assert client.list_objects("ztf") == []
    assert calls["n"] == 2


def test_4xx_is_not_retried(make_client, fake_time):
    client, seen = make_client(lambda req: httpx.Response(404, text="nope"))
    with pytest.raises(AlerceError) as ei:
        client.list_objects("ztf")
    assert ei.value.status == 404
    assert len(seen) == 1
    assert fake_time.sleeps == []


def test_schema_errors(make_client):
    client, _ = make_client(ok({"not_items": []}))
    with pytest.raises(AlerceSchemaError):
        client.list_objects("ztf")
    client, _ = make_client(ok({"items": [1, 2]}))
    with pytest.raises(AlerceSchemaError):
        client.list_objects("ztf")
    client, _ = make_client(lambda req: httpx.Response(200, text="<html>"))
    with pytest.raises(AlerceSchemaError):
        client.list_objects("ztf")


def test_rate_limiter_spaces_requests(make_client, fake_time):
    client, _ = make_client(ok({"items": []}), min_interval=1.0)
    for _ in range(3):
        client.list_objects("ztf")
    # first request is immediate; the next two wait a full interval (clock only moves on sleep)
    assert fake_time.sleeps == [1.0, 1.0]


def test_ztf_probabilities_encodes_oid(make_client):
    client, seen = make_client(ok(load_fixture("ztf_probabilities.json")))
    probs = client.probabilities("ztf", "ZTF26aaaaaaa/../../admin")
    assert seen[0].url.raw_path.startswith(b"/ztf/v1/objects/ZTF26aaaaaaa%2F..%2F..%2Fadmin/")
    assert probs and all("classifier_name" in p for p in probs)


def test_lsst_probabilities_uses_survey_id(make_client):
    client, seen = make_client(ok({"items": load_fixture("ztf_probabilities.json")}))
    probs = client.probabilities("lsst", 170032901203689551)
    q = dict(seen[0].url.params)
    assert seen[0].url.path == "/probability_api/probability"
    assert q == {"survey_id": "lsst", "oid": "170032901203689551"}
    assert len(probs) == 3


def test_does_not_follow_redirects(make_client):
    client, _ = make_client(
        lambda req: httpx.Response(302, headers={"Location": "https://evil.test/"})
    )
    with pytest.raises(AlerceError, match="redirect") as ei:
        client.ztf_classifiers()
    assert ei.value.status == 302
