import json,threading
from copy import deepcopy
import pytest
from healthcare_quality.expectation_lab import ExpectationLab,selection,aggregate
from healthcare_quality.expectation_protocol import cohort
from tests.unit.test_expectation_protocol import answer_for
pytestmark=[pytest.mark.unit,pytest.mark.regression]
BASE=dict(models=['qwen2.5-coder:3b'],tasks=['D81-01'],repeats=1,strategy='whole_case',self_review=True)
class Provider:
 settings={'fixture':'offline'}
 def __init__(self):self.prompts=[];self.answers=[]
 def status(self):return {'models':[{'name':'qwen2.5-coder:3b','digest':'offline-double'}]}
 def generate(self,model,prompt,schema):
  self.prompts.append(prompt)
  answer=self.answers.pop(0) if self.answers else answer_for(cohort()['tasks'][0]['plan'])
  return dict(text=json.dumps(answer),latency_ms=1,input_tokens=1,output_tokens=1)

def test_blind_self_review_happens_before_any_reference_assessment(tmp_path,monkeypatch):
 from healthcare_quality import expectation_evaluator
 p=Provider();real=expectation_evaluator.evaluate;counts=[]
 def evaluate(*args):counts.append(len(p.prompts));r=real(*args);r['secret']='REF_SECRET_NOT_FOR_MODEL';return r
 monkeypatch.setattr(expectation_evaluator,'evaluate',evaluate)
 lab=ExpectationLab(tmp_path/'e.sqlite',p,threading.Lock());r=lab.start(BASE);assert r['state']=='completed' and len(p.prompts)==2 and counts==[2,2];assert all('REF_SECRET_NOT_FOR_MODEL' not in text for text in p.prompts);assert r['approval'] is None;assert r['summary'][0]['reference_assisted_corrections']==0

def test_first_failure_and_self_review_success_stay_separate(tmp_path):
 p=Provider();bad=answer_for(cohort()['tasks'][0]['plan']);good=deepcopy(bad);bad['observations'][0]['expect']['payout_cents']+=1;p.answers=[bad,good];r=ExpectationLab(tmp_path/'e.sqlite',p,threading.Lock()).start(BASE);assert [s['eligible'] for s in r['summary']]==[0,1]

def test_stepwise_uses_only_own_predictions(tmp_path):
 p=Provider();a=answer_for(cohort()['tasks'][0]['plan']);p.answers=[dict(observations=[o]) for o in a['observations']]+[a];r=ExpectationLab(tmp_path/'e.sqlite',p,threading.Lock()).start({**BASE,'strategy':'stepwise'});assert r['state']=='completed' and len(p.prompts)==4;assert [s['eligible'] for s in r['summary']]==[1,1];assert 'YOUR own unverified predictions' in p.prompts[1]

@pytest.mark.parametrize('change',[{'repeats':True},{'self_review':1},{'models':['remote-model']},{'tasks':['bad']},{'tasks':['D81-01','D81-01']},{'strategy':'calculator'}])
def test_invalid_configuration_rejected(change):
 with pytest.raises(ValueError):selection({**BASE,**change})

def test_budget_counts_every_step_and_review():
 assert selection({**BASE,'strategy':'stepwise'})['request_budget']==4
 with pytest.raises(ValueError):selection({**BASE,'strategy':'stepwise','repeats':2,'tasks':['D81-01','D81-02','D81-03','D81-04']})

def test_provider_errors_are_failures_in_planned_denominator(tmp_path):
 class Broken(Provider):
  def generate(self,*args):raise TimeoutError()
 r=ExpectationLab(tmp_path/'e.sqlite',Broken(),threading.Lock()).start({**BASE,'tasks':['D81-01','D81-02']});assert r['state']=='completed';assert r['summary'][0]['trials']==2 and r['summary'][0]['provider_errors']==2 and r['summary'][0]['eligible']==0;assert r['summary'][1]['model_calls']==0

def test_exposure_survives_restart_and_duplicate_aggregation_is_blocked(tmp_path):
 p=Provider();lab=ExpectationLab(tmp_path/'e.sqlite',p,threading.Lock());a=lab.start(BASE);b=ExpectationLab(lab.store.path,p,threading.Lock()).start(BASE);assert b['previously_exposed_tasks']==['D81-01'];aggregate([a])
 # Reserved duplicate identities must never inflate the accuracy denominator.
 c=deepcopy(a);c['rows'][0]['split']='reserved_until_exposed'
 with pytest.raises(ValueError):aggregate([c,c])

def test_cancel_fences_late_response_and_preserves_all_planned_trials(tmp_path):
 started=threading.Event();release=threading.Event()
 class Blocking(Provider):
  def generate(self,*args):started.set();assert release.wait(3);return super().generate(*args)
 lock=threading.Lock();lab=ExpectationLab(tmp_path/'e.sqlite',Blocking(),lock);r=lab.start({**BASE,'tasks':['D81-01','D81-02']},True);assert started.wait(2);lab.cancel(r['id']);release.set();assert lock.acquire(timeout=2);lock.release();r=lab.get(r['id']);assert r['state']=='interrupted' and r['summary'][0]['trials']==2 and r['summary'][0]['unknown_requests']==1;assert 'response' not in r['rows'][0]['calls'][0]

def test_expired_lease_recovers_without_silent_retry(tmp_path):
 class Interrupt(Provider):
  def generate(self,*args):raise KeyboardInterrupt()
 p=Interrupt();lab=ExpectationLab(tmp_path/'e.sqlite',p,threading.Lock())
 with pytest.raises(KeyboardInterrupt):lab.start(BASE)
 lab.recover();r=lab.records()[0];assert r['state']=='interrupted' and r['summary'][0]['unknown_requests']==1


def test_target_requires_ten_unique_reserved_cases_and_finished_trials():
 from healthcare_quality.expectation_lab import summary
 rows=[dict(model='model',task_id=f'H{i}',split='reserved_until_exposed',repeat=1,calls=[],self_review_requested=False,phase='assessed',first={'assessment':{'eligible':i<8,'schema_valid':True}}) for i in range(10)]
 assert summary(rows)[0]['target_met'] and summary(rows)[0]['strict_percent']==80
 assert not summary(rows[:8])[0]['target_met']
 rows[-1]['phase']='pending';assert not summary(rows)[0]['target_met']

def test_old_sixteen_raw_failures_remain_blocked():
 from pathlib import Path
 from healthcare_quality.evaluation_v8 import cohort as v8_cohort
 from healthcare_quality.test_design import evaluate_answer
 r=json.loads((Path(__file__).resolve().parents[2]/'artifacts/v7.3/live-comparison.json').read_text());tasks={t['id']:t for t in v8_cohort()['tasks']}
 assert len(r['rows'])==16
 assert sum(evaluate_answer(tasks[row['task_id']]['plan'],row['response'])['eligible'] for row in r['rows'])==0


def test_aggregation_refuses_changed_model_weights(tmp_path):
 lab=ExpectationLab(tmp_path/'e.sqlite',Provider(),threading.Lock());a=lab.start(BASE);b=deepcopy(a);b['protocol']['model_digests']['qwen2.5-coder:3b']='changed-weights'
 with pytest.raises(ValueError):aggregate([a,b])
