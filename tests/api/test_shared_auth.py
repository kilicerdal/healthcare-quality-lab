import pytest,sqlite3
from werkzeug.security import generate_password_hash
from healthcare_quality.app import create_app
pytestmark=[pytest.mark.api,pytest.mark.regression]
@pytest.fixture
def shared(tmp_path):
    users={name:dict(password_hash=generate_password_hash('FixturePasswordOnly!'),roles=roles,actor_id=actor) for name,roles,actor in [('reviewer',['reviewer'],'auditor-demo'),('analyst',['analyst'],'auditor-demo'),('customer',['customer'],'customer-m100')]}
    return create_app(dict(TESTING=True,DATABASE=str(tmp_path/'claims.sqlite'),AUTH_MODE='shared',SECRET_KEY='test-secret-that-is-more-than-32-characters',IDENTITIES=users))
def login(client,name='reviewer'):return client.post('/api/auth/login',json=dict(username=name,password='FixturePasswordOnly!')).json['csrf_token']
def test_shared_authentication_csrf_roles_and_spoofing(shared):
    c=shared.test_client();assert c.get('/api/catalog').status_code==401;csrf=login(c,'analyst')
    assert c.post('/api/ai/experiments/missing/review',json={}).status_code==403
    assert c.post('/api/ai/experiments/missing/review',json={},headers={'X-CSRF-Token':csrf}).json['error']=='REVIEWER_ROLE_REQUIRED'
    assert c.get('/api/claims',headers={'X-Demo-Actor':'finance-demo'}).status_code==403
    assert c.get('/api/catalog').status_code==200

def test_customer_cannot_read_ai_records(shared):
    c=shared.test_client();login(c,'customer');assert c.get('/api/ai/experiments').status_code==403

def test_login_failure_and_secret_not_disclosed(shared):
    c=shared.test_client();r=c.post('/api/auth/login',json=dict(username='reviewer',password='wrong'));assert r.status_code==401 and b'password_hash' not in r.data

def test_audit_detects_tampering(shared):
    c=shared.test_client();c.get('/api/health');audit=shared.extensions['audit'];assert audit.verify()['valid']
    with sqlite3.connect(audit.path) as db:db.execute("UPDATE review_audit SET record='{}' WHERE seq=1")
    assert not audit.verify()['valid']

def test_shared_mode_requires_secret_and_hashed_users(tmp_path):
    with pytest.raises(ValueError):create_app(dict(TESTING=True,DATABASE=str(tmp_path/'x.sqlite'),AUTH_MODE='shared'))


def test_review_identity_cannot_be_forged(shared):
    from tests.support.ai_fixtures import FixtureProvider,generation_request,review_request
    s=shared.extensions['studio'];s.provider=FixtureProvider();r=s.generate(generation_request());c=shared.test_client();csrf=login(c)
    body=review_request(r);body['reviewer_label']='pretend admin'
    response=c.post('/api/ai/experiments/'+r['id']+'/review',json=body,headers={'X-CSRF-Token':csrf});assert response.status_code==200
    assert response.json['approval']['reviewer_label']=='reviewer' and response.json['approval']['authenticated_identity']['username']=='reviewer'


def test_new_advanced_and_integration_routes_keep_identity_and_review_gates(shared):
    from tests.unit.test_advanced_cases import CASES
    c=shared.test_client()
    assert c.get('/api/advanced').status_code==401
    assert c.get('/api/integrations').status_code==401
    login(c,'customer')
    assert c.get('/api/advanced').status_code==403 and c.get('/api/integrations').status_code==403
    csrf=login(c,'analyst')
    record=c.post('/api/advanced/import',json={'cases':CASES[:1]},headers={'X-CSRF-Token':csrf}).json
    review=dict(reviewer='forged-reviewer',note='Inspect independent money and ledger expectations',revision=1)
    assert c.post('/api/advanced/'+record['id']+'/review',json=review,headers={'X-CSRF-Token':csrf}).json['error']=='REVIEWER_ROLE_REQUIRED'
    csrf=login(c,'reviewer')
    assert c.post('/api/advanced/'+record['id']+'/review',json=review).status_code==403
    result=c.post('/api/advanced/'+record['id']+'/review',json=review,headers={'X-CSRF-Token':csrf})
    assert result.status_code==200 and result.json['approval']['reviewer']=='reviewer'

def test_v7_new_workbenches_preserve_shared_role_and_csrf_boundaries(shared):
    paths=['designs','experiments','investigations','traceability','effectiveness','portfolio'];c=shared.test_client()
    for path in paths:assert c.get('/api/advanced/'+path).status_code==401
    login(c,'customer')
    for path in paths:assert c.get('/api/advanced/'+path).status_code==403
    token=login(c,'analyst');assert c.post('/api/advanced/portfolio/control',json={}).status_code==403
    r=c.post('/api/advanced/portfolio/control',json={},headers={'X-CSRF-Token':token});assert r.status_code==201 and r.json['approval'] is None
