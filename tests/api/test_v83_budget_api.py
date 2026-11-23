import json
from pathlib import Path
import pytest
from tests.unit.test_compact_expectations import Provider,BASE
pytestmark=[pytest.mark.api,pytest.mark.regression]
URL='/api/advanced/expectations-v83'
def test_estimate_does_not_start_inference_or_save_experiment(client,app):
 p=Provider();lab=app.extensions['expectations_v83'];lab.provider=p;r=client.post(URL+'/estimate',json={**BASE,'max_seconds':10});assert r.status_code==200 and r.json['request_budget']==1 and not r.json['estimate_fits_budget'];assert not p.prompts and not lab.records()

def test_invalid_budget_rejected_before_provider_status(client,app):
 class NoStatus(Provider):
  def status(self):raise AssertionError('Preflight should not run')
 app.extensions['expectations_v83'].provider=NoStatus();r=client.post(URL,json={**BASE,'max_seconds':True});assert r.status_code==400 and r.json['error']=='INVALID_TIME_BUDGET'

def test_old_record_get_has_honest_derived_metrics_without_rewriting(client,app):
 p=Path(__file__).resolve().parents[2]/'artifacts/v8.2/heldout.json';r=json.loads(p.read_text());lab=app.extensions['expectations_v83'];lab.store.create(r);out=client.get(URL+'/'+r['id']);assert out.status_code==200 and not out.json['qualification_complete'];s=out.json['summary'][0];assert s['strict_percent'] is None and s['observations_correct']==7 and s['eligible']==4;assert lab.store.get(r['id'])==r


def test_public_live_entrypoint_always_admits_a_budget(client,app):
 app.extensions['expectations_v83'].provider=Provider();r=client.post(URL,json=BASE);assert r.status_code==202 and r.json['budget']['max_seconds']==180


def test_complete_development_run_is_not_complete_qualification(client,app):
 lab=app.extensions['expectations_v83'];lab.provider=Provider();r=lab.start(BASE);out=client.get(URL+'/'+r['id']).json;assert out['run_complete'] and not out['qualification_complete']
