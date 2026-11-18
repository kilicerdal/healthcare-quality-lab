from copy import deepcopy
import json,threading,time
from pathlib import Path
import pytest
pytestmark=[pytest.mark.unit,pytest.mark.regression]
from healthcare_quality.advanced_schema import validate,semantic_key
from healthcare_quality.advanced_lab import check,AdvancedLab
from healthcare_quality.advanced_runner import run
from healthcare_quality.ai_studio import StudioError

CASES=json.loads((Path(__file__).resolve().parents[2]/'healthcare_quality/data/advanced_cases_v63.json').read_text())['cases']

@pytest.mark.parametrize('case',CASES,ids=lambda c:c['id'])
def test_independent_lifecycle_matches_actual_store(case):
    assert check([case])['review_ready']
    result=run([case]);assert result['passed']==1, result

def test_literals_and_accumulator_restoration():
    case=CASES[0]
    assert [s['expect']['payout_cents'] for s in case['steps']]==[71200,71200,31200,31200,31200]
    assert [s['expect']['ledger_cents'] for s in case['steps']]==[0,71200,31200,0,0]
    assert case['steps'][-1]['expect']['individual_oop']==0
    assert CASES[4]['steps'][0]['expect']['payout_cents']==55200
    assert CASES[2]['steps'][2]['expect']['member_cents']==0
    assert CASES[3]['steps'][2]['expect']['payout_cents']==68000

@pytest.mark.parametrize('field',['payout_cents','ledger_cents','event_count','revision','family_oop','individual_benefit'])
def test_bad_expected_values_are_rejected(field):
    cases=deepcopy(CASES[:1]);cases[0]['steps'][0]['expect'][field]+=1
    assert not check(cases)['review_ready']

def test_schema_incomplete_assertion_and_duplicate_controls():
    c=deepcopy(CASES[0]);del c['steps'][0]['expect']['ledger_cents'];assert not check([c])['valid']
    c=deepcopy(CASES[0]);c['steps'][0]['action']='shell';assert not check([c])['valid']
    c=deepcopy(CASES[0]);c['steps'][0]['expect']['payout_cents']=True;assert not check([c])['valid']
    c=deepcopy(CASES[0]);c['id']='AB-RENAMED'
    for s in c['steps']:
        s['data']['claim_id']='RENAMED'
        if 'operation_key' in s['data']:s['data']['operation_key']='changed-'+s['data']['operation_key']
    assert semantic_key(c)==semantic_key(CASES[0])
    assert not check([CASES[0],c])['review_ready']

def test_rejected_write_requires_state_readback():
    c=deepcopy(CASES[5]);del c['steps'][2];assert not check([c])['review_ready']

def test_explicit_review_and_source_bound_execution(tmp_path,monkeypatch):
    lab=AdvancedLab(tmp_path/'advanced.sqlite',None,threading.BoundedSemaphore(1))
    r=lab.propose(CASES[:1]);assert r['approval'] is None
    with pytest.raises(StudioError):lab.execute(r['id'],'service')
    lab.review(r['id'],'engineer','Inspected money and ledger independently',1)
    assert lab.execute(r['id'],'service')['runs'][-1]['passed']==1
    monkeypatch.setattr('healthcare_quality.advanced_lab.source_hash',lambda:'changed')
    with pytest.raises(StudioError):lab.execute(r['id'],'service')

def test_durable_generation_has_raw_evidence_and_no_approval(tmp_path):
    class Provider:
        def generate(self,*args):return dict(text=json.dumps({'cases':CASES[:1]}),model='offline-double')
    lab=AdvancedLab(tmp_path/'advanced.sqlite',Provider(),threading.BoundedSemaphore(1))
    r=lab.generate(dict(requirement='Test a paid adjustment and reversal',model='qwen3.5:27b'),background=False)
    assert r['state']=='proposed' and r['raw'] and r['assessment']['review_ready']
    assert r['approval'] is None and r['runs']==[]


def test_every_plan_and_all_teaching_services_have_independent_outcomes():
    from healthcare_quality.advanced_reference import Oracle,PLANS
    from healthcare_quality.advanced_schema import SERVICES
    assert set(SERVICES)=={'dental','dme','emergency','hearing','home_health','hospice','hospital','lab','maternity','medical','mental_health','outpatient','prescription','preventive','rehabilitation','skilled_nursing','vision'}
    for plan in PLANS:
        for service in SERVICES:
            c=deepcopy(CASES[0]);c['steps']=c['steps'][:1]
            step=c['steps'][0];step['data'].update(plan_id=plan,lines=[dict(id='LINE-1',service=service,allowed_cents=100000)])
            step['expect']=Oracle().step(step)
            assert check([c])['review_ready']
            result=run([c]);assert result['passed']==1,(plan,service,result)
