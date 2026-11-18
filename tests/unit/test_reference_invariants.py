"""Authored literal anchors plus invariants; no SUT-derived expected answers."""
import pytest
from healthcare_quality import reference
pytestmark=[pytest.mark.unit,pytest.mark.regression]

# Independently inspectable arithmetic anchors, not an external clinical validation.
GOLDENS=[(1,0),(9973,0),(10000,0),(10001,1),(137891,127891),
         (209999,199999),(210000,200000),(210003,200000),(99999997,200000)]

@pytest.mark.parametrize('amount,payout',GOLDENS)
def test_reference_matches_literal_teaching_contract(amount,payout):
    result,_=reference.evaluate({'plan_id':'commercial_ppo','service':'medical','amount_cents':amount})
    assert result=={'status':200,'decision':'approved','reason':'COVERED','payout_cents':payout}

def test_fixture_facts_cannot_drift_together_with_both_algorithms():
    assert len(reference.PLANS)==8
    for plan in reference.PLANS.values():
        assert plan['deductible_cents']==10000
        assert plan['limit_cents']==200000

def test_monotonic_bounded_payout_across_all_authored_plans():
    for plan in reference.PLANS.values():
        results=[reference.evaluate({'plan_id':plan['id'],'service':plan['services'][0],'amount_cents':n})[0]['payout_cents'] for n,_ in GOLDENS]
        assert results==sorted(results)
        assert all(0<=value<=200000 for value in results)
        assert all(value<=amount for value,(amount,_) in zip(results,GOLDENS))

def test_reference_rejected_replay_preserves_entire_state():
    model=reference.Model()
    def step(action,actor,data):return model.step({'action':action,'actor':actor,'data':data})[0]
    step('submit','customer-m100',{'claim_id':'INV-100','member_id':'M100','service':'medical','amount_cents':137891})
    step('transition','adjuster-demo',{'claim_id':'INV-100','target':'approved'})
    before=step('transition','finance-demo',{'claim_id':'INV-100','target':'paid'})
    assert step('transition','finance-demo',{'claim_id':'INV-100','target':'paid'})=={'status':409,'error':'INVALID_TRANSITION'}
    assert step('read','customer-m100',{'claim_id':'INV-100'})==before
    assert before['payment_cents']==127891 and before['revision']==3 and before['event_count']==3
