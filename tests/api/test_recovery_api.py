import pytest
from tests.support.ai_fixtures import FixtureProvider,generation_request,review_request
pytestmark=[pytest.mark.api,pytest.mark.ai,pytest.mark.regression]

def interrupted(app,kind='generation'):
    studio=app.extensions['studio'];studio.provider=FixtureProvider();record=studio.generate(generation_request())
    if kind=='execution':record=studio.review(record['id'],review_request(record))
    with studio.store.transaction() as db:record['state']='generating' if kind=='generation' else 'running';studio.store.save(db,record)
    return record


def test_get_recovers_interruption_and_retry_is_new_unapproved_child(client,app):
    original=interrupted(app);parent=client.get('/api/ai/experiments/'+original['id']).json
    assert parent['state']=='interrupted'
    body={'expected_revision':parent['revision'],'reviewer_label':'API recovery operator','review_note':'Explicit generation retry after interruption'}
    response=client.post('/api/ai/experiments/'+parent['id']+'/retry',json=body)
    assert response.status_code==201 and response.json['retry_of']==parent['id']
    assert response.json['approval'] is None and response.json['runs']==[]
    assert client.post('/api/ai/experiments/'+parent['id']+'/retry',json=body).status_code==409


def test_interrupted_execution_requires_review_and_cannot_use_generation_retry(client,app):
    record=interrupted(app,'execution');record=client.get('/api/ai/experiments/'+record['id']).json
    assert record['approved_ids']==[]
    response=client.post('/api/ai/experiments/'+record['id']+'/execute',json={'expected_revision':record['revision']})
    assert response.status_code==409 and response.json['error']=='REVIEW_REQUIRED'
    response=client.post('/api/ai/experiments/'+record['id']+'/retry',json={'expected_revision':record['revision'],'reviewer_label':'API operator','review_note':'Cannot retry execution through generation'})
    assert response.status_code==400 and response.json['error']=='INVALID_STATE'


def test_retrieval_api_exact_and_unknown_id_behavior(client):
    assert [r['rule_id'] for r in client.get('/api/quality/retrieval?q=HC-007').json['results']]==['HC-007']
    assert client.get('/api/quality/retrieval?q=HC-999').json['results']==[]
