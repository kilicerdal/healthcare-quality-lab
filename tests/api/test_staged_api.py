import pytest
from tests.unit.test_compact_expectations import Provider,BASE
pytestmark=[pytest.mark.api,pytest.mark.regression]
URL='/api/advanced/expectations-v84'
def test_staged_estimate_counts_both_calls_without_generation(client,app):
 p=Provider();lab=app.extensions['expectations_v84'];lab.provider=p
 r=client.post(URL+'/estimate',json=BASE);assert r.status_code==200 and r.json['request_budget']==2 and not p.prompts and not lab.records()
def test_staged_export_remains_unapproved_and_wrong_values_stay_blocked(client,app):
 lab=app.extensions['expectations_v84'];lab.provider=Provider();r=lab.start(BASE,max_seconds=15);assert r['summary'][0]['eligible']==1
 out=client.post(URL+'/'+r['id']+'/propose',json={'row':0,'stage':'first'});assert out.status_code==201 and out.json['approval'] is None
 r['rows'][0]['first']['answer']['observations'][0]['expect']['payout_cents']+=1
 with lab.store.transaction() as db:lab.store.save(db,r)
 assert client.post(URL+'/'+r['id']+'/propose',json={'row':0,'stage':'first'}).status_code==409

def test_readiness_includes_staged_store(client,app):
 app.extensions['expectations_v84'].store.path.unlink();assert client.get('/api/ready').status_code==503
