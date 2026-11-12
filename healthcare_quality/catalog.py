"""Versioned synthetic contracts. Actual plan documents are outside V1."""
from healthcare_quality import __version__
from copy import deepcopy
import hashlib
import json
from pathlib import Path

DATA = Path(__file__).parent / "data"
PLANS = json.loads((DATA / "plans.json").read_text())
RULES = json.loads((DATA / "rules.json").read_text())
SERVICES = tuple(sorted({service for plan in PLANS for service in plan["services"]}))
CONTRACT_HASH = hashlib.sha256(json.dumps({"plans": PLANS, "rules": RULES}, sort_keys=True).encode()).hexdigest()


def get_catalog():
    return deepcopy({"version": __version__, "synthetic": True, "contract_hash": CONTRACT_HASH,
                     "plans": PLANS, "rules": RULES, "services": SERVICES})
