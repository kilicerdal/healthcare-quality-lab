import pytest
from tests.support.v86_model_fixtures import Provider
from tests.unit.test_compact_expectations import BASE
pytestmark=[pytest.mark.api,pytest.mark.regression]
URL='/api/advanced/expectations-v86'
def test_budget_and_estimate_are_explicit_and_do_not_generate(client,app):
 lab=app.extensions['expectations_v86'];lab.provider=Provider();assert client.post(URL,json=BASE).json['error']=='TIME_BUDGET_REQUIRED';r=client.post(URL+'/estimate',json={**BASE,'max_seconds':180});assert r.status_code==200 and r.json['request_budget']==2 and not lab.provider.prompts

def test_new_fields_are_rechecked_on_public_export(client,app):
 lab=app.extensions['expectations_v86'];lab.provider=Provider();r=lab.start(BASE,max_seconds=15);out=client.post(URL+'/'+r['id']+'/propose',json={'row':0,'stage':'first'});assert out.status_code==201 and out.json['approval'] is None
 r['rows'][0]['first']['answer']['observations'][0]['calculation'][0]['individual_deductible_remaining_cents']+=1
 with lab.store.transaction() as db:lab.store.save(db,r)
 assert client.post(URL+'/'+r['id']+'/propose',json={'row':0,'stage':'first'}).json['error']=='EXPECTATIONS_BLOCKED'

def test_readiness_covers_v86_store(client,app):
 app.extensions['expectations_v86'].store.path.unlink();assert client.get('/api/ready').status_code==503
