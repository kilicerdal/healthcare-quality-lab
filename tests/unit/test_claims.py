"""Explicit expectations from the teaching contract; no production oracle reuse."""
import json
from pathlib import Path
import pytest
from healthcare_quality.claims import ContractError, evaluate_claim

GOLDEN = json.loads((Path(__file__).parents[1] / "data/golden.json").read_text())
BASE = {"plan_id": "commercial_ppo", "service": "medical", "amount_cents": 100000}
pytestmark = [pytest.mark.unit, pytest.mark.regression]


@pytest.mark.smoke
def test_deductible_is_subtracted():
    result = evaluate_claim(BASE)
    assert result["decision"] == "approved"
    assert result["payout_cents"] == 90000  # $1,000 minus the synthetic $100 deductible.
    assert result["trace"][-1]["rule_id"] == "HC-007"


@pytest.mark.parametrize("case", GOLDEN, ids=[c["id"]+"-"+c["title"] for c in GOLDEN])
def test_reviewed_contract_examples(case):
    result = evaluate_claim(case["request"])
    assert {key: result[key] for key in case["expected"]} == case["expected"]
    assert result["synthetic"] is True
    if result["decision"] == "denied":
        assert result["trace"][-1]["rule_id"] == case["rule_id"]
        assert result["trace"][-1]["outcome"] == "denied"


@pytest.mark.parametrize("amount", [0, -1, 100000001, True, False, 1.5, "100", None, [], {}])
def test_reject_invalid_amount(amount):
    with pytest.raises(ContractError, match="amount_cents must be an integer"):
        evaluate_claim({**BASE, "amount_cents": amount})


@pytest.mark.parametrize("flag", ["active", "in_network", "authorized", "formulary"])
@pytest.mark.parametrize("invalid", ["false", 0, None])
def test_flags_must_be_actual_booleans(flag, invalid):
    with pytest.raises(ContractError, match=f"{flag} must be a boolean"):
        evaluate_claim({**BASE, flag: invalid})


@pytest.mark.parametrize("payload", [None, [], "hello", {}, {"plan_id":"commercial_ppo"}, {**BASE,"defect":"coverage"}])
def test_reject_malformed_request(payload):
    with pytest.raises(ContractError):
        evaluate_claim(payload)


@pytest.mark.parametrize("key,value", [("plan_id",[]),("plan_id","missing"),("service",{}),("service","missing")])
def test_reject_unknown_identifiers(key,value):
    with pytest.raises(ContractError):
        evaluate_claim({**BASE,key:value})


@pytest.mark.sanity
def test_authorization_change_check():
    request = {**BASE,"plan_id":"medicare_advantage","service":"hospital","authorized":False}
    assert evaluate_claim(request)["reason"] == "AUTH_REQUIRED"
    assert evaluate_claim({**request,"authorized":True})["decision"] == "approved"


def test_requests_do_not_leak_state_or_mutate_input():
    original = dict(BASE)
    first = evaluate_claim(BASE)
    first["request"]["active"] = False
    assert BASE == original
    assert evaluate_claim(BASE)["decision"] == "approved"


def test_unknown_defect_is_rejected():
    with pytest.raises(ValueError, match="Unknown defect"):
        evaluate_claim(BASE, defect="unknown")


def test_claim_equal_to_cap_is_approved_after_deductible():
    # An actual local-model suggestion incorrectly expected DENIED here.
    # HC-007 subtracts the deductible before applying the payout cap.
    result = evaluate_claim({**BASE, "amount_cents": 200000})
    assert result["decision"] == "approved"
    assert result["reason"] == "COVERED"
    assert result["payout_cents"] == 190000
