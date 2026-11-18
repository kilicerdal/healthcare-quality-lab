from copy import deepcopy
import json,threading
import pytest
pytestmark=[pytest.mark.unit,pytest.mark.regression]
from healthcare_quality.advanced_evaluation import cohort,assessment,measure
from healthcare_quality.advanced_lab import AdvancedLab,check
from healthcare_quality.ai_studio import StudioError
from tests.unit.test_advanced_cases import CASES


def test_frozen_protocol_rejects_wrong_missing_tampered_and_duplicate_cases():
    task=cohort()['tasks'][0];case=deepcopy(task['case'])
    def assess(cases):return assessment(task,dict(text=json.dumps(dict(cases=cases))))
    assert assess([case])['eligible']
    wrong=deepcopy(case);wrong['steps'][0]['expect']['payout_cents']+=1
    assert not assess([wrong])['eligible']
    missing=deepcopy(case);del missing['steps'][0]['expect']['ledger_count']
    assert not assess([missing])['valid']
    different=deepcopy(CASES[4]);assert not assess([different])['fixed_inputs']
    duplicate=deepcopy(case);duplicate['id']='AB-COPY'
    assert not assess([case,duplicate])['eligible']
    assert not assessment(task,dict(text='execute shell code'))['eligible']


def test_raw_and_reference_assisted_results_are_separate_and_exposure_persists(tmp_path):
    task=cohort()['tasks'][0];good=deepcopy(task['case']);bad=deepcopy(good);bad['steps'][0]['expect']['payout_cents']+=1
    class Provider:
        def __init__(self):self.calls=0
        def generate(self,*args):
            self.calls+=1;return dict(text=json.dumps({'cases':[bad if self.calls%2 else good]}),input_tokens=10,output_tokens=20)
    provider=Provider();state=tmp_path/'exposure.sqlite'
    r=measure(provider,'qwen3.5:27b',['ADV-01'],1,state,tmp_path/'one.json',True)
    assert r['state']=='completed' and provider.calls==2
    s=r['summary']['qwen3.5:27b'];assert s['raw_eligible']==0 and s['assisted_eligible']==1 and s['correction_requests']==1
    assert r['protocol']['approval']=='unapproved' and not r['protocol']['application_execution']
    r2=measure(provider,'qwen3.5:27b',['ADV-01'],1,state,tmp_path/'two.json')
    assert r2['previously_exposed_tasks']==['ADV-01'] and not r2['first_recorded_in_this_ledger']
    with pytest.raises(ValueError):measure(provider,'qwen3.5:27b',['ADV-01'],1,state,tmp_path/'two.json')


def test_ai_correction_is_new_unapproved_and_preserves_original(tmp_path):
    good=deepcopy(CASES[0]);wrong=deepcopy(good);wrong['steps'][0]['expect']['payout_cents']+=1
    class Provider:
        def generate(self,*args):return dict(text=json.dumps({'cases':[good]}))
    lab=AdvancedLab(tmp_path/'lab.sqlite',Provider(),threading.BoundedSemaphore(1));original=lab.propose([wrong])
    corrected=lab.correct(original['id'],'qwen3.5:27b')
    assert corrected['assessment']['review_ready'] and corrected['approval'] is None
    assert corrected['provenance']['reference_assisted']
    assert lab.get(original['id'])['cases']==[wrong]
    with pytest.raises(StudioError):lab.correct(corrected['id'],'qwen3.5:27b')
    with pytest.raises(StudioError):lab.execute(corrected['id'],'http')


def test_correction_cannot_substitute_an_easier_scenario(tmp_path):
    class Provider:
        def generate(self,*args):return dict(text=json.dumps({'cases':[CASES[4]]}))
    lab=AdvancedLab(tmp_path/'lab.sqlite',Provider(),threading.BoundedSemaphore(1));original=lab.propose(CASES[:1]);r=lab.correct(original['id'],'qwen3.5:27b')
    assert not r['assessment']['review_ready']
    with pytest.raises(StudioError):lab.review(r['id'],'engineer','Cannot change the requested scenario',1)


def test_scoring_requires_review_and_passing_reference_control(tmp_path):
    lab=AdvancedLab(tmp_path/'lab.sqlite',None,threading.BoundedSemaphore(1));r=lab.propose(CASES[:1])
    with pytest.raises(StudioError):lab.score(r['id'])
    lab.review(r['id'],'engineer','Inspected independently calculated full assertion set',1)
    score=lab.score(r['id']);assert score['detected']==score['total']==12
    assert 'observable-contract' in score['scope']


def test_expired_evaluation_recovery_retains_exposure_and_partial_rows(tmp_path):
    from healthcare_quality.advanced_evaluation import recover
    from healthcare_quality.ai_studio import ExperimentStore
    store=ExperimentStore(tmp_path/'evaluation.sqlite')
    r=dict(id='expired-evaluation',kind='advanced_evaluation',created_at='2026-11-18',state='running',rows=[{'task_id':'ADV-03','error':{'type':'interrupted'}}],protocol={'task_ids':['ADV-03']})
    store.create(r);recover(store);saved=store.get(r['id'])
    assert saved['state']=='interrupted' and saved['rows']==r['rows'] and saved['protocol']==r['protocol']


def test_raw_provider_failure_is_not_a_wrong_model_answer(tmp_path):
    class Provider:
        def generate(self,*args):raise TimeoutError('offline test double')
    r=measure(Provider(),'qwen3.5:27b',['ADV-03'],1,tmp_path/'state.sqlite',tmp_path/'measurement.json',True)
    s=r['summary']['qwen3.5:27b']
    assert s['provider_errors']==1 and s['raw_eligible']==0 and s['wrong_or_incomplete']==0 and s['correction_requests']==0


def test_duplicate_json_keys_and_float_money_are_rejected():
    task=cohort()['tasks'][0]
    assert not assessment(task,dict(text='{"cases":[],"cases":[]}'))['eligible']
    c=deepcopy(CASES[7]);c['steps'][0]['data']['lines'][0]['allowed_cents']=5000.0
    assert not check([c])['review_ready']


def test_interruption_during_correction_retains_completed_raw_response(tmp_path):
    from healthcare_quality.ai_studio import ExperimentStore
    from healthcare_quality.advanced_evaluation import recover
    task=cohort()['tasks'][0];bad=deepcopy(task['case']);bad['steps'][0]['expect']['payout_cents']+=1
    class Provider:
        calls=0
        def generate(self,*args):
            self.calls+=1
            if self.calls==2:raise KeyboardInterrupt('Injected worker interruption during correction')
            return dict(text=json.dumps({'cases':[bad]}),input_tokens=10,output_tokens=20)
    state=tmp_path/'evaluation.sqlite'
    with pytest.raises(KeyboardInterrupt):measure(Provider(),'qwen3.5:27b',['ADV-01'],1,state,tmp_path/'partial.json',True)
    store=ExperimentStore(state)
    with store.transaction() as db:
        db.execute('UPDATE studio_operations SET expires_at=0')
        id=db.execute('SELECT id FROM ai_experiments').fetchone()[0]
    recover(store);r=store.get(id)
    assert r['state']=='interrupted' and len(r['rows'])==1
    assert r['rows'][0]['raw']['text']==json.dumps({'cases':[bad]})
    assert r['rows'][0]['correction_requested'] and r['rows'][0]['phase']=='interrupted'
    assert not r['rows'][0]['raw_assessment']['eligible']


def test_interrupted_raw_attempt_is_counted_without_inventing_an_answer(tmp_path):
    from healthcare_quality.ai_studio import ExperimentStore
    from healthcare_quality.advanced_evaluation import recover
    class Provider:
        def generate(self,*args):raise KeyboardInterrupt('Injected interruption before response')
    state=tmp_path/'evaluation.sqlite'
    with pytest.raises(KeyboardInterrupt):measure(Provider(),'qwen3.5:27b',['ADV-03'],1,state,tmp_path/'partial.json')
    store=ExperimentStore(state)
    with store.transaction() as db:
        db.execute('UPDATE studio_operations SET expires_at=0');id=db.execute('SELECT id FROM ai_experiments').fetchone()[0]
    recover(store);r=store.get(id);s=r['summary']['qwen3.5:27b']
    assert r['state']=='interrupted' and s['requested']==1 and s['raw_completed']==0
    assert s['unknown_outcomes']==1 and s['provider_errors']==s['raw_eligible']==0
