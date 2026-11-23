from copy import deepcopy
import json,threading
import pytest
from jsonschema import ValidationError
from healthcare_quality import compact_expectations as protocol
from healthcare_quality.compact_evaluator import evaluate
from healthcare_quality.expectation_lab import ExpectationLab,selection,aggregate
from healthcare_quality.advanced_reference import Oracle
from healthcare_quality.ai_schema import digest
pytestmark=[pytest.mark.unit,pytest.mark.regression]
BASE=dict(models=['qwen2.5-coder:3b'],tasks=['D82-01'],repeats=1,strategy='whole_case',self_review=False)
def wire(plan):
 from healthcare_quality.compact_evaluator import worksheets,ledger_states
 pricing=worksheets(plan);ledger=ledger_states(plan);oracle=Oracle();quotes=[];observations=[];seen={}
 for i,step in enumerate(plan['case']['steps'],1):
  value=oracle.step(step);q={k:value[k] for k in protocol.QUOTE_KEYS};key=digest(q)
  if key not in seen:seen[key]=f'Q{len(quotes)+1:02}';quotes.append(dict(quote_id=seen[key],calculation=pricing[i-1],values=q))
  observations.append(dict(step_id=f'S{i:02}',quote_id=seen[key],ledger_calculation=ledger[i-1],**{k:value[k] for k in protocol.STATE_KEYS}))
 return dict(quotes=quotes,observations=observations)
class Provider:
 settings={'fixture':'offline-not-AI'};profile='offline-compact-fixture'
 def __init__(self,answers=None):self.answers=answers or [];self.prompts=[]
 def status(self):return {'models':[{'name':'qwen2.5-coder:3b','digest':'offline'}]}
 def generate(self,model,prompt,schema):
  self.prompts.append(prompt);answer=self.answers.pop(0) if self.answers else wire(protocol.cohort()['tasks'][0]['plan'])
  if set(schema.get('properties',{}))=={'quotes'}:answer={'quotes':answer['quotes']}
  if set(schema.get('properties',{}))=={'observations'} and 'quotes' in answer:answer={'observations':answer['observations']}
  return dict(text=json.dumps(answer),latency_ms=1,input_tokens=1,output_tokens=1)
def lab(path,provider=None,evaluator=evaluate):return ExpectationLab(path,provider or Provider(),threading.Lock(),protocol=protocol,evaluator=evaluator)
@pytest.mark.parametrize('task',protocol.cohort()['tasks'],ids=lambda t:t['id'])
def test_all_inputs_roundtrip_without_modifying_model_observations(task):
 raw=wire(task['plan']);before=deepcopy(raw);answer=protocol.parse(json.dumps(raw));result=evaluate(task['plan'],answer);assert result['eligible'] and raw==before
 assert len(raw['quotes'])<=len(raw['observations']);assert result['calculations_correct']
 for o,step in zip(answer['observations'],result['cases'][0]['steps']):assert step['expect']==o['expect']

def test_literal_cap_values_and_exact_alias_copy():
 task=protocol.cohort()['tasks'][0];raw=wire(task['plan']);q=raw['quotes'][0]['values'];assert q['payout_cents']==78513 and q['member_cents']==30000
 assert raw['quotes'][0]['calculation'][0]['individual_oop_remaining_cents']==30000 and raw['quotes'][0]['calculation'][0]['capped_member_cents']==30000
 assert len(raw['quotes'])==1
 raw['quotes'][0]['values']['payout_cents']=12345;answer=protocol.parse(json.dumps(raw));assert all(o['expect']['payout_cents']==12345 for o in answer['observations']);assert not evaluate(task['plan'],answer)['eligible']

@pytest.mark.parametrize('change',['bool_money','missing_field','extra_field','missing_quote','unused_quote','duplicate_quote'])
def test_compact_wire_rejects_ambiguous_or_invalid_model_values(change):
 raw=wire(protocol.cohort()['tasks'][0]['plan'])
 if change=='bool_money':raw['quotes'][0]['values']['payout_cents']=True
 if change=='missing_field':del raw['observations'][0]['revision']
 if change=='extra_field':raw['observations'][0]['calculator_answer']=1
 if change=='missing_quote':raw['observations'][0]['quote_id']='Q99'
 if change=='unused_quote':raw['quotes'].append({**deepcopy(raw['quotes'][0]),'quote_id':'Q99'})
 if change=='duplicate_quote':raw['quotes'].append(deepcopy(raw['quotes'][0]))
 with pytest.raises((ValueError,ValidationError)):protocol.parse(json.dumps(raw))

@pytest.mark.parametrize('change',['duplicate','reverse','omit','input'])
def test_immutable_step_assembly_rejects_bad_identity(change):
 plan=protocol.cohort()['tasks'][0]['plan'];a=protocol.parse(json.dumps(wire(plan)))
 if change=='duplicate':a['observations'][1]['step_id']='S01'
 if change=='reverse':a['observations'].reverse()
 if change=='omit':a['observations'].pop()
 if change=='input':a['observations'][0]['data']={'amount':1}
 assert not evaluate(plan,a)['eligible']

def test_prompt_never_invokes_calculators_or_oracle(monkeypatch):
 from healthcare_quality import benefits,benefit_reference,advanced_reference,test_design
 def blocked(*a,**kw):raise AssertionError('Answer leakage')
 monkeypatch.setattr(benefits,'calculate',blocked);monkeypatch.setattr(benefit_reference,'price',blocked);monkeypatch.setattr(advanced_reference.Oracle,'step',blocked);monkeypatch.setattr(test_design,'compile_plan',blocked)
 plan=protocol.cohort()['tasks'][0]['plan'];text=protocol.prompt(plan);assert 'CAP CHECK REQUIRED' in text and 'ONLY if' in text;assert '78513' not in text

def test_stepwise_only_sees_own_predictions_and_scores_after_all_responses(tmp_path):
 plan=protocol.cohort()['tasks'][0]['plan'];all=wire(plan);responses=[]
 for obs in all['observations']:responses.append(dict(quotes=[q for q in all['quotes'] if q['quote_id']==obs['quote_id']],observations=[obs]))
 p=Provider(responses);counts=[]
 def checked(*a):counts.append(len(p.prompts));return evaluate(*a)
 r=lab(tmp_path/'e.sqlite',p,checked).start({**BASE,'strategy':'stepwise'});assert r['state']=='completed' and r['summary'][0]['eligible']==1 and counts==[3];assert 'YOUR OWN unverified predictions' in p.prompts[1]

def test_blind_review_is_optional_and_has_no_reference_feedback(tmp_path):
 p=Provider();counts=[]
 def checked(*args):counts.append(len(p.prompts));return evaluate(*args)
 r=lab(tmp_path/'e.sqlite',p,checked).start({**BASE,'self_review':True});assert counts==[2,2];assert len(p.prompts)==2 and r['kind']=='model_expectations_v82';assert r['summary'][0]['eligible']==1

def test_timeout_is_classified_without_retry_and_kept_in_denominator(tmp_path):
 class Broken(Provider):
  def generate(self,*a):self.prompts.append('attempt');raise TimeoutError('bounded timeout')
 p=Broken();r=lab(tmp_path/'e.sqlite',p).start(BASE);g=r['summary'][0];assert g['timeout_requests']==1 and g['trials']==1 and g['not_assessed']==1 and g['eligible']==0;assert len(p.prompts)==1 and g['elapsed_max_ms'] is not None

def test_request_budget_exposure_and_protocols_remain_separate(tmp_path):
 assert selection({**BASE,'strategy':'stepwise','repeats':2},protocol.cohort())['request_budget']==6
 l=lab(tmp_path/'e.sqlite');a=l.start(BASE);b=l.start(BASE);assert b['previously_exposed_tasks']==['D82-01']
 a['rows'][0]['split']='reserved_until_exposed'
 with pytest.raises(ValueError):aggregate([a,a])
 assert not a['approval']

def test_compact_profile_does_not_change_v81_settings():
 from healthcare_quality.ollama_provider import CompactExpectationProvider,ExpectationOllamaProvider
 old=ExpectationOllamaProvider();new=CompactExpectationProvider();assert old.timeout==240 and old.settings['num_predict']==6000;assert new.timeout==240 and new.settings['num_predict']==2600

def test_six_survivors_have_reproducible_authored_witnesses():
 from tools.fault_audit_v82 import audit
 r=audit();assert r['investigated']==r['closed']==6;assert r['authored_effectiveness']['suites'][0]['detected']==27;assert all(f['minimal_prefix']['reduced_steps']<=f['minimal_prefix']['original_steps'] for f in r['faults']);assert 'not AI' in r['origin']


def test_correct_observations_with_wrong_pricing_worksheet_remain_blocked():
 plan=protocol.cohort()['tasks'][0]['plan'];raw=wire(plan);raw['quotes'][0]['calculation'][0]['payer_after_oop_cents']+=1;result=evaluate(plan,protocol.parse(json.dumps(raw)));assert result['observations_correct'] and not result['calculations_correct'] and not result['eligible']


@pytest.mark.parametrize('invalid',[False,0.0])
def test_saved_worksheet_cannot_pass_using_boolean_or_float_equality(invalid):
 plan=protocol.cohort()['tasks'][0]['plan'];answer=protocol.parse(json.dumps(wire(plan)));answer['observations'][0]['calculation'][0]['noncovered_cents']=invalid;r=evaluate(plan,answer);assert r['observations_correct'] and not r['eligible']


def test_correct_observations_do_not_hide_wrong_stored_ledger():
 plan=protocol.cohort()['tasks'][0]['plan'];raw=wire(plan);raw['observations'][0]['ledger_calculation']['ledger_after_cents']=78513;result=evaluate(plan,protocol.parse(json.dumps(raw)));assert result['observations_correct'] and not result['eligible']
