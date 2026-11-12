import pytest
from healthcare_quality.catalog import CONTRACT_HASH

pytestmark = [pytest.mark.api, pytest.mark.regression]
BASE = {"plan_id":"commercial_ppo","service":"medical","amount_cents":100000}


@pytest.mark.smoke
def test_health_and_home_are_available(client):
    assert client.get("/api/health").json == {"status":"ok","version":"5.6.0"}
    assert client.get("/").status_code == 200


def test_catalog_returns_versioned_synthetic_contracts(client):
    response = client.get("/api/catalog")
    assert response.status_code == 200
    assert response.json["synthetic"] is True
    assert response.json["contract_hash"] == CONTRACT_HASH
    assert len(response.json["plans"]) == 8


def test_evaluation_contract_contains_decision_trace_and_provenance(client):
    response = client.post("/api/evaluate",json=BASE)
    assert response.status_code == 200
    assert response.json["decision"] == "approved"
    assert response.json["payout_cents"] == 90000
    assert [t["rule_id"] for t in response.json["trace"]] == [f"HC-{i:03}" for i in range(1,8)]
    assert response.json["contract_hash"] == CONTRACT_HASH
    assert response.headers["Cache-Control"] == "no-store"


@pytest.mark.sanity
def test_authorization_denial_is_valid_business_response(client):
    response = client.post("/api/evaluate",json={**BASE,"plan_id":"medicare_advantage","service":"hospital","authorized":False})
    assert response.status_code == 200  # A business denial is not a server error.
    assert response.json["reason"] == "AUTH_REQUIRED"
    assert response.json["payout_cents"] == 0
    assert response.json["trace"][-1]["rule_id"] == "HC-005"


@pytest.mark.parametrize("payload", [None, [], {}, {**BASE,"amount_cents":True}, {**BASE,"defect":"deductible"}, {**BASE,"active":"false"}])
def test_invalid_json_contract_returns_400(client,payload):
    import json
    response = client.post("/api/evaluate",data=json.dumps(payload),content_type="application/json")
    assert response.status_code == 400
    assert response.json["rule_id"] == "HC-001"


def test_malformed_json_returns_actionable_400(client):
    response = client.post("/api/evaluate",data='{"plan_id":',content_type="application/json")
    assert response.status_code == 400
    assert response.json["rule_id"] == "HC-001"


def test_non_json_request_returns_415(client):
    assert client.post("/api/evaluate",data="plain text").status_code == 415


def test_oversized_request_returns_413(client):
    response = client.post("/api/evaluate",data='x'*17000,content_type="application/json")
    assert response.status_code == 413
    assert response.json["rule_id"] == "HC-001"


def test_unknown_routes_and_wrong_methods(client):
    assert client.get("/api/missing").status_code == 404
    assert client.get("/api/evaluate").status_code == 405


def test_verification_endpoint_is_explicit_about_missing_or_stale_evidence(client):
    response = client.get("/api/verification")
    assert response.status_code == 200
    assert response.json["status"] in {"not_run","stale","passed","failed"}


def test_engineering_report_is_served_as_html(client):
    response=client.get("/report")
    assert response.status_code==200
    assert response.mimetype=="text/html"
    assert b"Healthcare Quality Lab V5.6 Engineering Report" in response.data
