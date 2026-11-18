import json,threading
from copy import deepcopy
import pytest
from healthcare_quality.test_design import compile_plan,plan_from_case,retrieve,evaluate_answer,expectation_prompt,DesignLab
from tests.unit.test_advanced_cases import CASES
pytestmark=[pytest.mark.unit,pytest.mark.regression]

def test_compiler_literal_financial_and_reversal_anchors():
    c=compile_plan(plan_from_case(CASES[0]));assert c['steps'][0]['expect']['payout_cents']==71200;assert c['steps'][-1]['expect']['ledger_cents']==0

def test_retrieval_excludes_expected_answers_and_unrelated_policies():
    p=plan_from_case(CASES[0]);r=retrieve(p);assert len(r['plans'])==1 and len(r['policies'])==1;assert '"expect":' not in json.dumps(r);assert 'BN-006' in [x['id'] for x in r['rules']]

@pytest.mark.parametrize('mutation',[lambda p:p['case']['steps'][0]['data'].update(allowed_cents=1),lambda p:p['case']['steps'][0].update(expect={}),lambda p:p.update(url='https://example.com'),lambda p:p['case']['steps'][0]['data']['lines'][0].update(allowed_cents=True)])
def test_invalid_plan_rejected(mutation):
    p=plan_from_case(CASES[0]);mutation(p)
    with pytest.raises(Exception):compile_plan(p)

def test_changed_scenario_is_not_first_attempt_success():
    p=plan_from_case(CASES[0]);other=deepcopy(CASES[1]);assert not evaluate_answer(p,{'text':json.dumps({'cases':[other]})})['eligible']

class Provider:
    def __init__(self,responses):self.responses=iter(responses);self.calls=0
    def generate(self,*args):self.calls+=1;return {'text':json.dumps(next(self.responses))}

@pytest.mark.parametrize('mode,calls',[('calculator_expectations',1),('ai_expectations',2)])
def test_generation_discloses_expectation_author_and_never_approves(tmp_path,mode,calls):
    p=plan_from_case(CASES[0]);provider=Provider([p,{'cases':[compile_plan(p)]}]);lab=DesignLab(tmp_path/'design.sqlite',provider,threading.BoundedSemaphore(1));r=lab.generate('Check paid claim reversal thoroughly',mode,'qwen2.5-coder:3b');assert r['state']=='proposed' and r['assessment']['eligible'] and r['approval'] is None;assert provider.calls==calls and not r['reference_assisted_correction']

def test_raw_wrong_expectations_are_not_replaced(tmp_path):
    p=plan_from_case(CASES[0]);c=compile_plan(p);c['steps'][0]['expect']['payout_cents']+=1;provider=Provider([p,{'cases':[c]}]);lab=DesignLab(tmp_path/'d.sqlite',provider,threading.BoundedSemaphore(1));r=lab.generate('Check raw money and history assertions','ai_expectations','qwen2.5-coder:3b');assert not r['assessment']['eligible'];assert r['cases'][0]['steps'][0]['expect']['payout_cents']==71201

def test_provider_failure_preserves_completed_plan(tmp_path):
    p=plan_from_case(CASES[0]);lab=DesignLab(tmp_path/'d.sqlite',Provider([p]),threading.BoundedSemaphore(1));r=lab.generate('Check lifecycle state and financial assertions','ai_expectations','qwen2.5-coder:3b');assert r['state']=='failed' and r['plan']==p and r['planning_raw'] and r['approval'] is None

def test_prompt_versions_do_not_expose_reference_answer():
    p=plan_from_case(CASES[0]);assert '71200' not in expectation_prompt(p);assert expectation_prompt(p,'baseline-v67')!=expectation_prompt(p)
