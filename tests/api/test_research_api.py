import pytest
from tests.support.ai_fixtures import FixtureProvider,sample_case,generation_request,review_request
from tests.unit.test_investigator import experiment
pytestmark=[pytest.mark.api,pytest.mark.regression]
def test_overview_readonly_and_reserved_budget(app):
    s=app.extensions['studio'];s.provider=FixtureProvider();c=app.test_client();assert c.get('/api/research/overview').status_code==200 and not s.provider.calls
    assert c.post('/api/research/benchmarks',json=dict(models=['cloud'],task_ids=['R01'],repeats=2)).status_code==400

def test_change_impact_and_unapproved_ai_followup(app):
    s=app.extensions['studio'];s.provider=FixtureProvider();c=app.test_client();impact=c.post('/api/research/changes',json=dict(rule_ids=['HC-007']));assert impact.status_code==200 and impact.json['affected']
    r=c.post('/api/research/changes/propose',json=dict(rule_ids=['HC-007'],model='qwen2.5-coder:3b'));assert r.status_code==201 and r.json['approval'] is None

def test_grounded_investigation_saved_without_model(app):
    s=app.extensions['studio'];s.provider=FixtureProvider();r=s.generate(generation_request());r=s.review(r['id'],review_request(r));run=s.execute(r['id'],dict(expected_revision=r['revision']));calls=len(s.provider.calls)
    c=app.test_client();a=c.post('/api/research/investigations',json=dict(experiment_id=r['id'],run_id=run['id'],model=None));assert a.status_code==201 and a.json['analysis']['findings'][0]['category']=='passed' and len(s.provider.calls)==calls
    overview=c.get('/api/research/overview');assert overview.status_code==200 and overview.json['investigations'][0]['id']==a.json['id']

def test_advanced_api_full_journey_and_atomic_error(client):
    headers={'X-Demo-Actor':'customer-m100'};r=client.post('/api/benefits/claims',headers=headers,json=dict(operation_key='api-submit-100',id='API-BEN-100',member_id='M100',plan_id='commercial_ppo',service_date='2026-03-01',lines=[dict(id='L1',service='medical',allowed_cents=100000)]));assert r.status_code==201 and r.json['calculation']['totals']['payout_cents']==71200
    pay=dict(operation_key='api-pay-100',expected_revision=1);p=client.post('/api/benefits/claims/API-BEN-100/pay',headers={'X-Demo-Actor':'finance-demo'},json=pay);assert p.status_code==200 and p.json['ledger'][0]['amount']==71200
    assert client.post('/api/benefits/claims/API-BEN-100/pay',headers={'X-Demo-Actor':'finance-demo'},json=pay).json==p.json
    assert client.get('/api/benefits/claims/API-BEN-100',headers={'X-Demo-Actor':'customer-m200'}).status_code==403
    assert client.post('/api/benefits/claims/API-BEN-100/reverse',headers={'X-Demo-Actor':'customer-m100'},json=dict(operation_key='api-reverse-100',expected_revision=2,note='Invalid customer reversal')).status_code==403

def test_local_auth_session_and_logout_safe(client):
    assert client.get('/api/auth/session').json['mode']=='local';assert client.post('/api/auth/logout').status_code==200


def test_readiness_checks_new_benefit_store(app):
    c=app.test_client();assert c.get('/api/ready').json['storage']['benefits']=='ready'
    with app.extensions['benefits'].tx() as db:db.execute('DROP TABLE benefit_claims')
    assert c.get('/api/ready').status_code==503 and c.get('/api/ready').json['storage']['benefits']=='unavailable'
