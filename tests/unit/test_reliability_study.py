import json,threading
from copy import deepcopy
from pathlib import Path
import pytest
from healthcare_quality import reliability_protocol as p
from healthcare_quality.rule_review import review,VECTORS
from healthcare_quality.deductible_evaluator import evaluate
from healthcare_quality.reliability_scorecard import scorecard
from healthcare_quality.reliability_evidence import authored_cases,seal,read,collect
from tools.reliability_study import prepare,run,summarize
from tests.support.v86_model_fixtures import wire,Provider
pytestmark=[pytest.mark.unit,pytest.mark.regression]

@pytest.mark.parametrize('task',p.cohort()['tasks'],ids=lambda t:t['id'])
def test_new_cohort_roundtrip_preserves_all_values_and_executes(task):
 from healthcare_quality.advanced_runner import run as execute
 raw=wire(task['plan']);answer=p.parse(json.dumps(raw));result=evaluate(task['plan'],answer)
 assert result['eligible'];assert execute(result['cases'])['failed']==0

def test_input_only_sealing_never_calls_reference(monkeypatch):
 from healthcare_quality import benefit_reference,advanced_reference,benefits
 def blocked(*a,**k):raise AssertionError('Reference leaked into generation')
 monkeypatch.setattr(benefit_reference,'price',blocked);monkeypatch.setattr(advanced_reference.Oracle,'step',blocked);monkeypatch.setattr(benefits,'calculate',blocked)
 plan=prepare();assert len(plan['trials'])==14 and plan['max_calls']==28
 assert len({t['task'] for t in plan['trials'] if t['role']=='fresh'})==12
 for t in p.cohort()['tasks']:
  spec=json.loads(p.prompt(t['plan']));assert all('expect' not in step for step in spec['inputs']['steps']);p.pricing_prompt(spec);p.pricing_schema(spec)

def test_fixed_rule_vectors_detect_a_shared_calculator_error(monkeypatch):
 from healthcare_quality import rule_review as r
 assert review()['passed'] and len(VECTORS)==10
 original=r.price
 def wrong(*a,**k):
  value=original(*a,**k);value['payout_cents']+=1;return value
 monkeypatch.setattr(r,'price',wrong);assert not review()['passed']

def record(task,model='qwen3.5:27b'):
 class Local(Provider):
  def status(self):return dict(models=[dict(name=model,digest='fixture')])
 plan=next(t['plan'] for t in p.cohort()['tasks'] if t['id']==task)
 import tempfile
 with tempfile.TemporaryDirectory() as tmp:
  lab=p.LeanLab(Path(tmp)/'s.sqlite',Local([wire(plan),wire(plan)]),threading.Lock(),protocol=p,evaluator=evaluate)
  return lab.start(dict(models=[model],tasks=[task],repeats=1,strategy='whole_case',self_review=False))

def test_v87_scorecard_requires_strict_unchanged_stage_pair():
 r=record('R87-03');assert scorecard(r)['counts']=={'first_pass':1}
 r['rows'][0]['calls'][0]['response']['reused_frozen_model_response']=True
 assert scorecard(r)['counts']=={'nonfirst_pass':1}

class FakeLab:
 def __init__(self,timeout=False):self.calls=0;self.timeout=timeout
 def start(self,selection,**kwargs):
  self.calls+=1;r=record(selection['tasks'][0])
  if self.timeout:
   r['state']='interrupted';r['stop_reason']='time_budget';r['rows'][0]['first']={};r['rows'][0]['calls'][0]['phase']='interrupted'
  return r

def test_all_planned_trials_and_repeats_visible(tmp_path):
 lab=FakeLab();result=run(prepare(),tmp_path/'out',tmp_path/'state',lab)
 assert result['fresh_complete'] and result['fresh_passed']==12 and result['actual_calls']==28
 assert len(result['repeat_pairs'])==2 and all(x['both_passed'] for x in result['repeat_pairs'])
 _,cases,packets,provenance=collect(tmp_path/'out');assert len(cases)==12 and len(packets)==14 and len(provenance)==14
 with pytest.raises(ValueError):run(prepare(),tmp_path/'out',tmp_path/'state',lab)
 raw=tmp_path/'out'/'R87-01-r1.json';raw.write_text(raw.read_text()+' ')
 with pytest.raises(ValueError,match='changed'):collect(tmp_path/'out')

def test_provider_uncertainty_stops_further_calls_and_keeps_denominator(tmp_path):
 lab=FakeLab(timeout=True);r=run(prepare(),tmp_path/'out',tmp_path/'state',lab)
 assert lab.calls==1 and len(r['entries'])==14 and r['fresh_percent'] is None
 assert r['fresh_planned']==12 and r['fresh_assessed']==0
 assert all(x['outcome']=='not_run' for x in r['entries'][1:])

def test_wall_budget_prevents_admission(tmp_path):
 lab=FakeLab();ticks=iter([0,2000]+[2000]*50)
 r=run(prepare(),tmp_path/'out',tmp_path/'state',lab,clock=lambda:next(ticks))
 assert lab.calls==0 and r['actual_calls']==0 and r['fresh_percent'] is None

def test_plan_changes_rejected_before_model_call(tmp_path):
 plan=prepare();plan['max_calls']+=1
 with pytest.raises(ValueError,match='Sealed plan'):run(plan,tmp_path/'out',tmp_path/'state',FakeLab())

def test_integrity_seal_and_staleness_are_separate(tmp_path):
 f=tmp_path/'e.json';f.write_text(json.dumps(seal(dict(source_hash='old'))))
 assert read(f)['matches_current_source'] is False
 value=json.loads(f.read_text());value['payload']['source_hash']='edited';f.write_text(json.dumps(value))
 with pytest.raises(ValueError,match='integrity'):read(f)

def test_cross_claim_credit_keeps_later_claim_allocation_and_year_reset():
 from healthcare_quality.advanced_runner import run as execute
 cases=authored_cases()[-2:];result=execute(cases)
 assert result['failed']==0
 cross=cases[0];before=cross['steps'][2]['expect'];after=cross['steps'][-1]['expect']
 assert before['payout_cents']==after['payout_cents'] and after['family_deductible']==10000
 assert cases[1]['steps'][1]['expect']['individual_deductible']==12000
 assert cases[1]['steps'][-1]['expect']['individual_deductible']==10000

def test_showcase_refreshes_only_owned_previous_version(monkeypatch):
 from tools import reliability_showcase as s
 calls=[];versions=iter([dict(version='8.6.0',owned=True),dict(version='8.7.0',owned=True)])
 monkeypatch.setattr(s,'start',lambda *a:next(versions));monkeypatch.setattr(s,'stop',lambda *a:calls.append('owned-stop'))
 monkeypatch.setattr('sys.argv',['showcase']);assert s.main()==0 and calls==['owned-stop']


def test_builder_batches_all_journeys_and_keeps_ai_credit_separate(tmp_path,monkeypatch):
 from healthcare_quality import reliability_evidence as evidence
 plan=prepare();result=summarize(plan,[],0);out=tmp_path/'study';out.mkdir()
 (out/'plan.json').write_text(json.dumps(plan));(out/'results.json').write_text(json.dumps(result))
 monkeypatch.setattr(evidence,'collect',lambda path:(result,[],[],[]))
 def bounded(cases,transport):
  assert 1<=len(cases)<=3 and transport=='http'
  return dict(results=[],passed=len(cases),failed=0,actions=sum(len(c['steps']) for c in cases))
 monkeypatch.setattr(evidence,'run',bounded)
 from healthcare_quality import effectiveness
 monkeypatch.setattr(effectiveness,'variants',lambda:[])
 payload=evidence.build(out)
 assert payload['journeys']['passed']==15 and payload['journeys']['execution']['batches']==5
 assert payload['defect_detection'][0]['scored'] is False

def test_postprocessing_compatibility_rejects_unrelated_or_generation_changes(monkeypatch):
 from healthcare_quality import reliability_evidence as evidence
 with pytest.raises(ValueError,match='Git commit'):evidence.source_compatibility('stale',{})
 with pytest.raises(ValueError,match='does not match'):evidence.source_compatibility('stale',dict(code_commit=prepare()['code_commit']))


def test_compatibility_allows_builder_only_but_fences_generation_changes(tmp_path,monkeypatch):
 import io,tarfile,hashlib
 from healthcare_quality import reliability_evidence as evidence
 files={'healthcare_quality/deductible_expectations.py':b'original','requirements.txt':b'','requirements-dev.txt':b'','pytest.ini':b''}
 blob=io.BytesIO()
 with tarfile.open(fileobj=blob,mode='w') as archive:
  for name,value in files.items():
   info=tarfile.TarInfo(name);info.size=len(value);archive.addfile(info,io.BytesIO(value))
 digest=hashlib.sha256()
 for name in sorted(files):digest.update(name.encode()+b'\0'+files[name]+b'\0')
 for name,value in files.items():
  file=tmp_path/name;file.parent.mkdir(parents=True,exist_ok=True);file.write_bytes(value)
 builder=tmp_path/'healthcare_quality/reliability_evidence.py';builder.write_text('postprocessing change')
 monkeypatch.setattr(evidence,'__file__',str(builder));monkeypatch.setattr(evidence,'source_hash',lambda:'new-source');monkeypatch.setattr(evidence.subprocess,'check_output',lambda *a,**kw:blob.getvalue())
 plan=dict(code_commit='0'*40);old=digest.hexdigest()
 assert evidence.source_compatibility(old,plan)['generation_and_evaluator_files_unchanged']
 (tmp_path/'healthcare_quality/deductible_expectations.py').write_text('changed generation')
 with pytest.raises(ValueError,match='Generation'):evidence.source_compatibility(old,plan)


def test_family_oop_journey_preserves_other_members_when_zero_allocation_reversed():
 from healthcare_quality.advanced_runner import run as execute
 case=next(c for c in authored_cases() if c['id']=='AB-J87-family-oop')
 assert case['steps'][2]['expect']['member_cents']==0 and case['steps'][2]['expect']['payout_cents']==190013
 assert case['steps'][-1]['expect']['family_oop']==60000
 assert execute([case])['failed']==0
