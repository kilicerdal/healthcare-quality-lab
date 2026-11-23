import json,threading
from copy import deepcopy
import pytest
from jsonschema import Draft202012Validator,ValidationError
from healthcare_quality import lean_expectations as p,staged_expectations as old
from healthcare_quality.compact_evaluator import evaluate
from tests.unit.test_compact_expectations import Provider,BASE,wire
pytestmark=[pytest.mark.unit,pytest.mark.regression]

def spec(plan,step=None):return json.loads(p.prompt(plan,step=step))

@pytest.mark.parametrize('task',old.cohort()['tasks'],ids=lambda t:t['id'])
def test_historical_fixture_shapes_fit_safe_bounds(task):
 plan=task['plan'];w=wire(plan);s=spec(plan);ps=p.pricing_schema(s);Draft202012Validator(ps).validate({'quotes':w['quotes']});ls=p.lifecycle_schema(p.answer_schema(plan),{'quotes':w['quotes']});Draft202012Validator(ls).validate({'observations':w['observations']});assert evaluate(plan,p.parse(json.dumps(w)))['eligible']

def test_single_claim_bound_and_multi_claim_family_snapshot_safety():
 assert p.quote_limit(spec(old.cohort()['tasks'][0]['plan']))==1
 plan=deepcopy(next(t['plan'] for t in old.cohort()['tasks'] if t['id']=='H82-06'));assert p.quote_limit(spec(plan))==len(plan['case']['steps'])
 plan=deepcopy(old.cohort()['tasks'][0]['plan']);plan['case']['steps'].insert(2,dict(action='reverse',actor='finance-demo',data=dict(claim_id=plan['case']['steps'][0]['data']['claim_id'],operation_key='unit-reverse',expected_revision=2)));assert p.quote_limit(spec(plan))==4
 assert p.quote_limit(spec(plan,'S04'))==1

def test_lifecycle_gets_only_own_quotes_and_action_metadata():
 plan=old.cohort()['tasks'][0]['plan'];s=spec(plan);q={'quotes':wire(plan)['quotes']};text=p.lifecycle_prompt(s,q);assert 'policies' not in text and 'payer_bps' not in text and 'allowed_cents' not in text
 assert 'own_unverified_quotes' in text and 'Q01' in text
 schema=p.lifecycle_schema(p.answer_schema(plan),q);bad={'observations':deepcopy(wire(plan)['observations'])};bad['observations'][0]['quote_id']='Q99'
 with pytest.raises(ValidationError):Draft202012Validator(schema).validate(bad)

def test_two_calls_frozen_before_gate_and_no_numeric_repair(tmp_path):
 plan=p.cohort()['tasks'][0]['plan'];w=wire(plan);w['quotes'][0]['values']['payout_cents']=123;provider=Provider([{'quotes':w['quotes']},{'observations':w['observations']}]);counts=[]
 def gate(*args):counts.append(len(provider.prompts));return evaluate(*args)
 lab=p.LeanLab(tmp_path/'s.sqlite',provider,threading.Lock(),protocol=p,evaluator=gate);r=lab.start(BASE,max_seconds=15)
 assert counts==[2] and r['rows'][0]['first']['answer']['observations'][0]['expect']['payout_cents']==123 and not r['rows'][0]['first']['assessment']['eligible']
 assert [c['generation']['phase'] for c in r['rows'][0]['calls']]==['pricing','lifecycle']

def test_extra_quote_stops_before_lifecycle_without_fallback(tmp_path):
 w=wire(p.cohort()['tasks'][0]['plan']);q=deepcopy(w['quotes'][0]);q['quote_id']='Q02';w['quotes'].append(q);provider=Provider([{'quotes':w['quotes']}]);lab=p.LeanLab(tmp_path/'s.sqlite',provider,threading.Lock(),protocol=p,evaluator=evaluate);r=lab.start(BASE)
 assert r['state']=='completed' and len(provider.prompts)==1 and r['rows'][0]['first']['error']

def test_phase_metadata_is_durable_before_timeout(tmp_path):
 entered=threading.Event();done=threading.Event()
 class Slow(Provider):
  def generate(self,*args):entered.set();done.wait(5);return super().generate(*args)
 lab=p.LeanLab(tmp_path/'s.sqlite',Slow(),threading.Lock(),protocol=p,evaluator=evaluate)
 try:
  r=lab.start(BASE,max_seconds=1);assert entered.is_set() and r['state']=='interrupted';assert r['rows'][0]['calls'][0]['generation']==dict(phase='pricing',shape=dict(quote_limit=1,line_limit=1,observations=3))
 finally:done.set()

def test_prompt_construction_has_no_oracle_access(monkeypatch):
 from healthcare_quality.advanced_reference import Oracle
 from healthcare_quality import benefit_reference,benefits
 def forbidden(*a,**k):raise AssertionError('answer leakage')
 monkeypatch.setattr(Oracle,'step',forbidden);monkeypatch.setattr(benefit_reference,'price',forbidden);monkeypatch.setattr(benefits,'calculate',forbidden)
 plan=old.cohort()['tasks'][0]['plan'];s=spec(plan);assert p.pricing_prompt(s) and p.quote_limit(s)==1

def test_fresh_inputs_are_not_old_qualification_or_reference_answers():
 c=p.cohort();fresh=[t for t in c['tasks'] if t['split']=='reserved_until_exposed'];assert [t['id'] for t in fresh]==['H85-01','H85-02','H85-03'];assert len(c['tasks'])==21
 assert all('expect' not in s for t in fresh for s in t['plan']['case']['steps'])

def test_only_governing_plan_facts_and_flag_defaults_reach_pricing():
 s=spec(old.cohort()['tasks'][0]['plan']);assert all(set(plan)=={'id','services','network_required','authorization_services'} for plan in s['facts']['plans']);assert 'default TRUE' in p.PRICING_RULES and s['facts']['policies'][0]['individual_deductible']>=0
