from copy import deepcopy
import pytest
from tools.evaluate_first_attempts_v85 import prepare,run
from healthcare_quality.expectation_scorecard_v85 import KIND
pytestmark=[pytest.mark.unit,pytest.mark.regression]
class Fixture:
 def __init__(self,timeout=False):self.calls=[];self.timeout=timeout
 def start(self,body,max_seconds):
  self.calls.append(body);calls=[dict(stage='first',generation={'phase':p},phase='response_frozen',response={}) for p in ('pricing','lifecycle')]
  if self.timeout:calls[-1].update(phase='interrupted');first={}
  else:first={'answer':{'observations':[{}]},'assessment':{'eligible':True,'schema_valid':True}}
  return dict(id=str(len(self.calls)),kind=KIND,state='interrupted' if self.timeout else 'completed',stop_reason='time_budget' if self.timeout else None,protocol={'selection':body},rows=[dict(model=body['models'][0],task_id=body['tasks'][0],split='reserved_until_exposed',calls=calls,first=first)])
def test_all_fresh_denominators_remain_after_timeout(tmp_path):
 f=Fixture(True);r=run(prepare(),tmp_path/'out',tmp_path/'state.sqlite',f);assert len(f.calls)==1 and r['fresh_planned']==3 and r['fresh_first_attempt_percent'] is None and [e['outcome'] for e in r['entries']]==['timeout','not_run','not_run','not_run']
def test_plan_mismatch_and_existing_evidence_prevent_new_calls(tmp_path):
 plan=prepare();plan['case_max_seconds']=300;f=Fixture()
 with pytest.raises(ValueError):run(plan,tmp_path/'out',tmp_path/'state.sqlite',f)
 (tmp_path/'state.sqlite').touch()
 with pytest.raises(ValueError):run(prepare(),tmp_path/'out',tmp_path/'state.sqlite',f)
 assert not f.calls

def test_exposed_trial_never_inflates_fresh_score(tmp_path):
 f=Fixture();r=run(prepare(),tmp_path/'out',tmp_path/'state.sqlite',f);assert r['actual_calls']==8 and r['fresh_first_passes']==3 and r['fresh_planned']==3 and not r['qualification']

def test_full_case_headroom_is_required_before_next_admission(tmp_path):
 f=Fixture();ticks=iter([0,0,500,500]);r=run(prepare(),tmp_path/'out',tmp_path/'state.sqlite',f,clock=lambda:next(ticks));assert len(f.calls)==1 and r['entries'][1]['outcome']=='not_run' and r['fresh_first_attempt_percent'] is None

def test_preflight_error_preserves_planned_cases_without_new_model_work(tmp_path):
 from healthcare_quality.ai_studio import StudioError
 class Missing(Fixture):
  def start(self,*a,**kw):raise StudioError('MODEL_UNAVAILABLE','fixture missing model',409)
 r=run(prepare(),tmp_path/'out',tmp_path/'state.sqlite',Missing());assert r['actual_calls']==0 and r['entries'][0]['outcome']=='preflight_error' and len(r['entries'])==4

def test_model_identity_drift_is_not_pooled(tmp_path):
 class Changed(Fixture):
  def start(self,*a,**kw):
   r=super().start(*a,**kw);r['protocol']['model_digests']={'fixture':str(len(self.calls))};return r
 f=Changed();r=run(prepare(),tmp_path/'out',tmp_path/'state.sqlite',f);assert len(f.calls)==2 and not r['protocol_stable'] and not r['fresh_complete'] and r['entries'][1]['outcome']=='provider_changed'

def test_source_drift_invalidates_combined_score(tmp_path,monkeypatch):
 import tools.evaluate_first_attempts_v85 as runner
 plan=prepare();changed=[False];monkeypatch.setattr(runner,'source_hash',lambda:'changed' if changed[0] else plan['source_hash'])
 class Drift(Fixture):
  def start(self,*a,**kw):r=super().start(*a,**kw);changed[0]=True;return r
 r=run(plan,tmp_path/'out',tmp_path/'state.sqlite',Drift());assert not r['protocol_stable'] and r['entries'][0]['outcome']=='source_changed' and r['fresh_first_attempt_percent'] is None
