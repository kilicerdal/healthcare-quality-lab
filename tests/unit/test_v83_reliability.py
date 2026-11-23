from copy import deepcopy
from pathlib import Path
import json,threading,time
import pytest
from healthcare_quality import compact_expectations_v83 as protocol
from healthcare_quality.expectation_lab import ExpectationLab,summary
from healthcare_quality.compact_evaluator import evaluate
from healthcare_quality.experiment_budget import estimate,request
from tests.unit.test_compact_expectations import Provider,BASE
pytestmark=[pytest.mark.unit,pytest.mark.regression]
ROOT=Path(__file__).resolve().parents[2]
def historical():return json.loads((ROOT/'artifacts/v8.2/heldout.json').read_text())
def lab(tmp_path,p):return ExpectationLab(tmp_path/'b.sqlite',p,threading.Lock(),protocol=protocol,evaluator=evaluate)

def test_historical_partial_metrics_do_not_look_like_finished_accuracy():
 record=historical();before=deepcopy(record);s=summary(record['rows'])[0];assert (s['assessed'],s['trials'],s['observations_correct'],s['eligible'],s['worksheet_mismatch_trials'])==(7,20,7,4,3);assert s['strict_percent'] is None and s['planned_progress_percent']==20;assert record==before

def test_unrequested_review_is_not_a_regression():
 from tools.expectation_report import analyze
 r=analyze([historical()]);p=r['paired_outcomes']['qwen3.5:27b'];assert p=={'review_not_requested':20};assert not r['complete']

def test_requested_unassessed_review_is_not_a_regression():
 from tools.expectation_report import analyze
 r=historical();r['rows']=r['rows'][:1];r['rows'][0]['self_review_requested']=True;p=analyze([r])['paired_outcomes']['qwen3.5:27b'];assert p=={'review_unassessed':1}

@pytest.mark.parametrize('bad',[0,-1,301,True,1.5,'180'])
def test_time_budget_rejects_invalid_values(bad):
 with pytest.raises(ValueError):request({**BASE,'max_seconds':bad})

def test_estimate_is_read_only_and_includes_every_step_and_review():
 r=historical();before=deepcopy(r);whole=estimate({**BASE,'models':['qwen3.5:27b'],'max_seconds':180},[r],protocol.cohort());steps=estimate({**BASE,'models':['qwen3.5:27b'],'strategy':'stepwise','self_review':True,'max_seconds':30},[r],protocol.cohort());assert whole['request_budget']==1 and 60<whole['estimated_seconds']<100;assert steps['request_budget']==4 and not steps['estimate_fits_budget'];assert r==before

class Blocking(Provider):
 timeout=240
 def __init__(self):super().__init__();self.started=threading.Event();self.release=threading.Event()
 def generate(self,*args):self.started.set();self.release.wait(5);return super().generate(*args)

def test_total_budget_returns_without_waiting_for_uncooperative_provider(tmp_path):
 p=Blocking();l=lab(tmp_path,p);start=time.monotonic()
 try:
  r=l.start({**BASE,'tasks':['D82-01','D82-02']},max_seconds=1);assert time.monotonic()-start<2;assert r['state']=='interrupted' and r['stop_reason']=='time_budget';assert len(r['rows'])==2 and len(r['rows'][0]['calls'])==1;assert r['rows'][0]['calls'][0]['phase']=='interrupted';assert r['rows'][0]['calls'][0]['timeout_seconds']<=1;assert p.timeout==240
 finally:p.release.set()
 assert l.lock.acquire(timeout=2);l.lock.release();assert 'response' not in l.get(r['id'])['rows'][0]['calls'][0]

def test_budget_does_not_mark_fast_completed_job_interrupted(tmp_path):
 p=Provider();p.timeout=240;l=lab(tmp_path,p);r=l.start(BASE,max_seconds=1);assert r['state']=='completed' and r['summary'][0]['eligible']==1;assert not r['budget'].get('expired',False);assert p.timeout==240

def test_restart_recovers_expired_total_budget_even_with_live_lease(tmp_path):
 from healthcare_quality import operations
 p=Provider();l=lab(tmp_path,p);r=l.start(BASE);r['state']='running';r['budget']={'deadline_epoch':0,'max_seconds':1}
 with l.store.transaction() as db:operations.start(db,r,'test',30);l.store.save(db,r)
 l.recover();out=l.get(r['id']);assert out['state']=='interrupted' and out['stop_reason']=='time_budget' and out['budget']['expired']

def test_guidance_has_no_calculator_calls_or_case_specific_answers(monkeypatch):
 from healthcare_quality import benefits,benefit_reference,advanced_reference,test_design
 def forbidden(*a,**kw):raise AssertionError('Calculator used in prompt')
 for module,name in ((benefits,'calculate'),(benefit_reference,'price'),(test_design,'compile_plan')):monkeypatch.setattr(module,name,forbidden)
 monkeypatch.setattr(advanced_reference.Oracle,'step',forbidden)
 for id in ('D83-01','D83-02'):
  task=next(t for t in protocol.cohort()['tasks'] if t['id']==id);text=protocol.prompt(task['plan']);assert 'IMMEDIATELY BEFORE THAT LINE' in text and 'ALL ZERO' in text;assert '161486' not in text and '9371' not in text

def test_old_worksheet_failures_stay_blocked_and_raw_values_unchanged():
 tasks={t['id']:t for t in protocol.cohort()['tasks']};r=historical();before=deepcopy(r);wrong=[]
 for row in r['rows']:
  a=row.get('first',{}).get('assessment',{})
  if a.get('schema_valid') and not a.get('eligible'):
   answer=protocol.parse(row['calls'][0]['response']['text']);assert answer==row['first']['answer'];result=evaluate(tasks[row['task_id']]['plan'],answer);assert result['observations_correct'] and not result['eligible'];wrong.append(row)
 assert len(wrong)==3 and r==before


def test_different_total_time_budgets_cannot_be_pooled(tmp_path):
 from healthcare_quality.expectation_lab import aggregate
 l=lab(tmp_path,Provider());a=l.start(BASE,max_seconds=30);b=l.start(BASE,max_seconds=60)
 with pytest.raises(ValueError,match='time budgets'):aggregate([a,b])


def test_cli_dry_run_has_time_budget_and_creates_no_state(tmp_path):
 import subprocess,sys
 state=tmp_path/'no.sqlite';output=tmp_path/'no.json';r=subprocess.run([sys.executable,'-m','tools.expectations_v83','--models','qwen3.5:27b','--tasks','D83-01','--state',str(state),'--output',str(output),'--max-seconds','60','--dry-run'],cwd=ROOT,text=True,capture_output=True);assert r.returncode==0,r.stderr;data=json.loads(r.stdout);assert data['request_budget']==1 and data['max_seconds']==60 and not data['estimate_fits_budget'];assert not state.exists() and not output.exists()
