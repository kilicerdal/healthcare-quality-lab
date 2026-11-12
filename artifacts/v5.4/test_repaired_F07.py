"""Trusted pytest wrapper around explicitly reviewed case data. SNAPSHOT records expectation provenance; no generated code is executed."""
import json
import pytest
from healthcare_quality.ai_schema import contract_fingerprint, digest, validate_cases
from healthcare_quality.ai_runner import run_cases
from healthcare_quality import reference
from healthcare_quality.assertion_quality import assess, policy_fingerprint
SNAPSHOT = json.loads('{"approval": {"assertion_policy_fingerprint": "e5280e96161fa7f6fa48c100937e2a6431e42e01ec1888c44f3ca4e72fe3a2fa", "at": "2026-11-12T15:06:19.052946+00:00", "expectations_checked": true, "hashes": {"AI-001": "ef67b1bc5ff634f6fe78f342bbbca56190a4e584aec4f7875c7bd749eedd35e0"}, "identity_mode": "Local attestation label, not authenticated human identity", "note": "Known failure expectations checked against authored literal results, reference and unchanged scenario. Engineering validation only, not authenticated human approval.", "reference_fingerprint": "0271f70cf99766ccad19129f0bbe82d6e786cbef6155bb0efdad1e8ddf2fe9be", "reviewer_label": "Codex engineering operator (automated attestation)", "revision": 2}, "cases": [{"assumptions": [], "id": "AI-001", "rationale": "Evaluate a medical claim for a commercial PPO member to ensure correct payout calculation.", "rule_ids": ["HC-007"], "steps": [{"action": "evaluate", "actor": "none", "data": {"amount_cents": 286450, "plan_id": "commercial_ppo", "service": "medical"}, "expect": {"decision": "approved", "payout_cents": 200000, "reason": "COVERED", "status": 200}}], "title": "Evaluate Medical Claim for Commercial PPO"}], "contract_fingerprint": "3b062e81b83724527d2afc4c8cb85cd07849d074f682023038eaed89825c43dc", "correction_of": "37933fb6b7a044ad981480b085f2d851", "expectation_origin": "reference_guided_ai", "experiment_id": "64f6b5d21333420c9c7699e52de83107", "reference_assisted_of": null, "source_ids": ["HC-007"]}')
pytestmark = [pytest.mark.ai, pytest.mark.regression]
@pytest.mark.parametrize("case", SNAPSHOT["cases"], ids=lambda case: case["id"])
def test_reviewed_ollama_case(case):
    assert SNAPSHOT["contract_fingerprint"] == contract_fingerprint(), "Stale contract/schema; review again"
    assert digest(case) == SNAPSHOT["approval"]["hashes"][case["id"]], "Snapshot changed"
    assert validate_cases([case], SNAPSHOT["source_ids"])[0]["valid"]
    assert SNAPSHOT["approval"].get("assertion_policy_fingerprint") == policy_fingerprint(), "Stale assertion policy"
    assert assess(case)["complete"], "Incomplete business assertions"
    assert SNAPSHOT["approval"].get("reference_fingerprint") == reference.fingerprint(), "Stale independent reference"
    assert reference.check(case)["status"] == "matched", "Reference mismatch"
    result = run_cases([case])
    assert result["failed"] == 0, json.dumps(result, indent=2)
