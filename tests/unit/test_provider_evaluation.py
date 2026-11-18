import json
from copy import deepcopy
import pytest
from healthcare_quality import focused,reference
from healthcare_quality.provider_evaluation import request_for,assess,summarize,cohort
pytestmark=[pytest.mark.unit,pytest.mark.ai,pytest.mark.regression]

def authored_response(data):
    context,_,_=request_for(data);expected,_=reference.evaluate(data)
    return {'assessment':focused.expected_assessment(context),'expect':{k:expected.get(k) for k in ['status','decision','reason','error','payout_cents']}}

def test_correct_fixture_is_only_eligible_never_approved():
    data=cohort()['cases'][0]['data'];value=assess(data,{'text':json.dumps(authored_response(data))})
    assert value['accepted_for_review'] is True and value['approval']=='unapproved'

def test_plausible_wrong_payout_cannot_pass_checker():
    data=cohort()['cases'][0]['data'];raw=authored_response(data)
    raw['expect']['payout_cents']+=1
    result=assess(data,{'text':json.dumps(raw)})
    assert result['schema_valid'] and not result['reference_matched'] and not result['accepted_for_review']

def test_correct_expectation_with_wrong_calculation_stays_blocked():
    data={'plan_id':'commercial_ppo','service':'medical','amount_cents':137893,'active':False}
    raw=authored_response(data);raw['assessment']['payout_cents']=None
    result=assess(data,{'text':json.dumps(raw)})
    assert result['literal_match'] and not result['calculation_matched'] and not result['accepted_for_review']

def test_incomplete_assertions_are_not_silently_filled():
    data=cohort()['cases'][0]['data'];raw=authored_response(data);raw['expect']['payout_cents']=None
    result=assess(data,{'text':json.dumps(raw)})
    assert not result['assertions_complete'] and not result['accepted_for_review']

def test_errors_and_incorrect_trials_count_in_repeatability_denominator():
    rows=[{'provider':'openai','scenario':'one','assessment':{'accepted_for_review':True,'case':{'steps':[{'expect':{'status':200}}]}},'response':{'latency_ms':1,'usage_estimate_usd':'.01'}},
          {'provider':'openai','scenario':'one','error_type':'TimeoutError'}]
    summary=summarize(rows)['openai']
    assert summary['attempts']==2 and summary['rejected_or_error']==1
    assert not summary['repeatability'][0]['identical_expectations']
    assert not summary['repeatability'][0]['all_accepted']
    assert summary['cost_per_accepted_case_usd']=='0.01'
