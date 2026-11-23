import pytest
from tests.unit.test_compact_expectations import Provider,BASE
pytestmark=[pytest.mark.api,pytest.mark.regression]
URL='/api/advanced/expectations-v82'
def start(app):
 l=app.extensions['expectations_v82'];l.provider=Provider();return l.start(BASE)
def test_compact_configuration_and_catalog_do_not_infer(client,app):
 p=Provider();app.extensions['expectations_v82'].provider=p;r=client.get(URL);assert r.status_code==200 and len(r.json['tasks'])==16;assert len(client.get(URL+'/faults').json['faults'])==6;assert not p.prompts;assert client.get('/reports/v8.2').status_code==200

def test_exact_model_values_export_unapproved_then_pass_http(client,app):
 r=start(app);a=r['rows'][0]['first']['answer'];response=client.post(URL+'/'+r['id']+'/propose',json={'row':0,'stage':'first'});assert response.status_code==201;p=response.json;assert p['approval'] is None;assert [s['expect'] for s in p['cases'][0]['steps']]==[o['expect'] for o in a['observations']];path='/api/advanced/'+p['id'];assert client.post(path+'/execute',json={'transport':'http'}).status_code==409
 assert client.post(path+'/review',json={'reviewer':'Offline test inspection','note':'Fixture verification, not actual AI accuracy.','revision':p['revision']}).status_code==200
 run=client.post(path+'/execute',json={'transport':'http'});assert run.status_code==200 and run.json['runs'][-1]['passed']==1

def test_export_rechecks_values_and_stale_source(client,app):
 r=start(app);r['rows'][0]['first']['answer']['observations'][0]['expect']['member_cents']+=1;l=app.extensions['expectations_v82']
 with l.store.transaction() as db:l.store.save(db,r)
 assert client.post(URL+'/'+r['id']+'/propose',json={'row':0,'stage':'first'}).status_code==409
 r['protocol']['source_hash']='old'
 with l.store.transaction() as db:l.store.save(db,r)
 assert client.post(URL+'/'+r['id']+'/propose',json={'row':0,'stage':'first'}).json['error']=='STALE_EXPERIMENT'

def test_readiness_covers_new_store(client,app):
 assert client.get('/api/ready').status_code==200;app.extensions['expectations_v82'].store.path.unlink();assert client.get('/api/ready').status_code==503

@pytest.mark.parametrize('role',['auditor','customer','analyst','reviewer'])
def test_compact_shared_roles_and_csrf(tmp_path,role):
 from healthcare_quality.app import create_app
 from werkzeug.security import generate_password_hash
 app=create_app({'TESTING':True,'DATABASE':str(tmp_path/'c.sqlite'),'AUTH_MODE':'shared','SECRET_KEY':'x'*40,'IDENTITIES':{'user':{'password_hash':generate_password_hash('password'),'roles':[role],'actor_id':'customer-m100'}}});c=app.test_client();assert c.get(URL).status_code==401;s=c.post('/api/auth/login',json={'username':'user','password':'password'}).json;headers={'X-CSRF-Token':s['csrf_token']};assert c.get(URL).status_code==(403 if role=='customer' else 200)
 r=start(app);body={'row':0,'stage':'first'};path=URL+'/'+r['id']+'/propose';assert c.post(path,json=body).status_code==403;assert c.post(path,json=body,headers=headers).status_code==(201 if role in ('analyst','reviewer') else 403)
