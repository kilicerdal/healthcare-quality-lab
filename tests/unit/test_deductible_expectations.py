from copy import deepcopy
import json,threading
from pathlib import Path
import pytest
from jsonschema import ValidationError
from healthcare_quality import deductible_expectations as p,lean_expectations as old
from healthcare_quality.deductible_evaluator import evaluate,worksheets
from tests.support.v86_model_fixtures import wire,Provider
from tests.unit.test_compact_expectations import BASE
pytestmark=[pytest.mark.unit,pytest.mark.regression]

@pytest.mark.parametrize('task',old.cohort()['tasks'],ids=lambda t:t['id'])
def test_historical_complete_wire_checks_both_old_and_new_fields(task):
 raw=wire(task['plan']);before=deepcopy(raw);answer=p.parse(json.dumps(raw));r=evaluate(task['plan'],answer);assert r['eligible'] and raw==before
 for obs,expanded in zip(raw['observations'],answer['observations']):assert expanded['calculation']==next(q['calculation'] for q in raw['quotes'] if q['quote_id']==obs['quote_id'])

@pytest.mark.parametrize('field,value',[('individual_deductible_remaining_cents',1),('family_deductible_remaining_cents',1),('coverage_decision','rejected')])
def test_wrong_extra_fields_cannot_hide_behind_correct_api_values(field,value):
 plan=old.cohort()['tasks'][0]['plan'];raw=wire(plan);raw['quotes'][0]['calculation'][0][field]=value;answer=p.parse(json.dumps(raw));before=deepcopy(answer);r=evaluate(plan,answer);assert not r['eligible'] and r['observations_correct'] and not r['calculations_correct'] and answer==before

def test_missing_fields_are_not_filled_and_unused_aux_difference_is_not_discarded():
 raw=wire(old.cohort()['tasks'][0]['plan']);del raw['quotes'][0]['calculation'][0]['coverage_decision']
 with pytest.raises(ValidationError):p.parse(json.dumps(raw))
 raw=wire(old.cohort()['tasks'][0]['plan']);q=deepcopy(raw['quotes'][0]);q['quote_id']='Q99';q['calculation'][0]['individual_deductible_remaining_cents']+=1;raw['quotes'].append(q)
 with pytest.raises(ValueError):p.parse(json.dumps(raw))

def test_policy_aliases_copy_facts_without_computing_answers(monkeypatch):
 from healthcare_quality.advanced_reference import Oracle
 from healthcare_quality import benefits,benefit_reference
 def no(*a,**kw):raise AssertionError('reference leaked into generation')
 monkeypatch.setattr(Oracle,'step',no);monkeypatch.setattr(benefits,'calculate',no);monkeypatch.setattr(benefit_reference,'price',no)
 plan=old.cohort()['tasks'][0]['plan'];before=json.loads(old.prompt(plan));after=json.loads(p.prompt(plan));assert after['inputs']==before['inputs']
 for a,b in zip(before['facts']['policies'],after['facts']['policies']):assert {p.POLICY_NAMES.get(k,k):v for k,v in a.items()}==b
 schema=p.pricing_schema(after);text=p.pricing_prompt(after);assert 'nominal_deductible_cents = min(' in text and 'policy.individual_deductible_limit_cents - individual_deductible_used' in text and schema['properties']['quotes']['maxItems']==1

def test_sequential_rejected_line_uses_updated_remaining_deductibles():
 plan=next(t['plan'] for t in old.cohort()['tasks'] if t['id']=='H85-03');expected=worksheets(plan)[0];assert expected[0]['coverage_decision']=='covered' and expected[1]['coverage_decision']=='rejected';assert expected[1]['individual_deductible_remaining_cents']<expected[0]['individual_deductible_remaining_cents']

def test_old_failed_answers_do_not_become_passes_from_new_fields():
 root=Path(__file__).resolve().parents[2]
 for id in ('H85-02','H85-03'):
  r=json.loads((root/f'artifacts/v8.5/assessment/{id}.json').read_text());answer=deepcopy(r['rows'][0]['first']['answer']);plan=next(t['plan'] for t in old.cohort()['tasks'] if t['id']==id);extras=worksheets(plan)[0]
  for obs in answer['observations']:
   for line,extra in zip(obs['calculation'],extras):line.update(extra)
  before=deepcopy(answer);assert not evaluate(plan,answer)['eligible'] and answer==before

def test_two_stages_freeze_without_numeric_repair(tmp_path):
 provider=Provider();calls=[]
 def gate(*args):calls.append(len(provider.prompts));return evaluate(*args)
 lab=p.LeanLab(tmp_path/'s.sqlite',provider,threading.Lock(),protocol=p,evaluator=gate);r=lab.start(BASE,max_seconds=15);assert r['state']=='completed' and r['summary'][0]['eligible']==1 and calls==[2];assert 'own_unverified_quotes' in provider.prompts[1]

def test_only_new_variants_are_reserved_and_no_expected_values_are_inputs():
 fresh=[t for t in p.cohort()['tasks'] if t['split']=='reserved_until_exposed'];assert [t['id'] for t in fresh]==['H86-01','H86-02'];assert all('expect' not in s for t in fresh for s in t['plan']['case']['steps'])

@pytest.mark.parametrize('action',['adjust','resolve'])
def test_repricing_credits_only_original_allocation_before_new_deductible(action):
 plan=deepcopy(old.cohort()['tasks'][0]['plan']);steps=plan['case']['steps'];claim=steps[0]['data']['claim_id'];lines=deepcopy(steps[0]['data']['lines']);lines[0]['allowed_cents']=81237
 if action=='resolve':steps[1]=dict(action='appeal',actor='customer-m100',data=dict(claim_id=claim,operation_key='unit-appeal',expected_revision=1,note='Unit appeal fixture'))
 steps.insert(2,dict(action=action,actor='adjuster-demo',data=dict(claim_id=claim,operation_key='unit-'+action,expected_revision=2,lines=lines,note='Unit repricing fixture')))
 expected=worksheets(plan);assert expected[2][0]['individual_deductible_remaining_cents']==expected[0][0]['individual_deductible_remaining_cents'] and expected[2][0]['family_deductible_remaining_cents']==expected[0][0]['family_deductible_remaining_cents'];assert evaluate(plan,p.parse(json.dumps(wire(plan))))['eligible']
