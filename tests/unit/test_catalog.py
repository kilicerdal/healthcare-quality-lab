import pytest
from healthcare_quality.catalog import PLANS, RULES, get_catalog

pytestmark = [pytest.mark.unit, pytest.mark.regression]


def test_catalog_has_unique_ids_and_all_required_families():
    assert len(PLANS) == 8
    assert len({p["id"] for p in PLANS}) == 8
    assert len({r["id"] for r in RULES}) == 7
    assert {p["family"] for p in PLANS} == {"Medicare","Commercial","Supplemental"}
    assert sum("Advantage" in p["name"] for p in PLANS) == 1


def test_catalog_snapshot_does_not_allow_mutating_global_contracts():
    snapshot = get_catalog()
    snapshot["plans"][0]["services"].clear()
    assert get_catalog()["plans"][0]["services"]


def test_plan_contracts_are_internally_consistent():
    for plan in PLANS:
        assert set(plan["authorization_services"]) <= set(plan["services"])
        assert type(plan["network_required"]) is bool
        assert plan["deductible_cents"] == 10000
        assert plan["limit_cents"] == 200000
