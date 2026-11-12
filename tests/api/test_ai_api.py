import json
import pytest
from tests.support.ai_fixtures import FixtureProvider,generation_request,review_request
pytestmark=[pytest.mark.api,pytest.mark.ai,pytest.mark.regression]

@pytest.fixture
def ai(client,app):
    app.extensions['studio'].provider=FixtureProvider()
    return client


def create(ai):
    response=ai.post('/api/ai/experiments',json=generation_request())
    assert response.status_code==201
    return response.json


def test_studio_config_and_provider_are_explicit(ai):
    data=ai.get('/api/ai/config').json
    assert 'qwen2.5-coder:3b' in data['models'] and len(data['rules'])==13
    assert ai.get('/api/ai/provider').json['mode']=='offline test double'


@pytest.mark.smoke
def test_http_generation_review_execute_and_export(ai):
    record=create(ai)
    assert ai.post('/api/ai/experiments/'+record['id']+'/execute',json={'expected_revision':1}).status_code==409
    approved=ai.post('/api/ai/experiments/'+record['id']+'/review',json=review_request(record)).json
    run=ai.post('/api/ai/experiments/'+record['id']+'/execute',json={'expected_revision':approved['revision']})
    assert run.status_code==200 and run.json['status']=='passed'
    exported=ai.get('/api/ai/experiments/'+record['id']+'/evidence').json
    assert exported['raw_generation'] and len(exported['runs'])==1
    assert ai.get('/api/ai/experiments').json['experiments'][0]['id']==record['id']


@pytest.mark.sanity
def test_http_review_requires_attestation(ai):
    record=create(ai)
    response=ai.post('/api/ai/experiments/'+record['id']+'/review',json={**review_request(record),'expectations_checked':False})
    assert response.status_code==409 and response.json['error']=='REVIEW_REQUIRED'


def test_ai_execution_does_not_change_interactive_claim_store(ai,app):
    record=create(ai);approved=ai.post('/api/ai/experiments/'+record['id']+'/review',json=review_request(record)).json
    ai.post('/api/ai/experiments/'+record['id']+'/execute',json={'expected_revision':approved['revision']})
    assert app.extensions['workflow'].list('auditor-demo')['claims']==[]
    assert app.extensions['studio'].store.path!=app.extensions['workflow'].store.path


@pytest.mark.parametrize('payload',[None,{},[],{**generation_request(),'endpoint':'https://external.example'},{**generation_request(),'model':'some-cloud-model'}])
def test_invalid_generation_request_returns_400_without_model_call(ai,app,payload):
    response=ai.post('/api/ai/experiments',data=json.dumps(payload),content_type='application/json')
    assert response.status_code==400
    assert app.extensions['studio'].provider.calls==[]


def test_failed_model_response_is_saved_without_fake_success(ai,app):
    app.extensions['studio'].provider=FixtureProvider('bad JSON')
    record=create(ai)
    assert record['state']=='generation_failed' and record['generation_error']
    assert record['proposals']==[]


def test_unknown_experiment_and_overposted_execution_fields(ai):
    assert ai.get('/api/ai/experiments/missing').status_code==404
    record=create(ai)
    response=ai.post('/api/ai/experiments/'+record['id']+'/execute',json={'expected_revision':1,'python':'print(1)'})
    assert response.status_code==400


def test_historic_v2_report_stays_available(ai):
    response=ai.get('/reports/v2')
    assert response.status_code==200 and b'Healthcare Quality Lab V2 Engineering Report' in response.data
