"""Named engineering fault controls. Never accepts source or code from a model."""
from copy import deepcopy
from contextlib import contextmanager
from unittest.mock import patch
from healthcare_quality import benefit_claims

@contextmanager
def seeded_payout():
    original=benefit_claims.calculate
    def wrong(*a,**kw):
        value=deepcopy(original(*a,**kw));value['totals']['payout_cents']+=1;return value
    with patch.object(benefit_claims,'calculate',wrong):yield
