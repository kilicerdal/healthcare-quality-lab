import json,threading
from copy import deepcopy
import pytest
from healthcare_quality.experiment_lab import ExperimentLab,config,cohort,summarize
from healthcare_quality.test_design import compile_plan
pytestmark=[pytest.mark.unit,pytest.mark.regression]
BASE=dict(models=['qwen2.5-coder:3b'],prompts=['focused-v68'],tasks=['XP-03'],repeats=1,modes=['ai_expectations','calculator_control'])
class Provider:
 settings={'temperature':0,'seed':7}
 def __init__(self):self.calls=0
 def status(self):return {'models':[{'name':'qwen2.5-coder:3b','digest':'fixture-only'}]}
 def generate(self,*args):self.calls+=1;return {'text':json.dumps({'cases':[compile_plan(cohort()['tasks'][2]['plan'])]}),'latency_ms':1,'input_tokens':10,'output_tokens':20}

def test_calculator_control_never_counted_as_ai_reasoning(tmp_path):
 p=Provider();lab=ExperimentLab(tmp_path/'e.sqlite',p,threading.BoundedSemaphore(1));r=lab.start(BASE);assert r['state']=='completed' and r['approval'] is None and p.calls==1;assert {x['ai_reasoning_metric'] for x in r['summary']}=={True,False};assert all(x['reference_assisted_corrections']==0 for x in r['summary'])

def test_exposure_reserved_and_retained_across_later_runs(tmp_path):
 lab=ExperimentLab(tmp_path/'e.sqlite',Provider(),threading.BoundedSemaphore(1));a=lab.start(BASE);b=lab.start(BASE);assert a['first_recorded_in_this_ledger'] and b['previously_exposed_tasks']==['XP-03']

@pytest.mark.parametrize('change',[{'repeats':True},{'tasks':['XP-UNKNOWN']},{'models':['not-local']},{'prompts':['unreviewed']},{'modes':['code']},{'tasks':['XP-03','XP-03']}])
def test_invalid_protocol_rejected(change):
 with pytest.raises(ValueError):config({**BASE,**change})

def test_combination_budget_rejected():
 with pytest.raises(ValueError):config({**BASE,'tasks':[t['id'] for t in cohort()['tasks']],'repeats':3})

def test_provider_error_is_not_wrong_financial_answer(tmp_path):
 class Broken(Provider):
  def generate(self,*args):raise TimeoutError('offline fixture')
 lab=ExperimentLab(tmp_path/'e.sqlite',Broken(),threading.BoundedSemaphore(1));r=lab.start({**BASE,'modes':['ai_expectations']});s=r['summary'][0];assert s['provider_errors']==1 and s['wrong_or_incomplete']==0 and s['unknown_outcomes']==0

def test_interrupted_request_preserves_exposure_and_unknown_outcome(tmp_path):
 class Interrupt(Provider):
  def generate(self,*args):raise KeyboardInterrupt()
 lab=ExperimentLab(tmp_path/'e.sqlite',Interrupt(),threading.BoundedSemaphore(1))
 with pytest.raises(KeyboardInterrupt):lab.start({**BASE,'modes':['ai_expectations']})
 lab.recover();r=lab.records()[0];assert r['state']=='interrupted' and r['summary'][0]['unknown_outcomes']==1 and r['summary'][0]['provider_errors']==0

def test_cancellation_fences_late_response_without_provider_error(tmp_path):
    started=threading.Event();release=threading.Event()
    class Blocking(Provider):
        def generate(self,*args):started.set();assert release.wait(3);return super().generate(*args)
    lock=threading.BoundedSemaphore(1);lab=ExperimentLab(tmp_path/'e.sqlite',Blocking(),lock);r=lab.start({**BASE,'modes':['ai_expectations']},True);assert started.wait(2);cancelled=lab.cancel(r['id']);release.set();assert lock.acquire(timeout=2);lock.release();saved=lab.get(r['id']);assert saved['state']=='interrupted' and saved['summary'][0]['unknown_outcomes']==1 and saved['summary'][0]['provider_errors']==0;assert 'response' not in saved['rows'][0]

def test_repeated_stability_ignores_generated_titles(tmp_path):
    class Renamed(Provider):
        def generate(self,*args):
            result=super().generate(*args);data=json.loads(result['text']);data['cases'][0]['title']='Changed title '+str(self.calls);result['text']=json.dumps(data);return result
    lab=ExperimentLab(tmp_path/'e.sqlite',Renamed(),threading.BoundedSemaphore(1));r=lab.start({**BASE,'repeats':2,'modes':['ai_expectations']});assert r['summary'][0]['stable_repeated_tasks']==1
