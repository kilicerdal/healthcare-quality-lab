import pytest
pytestmark=[pytest.mark.api,pytest.mark.regression]
from copy import deepcopy
from tests.unit.test_advanced_cases import CASES


def test_advanced_review_and_real_http_execution(client):
    response=client.post('/api/advanced/import',json={'cases':CASES[:1]});assert response.status_code==201
    r=response.json;id=r['id'];assert r['assessment']['review_ready']
    assert client.post('/api/advanced/'+id+'/execute',json={'transport':'http'}).status_code==409
    assert client.post('/api/advanced/'+id+'/review',json=dict(reviewer='engineer',note='Independently inspected reference results',revision=1)).status_code==200
    execution=client.post('/api/advanced/'+id+'/execute',json={'transport':'http'})
    assert execution.status_code==200 and execution.json['runs'][-1]['passed']==1
    assert client.get('/api/advanced').json['records'][0]['id']==id


def test_bad_reference_cannot_be_approved(client):
    c=deepcopy(CASES[0]);c['steps'][0]['expect']['payout_cents']+=1
    r=client.post('/api/advanced/import',json={'cases':[c]}).json
    assert client.post('/api/advanced/'+r['id']+'/review',json=dict(reviewer='engineer',note='Review must remain blocked',revision=1)).status_code==409


def test_readiness_includes_advanced_store(client,app):
    assert client.get('/api/ready').json['storage']['advanced']=='ready'
    app.extensions['advanced'].store.path.unlink()
    assert client.get('/api/ready').status_code==503
