import pytest
from tests.support.api_client import ClaimsClient
pytestmark=[pytest.mark.api,pytest.mark.regression]


@pytest.mark.smoke
def test_api_lifecycle(client):
    api=ClaimsClient(client)
    created=api.submit()
    assert created.status_code==201
    assert created.json["claim"]["status"]=="submitted"
    assert api.as_actor("adjuster-demo").transition("API-100","approved").status_code==200
    paid=api.as_actor("finance-demo").transition("API-100","paid")
    assert paid.status_code==200
    assert paid.json["payment"]["amount_cents"]==90000
    assert [e["revision"] for e in paid.json["events"]]==[1,2,3]


@pytest.mark.sanity
def test_duplicate_conflict_and_replay_leave_evidence_unchanged(client):
    api=ClaimsClient(client);created=api.submit().json
    duplicate=api.submit()
    assert duplicate.status_code==409
    assert duplicate.json["error"]=="DUPLICATE_CLAIM"
    assert api.get("API-100").json==created


@pytest.mark.parametrize("actor",[None,"missing","customer-m200"])
def test_missing_unknown_or_other_customer_cannot_read(client,actor):
    ClaimsClient(client).submit()
    response=client.get('/api/claims/API-100',headers={'X-Demo-Actor':actor} if actor else {})
    assert response.status_code==403
    assert response.json["rule_id"]=="WF-001"


def test_list_is_scoped_to_owner_and_staff_has_readonly_access(client):
    api=ClaimsClient(client);api.submit()
    assert api.as_actor("customer-m200").list().json["claims"]==[]
    assert len(api.as_actor("auditor-demo").list().json["claims"])==1
    assert api.as_actor("auditor-demo").transition("API-100","approved").status_code==403


def test_denial_returns_evaluation_and_does_not_reserve_id(client):
    api=ClaimsClient(client)
    denied=api.submit(service="dental")
    assert denied.status_code==422
    assert denied.json["details"]["evaluation"]["reason"]=="SERVICE_NOT_COVERED"
    assert api.list().json["claims"]==[]
    assert api.submit().status_code==201


@pytest.mark.parametrize("overpost",[{"role":"finance"},{"active":True},{"plan_id":"medicare_advantage"}])
def test_server_rejects_overposted_identity_and_policy(client,overpost):
    response=ClaimsClient(client).submit(**overpost)
    assert response.status_code==400
    assert response.json["error"]=="INVALID_REQUEST"


def test_api_payment_cannot_skip_approval_or_be_replayed(client):
    api=ClaimsClient(client);api.submit()
    finance=api.as_actor("finance-demo")
    assert finance.transition("API-100","paid").status_code==409
    api.as_actor("adjuster-demo").transition("API-100","approved")
    paid=finance.transition("API-100","paid").json
    assert finance.transition("API-100","paid").status_code==409
    assert api.get("API-100").json==paid


def test_unknown_claim_and_malformed_target(client):
    api=ClaimsClient(client).as_actor("adjuster-demo")
    assert api.get("MISSING").status_code==404
    assert api.transition("MISSING","approved").status_code==404
    assert api.transition("MISSING","submitted").status_code==400


def test_export_endpoint_contains_snapshot_and_timeline(client):
    api=ClaimsClient(client);created=api.submit().json
    response=client.get('/api/claims/API-100/evidence',headers=api.headers)
    assert response.status_code==200
    assert response.json==created
    assert response.headers['Cache-Control']=='no-store'


def test_database_failure_returns_503_and_rolls_back(client,app):
    api=ClaimsClient(client);api.submit()
    before=api.as_actor('adjuster-demo').transition('API-100','approved').json
    with app.extensions['workflow'].store.transaction(write=True) as db:
        db.execute("CREATE TRIGGER injected BEFORE INSERT ON payments BEGIN SELECT RAISE(ABORT,'test fault'); END")
    response=api.as_actor('finance-demo').transition('API-100','paid')
    assert response.status_code==503
    assert response.json['error']=='STORAGE_ERROR'
    assert api.get('API-100').json==before


def test_workflow_fixtures_are_explicitly_synthetic(client):
    response=client.get('/api/workflow/fixtures')
    assert response.status_code==200
    assert response.json['synthetic'] is True
    assert len(response.json['members'])==9
    assert len(response.json['actors'])==12
    assert 'not authentication' in response.json['identity_mode']


def test_app_test_database_is_outside_interactive_database(app):
    from healthcare_quality.app import ROOT
    assert not str(app.config['DATABASE']).startswith(str(ROOT/'.local'))


def test_previous_version_report_remains_available(client):
    response=client.get('/reports/v1')
    assert response.status_code==200
    assert b'Healthcare Quality Lab V1 Engineering Report' in response.data
    assert client.get('/reports/v99').status_code==404
