"""A deterministic teaching system that our tests can challenge."""
from healthcare_quality import __version__
from healthcare_quality.catalog import PLANS, SERVICES, CONTRACT_HASH

DEFECTS = ("none", "eligibility", "coverage", "network", "authorization", "formulary", "deductible", "limit")


class ContractError(ValueError):
    """A request does not satisfy HC-001."""


def validate_request(payload):
    required = {"plan_id", "service", "amount_cents"}
    flags = {"active", "in_network", "authorized", "formulary"}
    if not isinstance(payload, dict) or not required <= payload.keys() or payload.keys() - required - flags:
        raise ContractError("Provide plan_id, service, amount_cents and optional coverage flags only")
    if not isinstance(payload["plan_id"], str) or not any(p["id"] == payload["plan_id"] for p in PLANS):
        raise ContractError("Unknown plan_id")
    if not isinstance(payload["service"], str) or payload["service"] not in SERVICES:
        raise ContractError("Unknown service")
    if type(payload["amount_cents"]) is not int or not 1 <= payload["amount_cents"] <= 100000000:
        raise ContractError("amount_cents must be an integer from 1 to 100000000")
    for flag in flags:
        if flag in payload and type(payload[flag]) is not bool:
            raise ContractError(f"{flag} must be a boolean")
    return {**payload, **{flag: payload.get(flag, True) for flag in flags}}


def evaluate_claim(payload, *, defect="none"):
    """Evaluate once; keep no patient, member, or claim record.

    Defect modes are available only through Python for controlled experiments.
    The public HTTP endpoint always uses defect='none'.
    """
    if defect not in DEFECTS:
        raise ValueError("Unknown defect")
    data = validate_request(payload)
    plan = next(plan for plan in PLANS if plan["id"] == data["plan_id"])
    trace = [{"rule_id": "HC-001", "outcome": "passed", "detail": "Request satisfies the input contract"}]

    def result(decision, reason, payout=0):
        return {"version": __version__, "synthetic": True, "contract_hash": CONTRACT_HASH,
                "request": data, "plan_name": plan["name"], "decision": decision,
                "reason": reason, "payout_cents": payout, "trace": trace}

    checks = [
        ("HC-002", "INACTIVE_POLICY", not data["active"] and defect != "eligibility"),
        ("HC-003", "SERVICE_NOT_COVERED", data["service"] not in plan["services"] and defect != "coverage"),
        ("HC-004", "OUT_OF_NETWORK", plan["network_required"] and not data["in_network"] and defect != "network"),
        ("HC-005", "AUTH_REQUIRED", data["service"] in plan["authorization_services"] and not data["authorized"] and defect != "authorization"),
        ("HC-006", "NON_FORMULARY", data["service"] == "prescription" and not data["formulary"] and defect != "formulary"),
    ]
    for rule, reason, denied in checks:
        trace.append({"rule_id": rule, "outcome": "denied" if denied else "passed", "detail": reason if denied else "No denial triggered under this contract"})
        if denied:
            return result("denied", reason)
    after_deductible = max(data["amount_cents"] - plan["deductible_cents"], 0)
    if defect == "deductible":
        after_deductible = data["amount_cents"]
    payout = after_deductible if defect == "limit" else min(after_deductible, plan["limit_cents"])
    trace.append({"rule_id": "HC-007", "outcome": "passed", "detail": f"Claim {data['amount_cents']} cents; deductible {plan['deductible_cents']}; cap {plan['limit_cents']}; payout {payout}"})
    return result("approved", "COVERED", payout)
