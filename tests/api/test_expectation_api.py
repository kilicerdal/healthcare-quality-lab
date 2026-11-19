import threading
from copy import deepcopy
import pytest
from healthcare_quality.expectation_lab import ExpectationLab
from tests.unit.test_expectation_lab import Provider,BASE
pytestmark=[pytest.mark.api,pytest.mark.regression]
URL='/api/advanced/expectations'

def test_config_reads_never_generate_and_report_is_available(client):
 r=client.get(URL);assert r.status_code==200 and len(r.json['tasks'])==14 and not r.json['records'];assert client.get('/reports/v8.1').status_code==200

def test_successful_model_answer_exports_unchanged_and_unapproved(client,app,tmp_path):
 p=Provider();lab=app.extensions['expectations_v81'];lab.provider=p;r=lab.start(BASE);before=deepcopy(r['rows'][0]['first']['answer']);out=client.post(URL+'/'+r['id']+'/propose',json={'row':0,'stage':'first'});assert out.status_code==201 and out.json['approval'] is None and not out.json['runs'];assert out.json['provenance']['expectation_author']=='local model; no calculator assistance';assert lab.get(r['id'])['rows'][0]['first']['answer']==before;assert client.post('/api/advanced/'+out.json['id']+'/execute',json={'transport':'http'}).status_code==409

def test_export_rechecks_wrong_answer_instead_of_trusting_stored_assessment(client,app):
 lab=app.extensions['expectations_v81'];lab.provider=Provider();r=lab.start(BASE);r['rows'][0]['first']['answer']['observations'][0]['expect']['payout_cents']+=1
 with lab.store.transaction() as db:lab.store.save(db,r)
 assert client.post(URL+'/'+r['id']+'/propose',json={'row':0,'stage':'first'}).status_code==409

def test_readiness_detects_missing_expectation_store(client,app):
 assert client.get('/api/ready').status_code==200;app.extensions['expectations_v81'].store.path.unlink();assert client.get('/api/ready').status_code==503


@pytest.mark.parametrize('role',['auditor','customer','analyst','reviewer'])
def test_model_only_routes_keep_shared_role_and_csrf_boundaries(tmp_path,role):
 from healthcare_quality.app import create_app
 from werkzeug.security import generate_password_hash
 app=create_app({'TESTING':True,'DATABASE':str(tmp_path/'claims.sqlite'),'AUTH_MODE':'shared','SECRET_KEY':'x'*40,'IDENTITIES':{'user':{'password_hash':generate_password_hash('password'),'roles':[role],'actor_id':'customer-m100'}}});c=app.test_client();assert c.get(URL).status_code==401;session=c.post('/api/auth/login',json={'username':'user','password':'password'}).json;headers={'X-CSRF-Token':session['csrf_token']};assert c.get(URL).status_code==(403 if role=='customer' else 200)
 lab=app.extensions['expectations_v81'];lab.provider=Provider();r=lab.start(BASE);path=URL+'/'+r['id']+'/propose';body={'row':0,'stage':'first'}
 assert c.post(path,json=body).status_code==403
 response=c.post(path,json=body,headers=headers);assert response.status_code==(201 if role in ('analyst','reviewer') else 403)
 if role=='analyst':assert c.post('/api/advanced/'+response.json['id']+'/review',json={'reviewer':'spoof','note':'Test inspection note','revision':1},headers=headers).status_code==403
