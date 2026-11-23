import pytest
from tests.unit.test_compact_expectations import Provider,BASE
pytestmark=[pytest.mark.api,pytest.mark.regression]
URL='/api/advanced/expectations-v85'
def test_budget_required_and_estimate_does_not_generate(client,app):
 p=Provider();lab=app.extensions['expectations_v85'];lab.provider=p
 assert client.post(URL,json=BASE).json['error']=='TIME_BUDGET_REQUIRED'
 r=client.post(URL+'/estimate',json={**BASE,'max_seconds':180});assert r.status_code==200 and r.json['stage_totals']=={'pricing':15,'lifecycle':15} and not p.prompts and not lab.records()
 assert client.get(URL).json['default_max_seconds'] is None

def test_original_scores_and_unapproved_export_remain_separate(client,app):
 lab=app.extensions['expectations_v85'];lab.provider=Provider();r=lab.start(BASE,max_seconds=15);out=client.get(URL+'/'+r['id']).json;assert out['first_attempt_scorecard']['counts']=={'first_pass':1}
 proposal=client.post(URL+'/'+r['id']+'/propose',json={'row':0,'stage':'first'});assert proposal.status_code==201 and proposal.json['approval'] is None

def test_readiness_covers_new_store(client,app):
 app.extensions['expectations_v85'].store.path.unlink();assert client.get('/api/ready').status_code==503
