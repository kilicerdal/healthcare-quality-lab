import pytest
from healthcare_quality.app import create_app
from werkzeug.security import generate_password_hash
pytestmark=[pytest.mark.api,pytest.mark.regression]
BASE='/api/advanced/workbench'
def proposal(client):return client.post(BASE+'/propose',json={'pack':'medicare_b','scenario':0}).json

def test_workbench_packs_queue_assistant_and_routing_never_approve(client):
 r=client.get(BASE);assert r.status_code==200;assert len(r.json['packs'])==8;assert len(r.json['cohort']['tasks'])==31
 p=proposal(client);assert p['approval'] is None and not p['runs'];id=p['id']
 a=client.get(BASE+'/assistant/'+id).json;assert a['live_model_calls']==0 and not a['can_approve'] and not a['can_execute'];assert a['facts']
 r=client.post(BASE+'/team/'+id,json={'owner':'QE team','decision':'ready_for_review','note':'Inspect independent financial expectations'});assert r.status_code==200 and r.json['approval'] is None
 assert len(client.get(BASE+'/team/'+id).json['current'])==1
 assert client.get(BASE).json['queue'][0]['decision']=='ready_for_review'
 assert client.post('/api/advanced/'+id+'/execute',json={'transport':'service'}).status_code==409
 assert len(client.get(BASE+'/gaps').json['proposed_packs'])==7

@pytest.mark.parametrize('body',[{}, {'pack':'x','scenario':0},{'pack':'medicare_b','scenario':True},{'pack':'medicare_b','scenario':-1},{'pack':'medicare_b','scenario':0,'approve':True}])
def test_invalid_pack_requests_are_client_errors(client,body):assert client.post(BASE+'/propose',json=body).status_code==400

def test_invalid_plan_and_routing_decision_are_explicit(client):
 assert not client.post(BASE+'/inspect',json={'plan':{}}).json['valid']
 p=proposal(client);assert client.post(BASE+'/team/'+p['id'],json={'owner':'QE','decision':'approved','note':'Try to bypass review'}).status_code==400

@pytest.mark.parametrize('role',['auditor','customer','analyst','reviewer'])
def test_shared_role_boundaries(tmp_path,role):
 app=create_app({'TESTING':True,'DATABASE':str(tmp_path/'claims.sqlite'),'AUTH_MODE':'shared','SECRET_KEY':'x'*40,'IDENTITIES':{'user':{'password_hash':generate_password_hash('password'),'roles':[role],'actor_id':'auditor-demo' if role=='auditor' else 'customer-m100'}}});c=app.test_client()
 assert c.get(BASE).status_code==401
 login=c.post('/api/auth/login',json={'username':'user','password':'password'});token=login.json['csrf_token']
 assert c.get(BASE).status_code==(403 if role=='customer' else 200)
 assert c.post(BASE+'/propose',json={'pack':'medicare_b','scenario':0}).status_code==403
 r=c.post(BASE+'/propose',json={'pack':'medicare_b','scenario':0},headers={'X-CSRF-Token':token});assert r.status_code==(201 if role in ('analyst','reviewer') else 403)

def test_new_stores_are_readiness_checked(client,app):
 assert client.get('/api/ready').status_code==200
 app.extensions['team_v8'].path.unlink();assert client.get('/api/ready').status_code==503

def test_quality_gated_ai_export_rejects_missing_readback(client,app):
 from healthcare_quality.coverage_packs import plan_for
 from healthcare_quality.test_design import compile_plan
 from healthcare_quality.advanced_lab import contract_hash
 from tools.fingerprints import source_hash
 p=plan_for('commercial_ppo');p['case']['steps'].pop();lab=app.extensions['designs'];r=dict(id='a'*32,created_at='2026-11-18',state='proposed',plan=p,cases=[compile_plan(p)],assessment={'eligible':True},source_hash=source_hash(),contract_hash=contract_hash(),model='qwen2.5-coder:3b');lab.store.create(r)
 assert client.post(BASE+'/assistant/designs/'+r['id']+'/propose',json={}).status_code==409
 p=plan_for('commercial_ppo');r.update(id='b'*32,plan=p,cases=[compile_plan(p)]);lab.store.create(r)
 out=client.post(BASE+'/assistant/designs/'+r['id']+'/propose',json={});assert out.status_code==201 and out.json['approval'] is None;assert out.json['provenance']['reference_assisted_correction'] is False


@pytest.mark.parametrize('version',['v7.'+str(i) for i in range(1,10)]+['v8.0'])
def test_all_new_milestone_reports_are_served(client,version):
 response=client.get('/reports/'+version)
 assert response.status_code==200 and (version.upper()+' Engineering Report').encode() in response.data
 assert b'Purpose and location' in response.data and b'Outcome and practical limits' in response.data

def test_ai_export_blocks_duplicate_business_inputs(client,app):
 from healthcare_quality.coverage_packs import plan_for
 from healthcare_quality.test_design import compile_plan
 from healthcare_quality.advanced_lab import contract_hash
 from tools.fingerprints import source_hash
 p=plan_for('commercial_ppo');app.extensions['advanced'].propose([compile_plan(p)])
 r=dict(id='c'*32,created_at='2026-11-18',state='proposed',plan=p,cases=[compile_plan(p)],assessment={'eligible':True},source_hash=source_hash(),contract_hash=contract_hash(),model='qwen2.5-coder:3b');app.extensions['designs'].store.create(r)
 assert client.post(BASE+'/assistant/designs/'+r['id']+'/propose',json={}).status_code==409


def test_assistant_explains_invalid_saved_ai_proposal_without_crashing(client,app):
 r=app.extensions['advanced'].propose([{'id':'BAD','steps':[]}],{'origin':'offline_invalid_model_double'})
 response=client.get(BASE+'/assistant/'+r['id']);assert response.status_code==200
 assert response.json['recommendations'][0]['issue']['code']=='INVALID_PLAN'
 assert len(client.get(BASE+'/gaps').json['proposed_packs'])==8
