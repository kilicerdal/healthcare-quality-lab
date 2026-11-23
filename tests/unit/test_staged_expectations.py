import json,threading
from copy import deepcopy
from pathlib import Path
import pytest
from healthcare_quality import staged_expectations as p
from healthcare_quality.compact_evaluator import evaluate
from healthcare_quality.expectation_lab import selection
from tests.unit.test_compact_expectations import Provider,BASE,wire
pytestmark=[pytest.mark.unit,pytest.mark.regression]

def test_stages_freeze_raw_quotes_before_lifecycle_and_only_then_score(tmp_path):
 plan=p.cohort()['tasks'][0]['plan'];w=wire(plan);provider=Provider([{'quotes':w['quotes']},{'observations':w['observations']}]);count=[]
 def gate(*a):count.append(len(provider.prompts));return evaluate(*a)
 lab=p.StagedLab(tmp_path/'s.sqlite',provider,threading.Lock(),protocol=p,evaluator=gate);r=lab.start(BASE,max_seconds=15)
 assert r['state']=='completed' and r['summary'][0]['eligible']==1 and count==[2]
 assert [c['generation_phase'] for c in r['rows'][0]['calls']]==['pricing','lifecycle']
 assert 'YOUR OWN UNVERIFIED PRICING' in provider.prompts[1]
 assert r['protocol']['selection']['request_budget']==2
 assert all(o['expect']['payout_cents']==w['quotes'][0]['values']['payout_cents'] for o in r['rows'][0]['first']['answer']['observations'])

def test_wrong_model_values_not_repaired(tmp_path):
 w=wire(p.cohort()['tasks'][0]['plan']);w['quotes'][0]['values']['payout_cents']=123
 lab=p.StagedLab(tmp_path/'s.sqlite',Provider([{'quotes':w['quotes']},{'observations':w['observations']}]),threading.Lock(),protocol=p,evaluator=evaluate);r=lab.start(BASE)
 assert not r['rows'][0]['first']['assessment']['eligible'];assert r['rows'][0]['first']['answer']['observations'][0]['expect']['payout_cents']==123

def test_malformed_pricing_stops_that_trial_without_hidden_retry(tmp_path):
 lab=p.StagedLab(tmp_path/'s.sqlite',Provider([{'quotes':[]}]),threading.Lock(),protocol=p,evaluator=evaluate);r=lab.start(BASE)
 assert r['state']=='completed' and len(r['rows'][0]['calls'])==1 and r['summary'][0]['eligible']==0

def test_split_request_accounting_and_fresh_inputs():
 assert selection({**BASE,'tasks':['D83-01','H84-01','H84-02']},p.cohort())['request_budget']==6
 assert selection({**BASE,'self_review':True},p.cohort())['request_budget']==4
 for t in p.cohort()['tasks']:
  assert all('expect' not in s for s in t['plan']['case']['steps'])

def test_prompts_do_not_consult_oracle(monkeypatch):
 from healthcare_quality.advanced_reference import Oracle
 def forbidden(*a):raise AssertionError('reference leakage')
 monkeypatch.setattr(Oracle,'step',forbidden)
 assert '27137' in p.prompt(next(t['plan'] for t in p.cohort()['tasks'] if t['id']=='H84-01'))

def test_original_failed_pilot_still_fails():
 r=json.loads((Path(__file__).resolve().parents[2]/'artifacts/v8.3/live-pilot.json').read_text());t=next(t for t in p.cohort()['tasks'] if t['id']=='D83-01');raw=deepcopy(r['rows'][0]['first']['answer']);assert not evaluate(t['plan'],raw)['eligible'];assert raw==r['rows'][0]['first']['answer']

def test_budget_between_stages_fences_late_lifecycle(tmp_path):
 import time
 done=threading.Event();entered=threading.Event();w=wire(p.cohort()['tasks'][0]['plan'])
 class Slow(Provider):
  def generate(self,model,prompt,schema):
   if set(schema['properties'])=={'observations'}:entered.set();done.wait(5)
   return super().generate(model,prompt,schema)
 provider=Slow([{'quotes':w['quotes']},{'observations':w['observations']}]);lock=threading.Lock();lab=p.StagedLab(tmp_path/'s.sqlite',provider,lock,protocol=p,evaluator=evaluate)
 try:
  r=lab.start(BASE,max_seconds=1);assert entered.is_set() and r['state']=='interrupted' and len(r['rows'][0]['calls'])==2
  assert r['rows'][0]['calls'][0]['generation_phase']=='pricing' and r['rows'][0]['calls'][1]['phase']=='interrupted'
  assert 'assessment' not in r['rows'][0].get('first',{}) and lock.locked()
 finally:done.set()
 deadline=time.monotonic()+2
 while lock.locked() and time.monotonic()<deadline:time.sleep(.01)
 assert not lock.locked() and lab.get(r['id'])['state']=='interrupted'

@pytest.mark.parametrize('bad_phase',['pricing','lifecycle'])
def test_full_wire_cannot_bypass_invalid_stage_contract(tmp_path,bad_phase):
 w=wire(p.cohort()['tasks'][0]['plan'])
 # A complete correct legacy answer is invalid for either isolated stage.
 answers=[w] if bad_phase=='pricing' else [{'quotes':w['quotes']},w]
 class Raw(Provider):
  def generate(self,*args):return dict(text=json.dumps(answers.pop(0)),latency_ms=1)
 lab=p.StagedLab(tmp_path/'s.sqlite',Raw(),threading.Lock(),protocol=p,evaluator=evaluate);r=lab.start(BASE)
 assert r['state']=='completed' and r['summary'][0]['eligible']==0 and r['rows'][0]['first']['error']

def test_rejected_branch_names_survive_stage_separation():
 assert 'member_before_oop_cents' in p.PRICING_RULES and 'capped_member_cents' in p.PRICING_RULES and 'ALL ZERO' in p.PRICING_RULES

def test_unused_exact_aliases_are_representation_only():
 w=wire(p.cohort()['tasks'][0]['plan']);original=p.parse(json.dumps(w));q=deepcopy(w['quotes'][0]);q['quote_id']='Q99';w['quotes'].append(q);before=deepcopy(w)
 canonical,audit=p.normalize(w);assert audit['discarded_quote_ids']==['Q99'] and audit['expected_fields_changed']==0
 assert p.parse(json.dumps(w))==original and w==before

@pytest.mark.parametrize('change',['money','worksheet','missing_id','duplicate_id'])
def test_alias_normalization_cannot_hide_wrong_or_missing_values(change):
 w=wire(p.cohort()['tasks'][0]['plan']);q=deepcopy(w['quotes'][0]);q['quote_id']='Q99';w['quotes'].append(q)
 if change=='money':q['values']['payout_cents']+=1
 if change=='worksheet':q['calculation'][0]['eligible_cents']+=1
 if change=='missing_id':w['observations'][0]['quote_id']='Q98'
 if change=='duplicate_id':q['quote_id']=w['quotes'][0]['quote_id']
 with pytest.raises(ValueError):p.parse(json.dumps(w))

def test_frozen_resumed_prediction_passes_without_changing_any_expected_value():
 path=Path(__file__).resolve().parents[1]/'fixtures/v84-resumed-wire.json'
 raw=json.loads(path.read_text());before=deepcopy(raw);answer=p.parse(json.dumps(raw));plan=next(t['plan'] for t in p.cohort()['tasks'] if t['id']=='D83-01');assert evaluate(plan,answer)['eligible'] and raw==before
