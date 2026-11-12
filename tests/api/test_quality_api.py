import pytest
from healthcare_quality.app import create_app
from tests.support.ai_fixtures import FixtureProvider
pytestmark=[pytest.mark.api,pytest.mark.ai,pytest.mark.regression]

def test_dataset_and_retrieval_are_inspectable(client):
    response=client.get('/api/quality/dataset');assert response.status_code==200 and len(response.json['tasks'])==8
    assert client.get('/api/quality/retrieval?q=WF-004').json['results'][0]['rule_id']=='WF-004'
    assert client.get('/api/quality/retrieval?q=xyzzyquux').json['results']==[]
    assert client.get('/api/quality/retrieval').status_code==400

def test_unknown_evidence_and_invalid_posts(client):
    assert client.get('/api/quality/records/missing').status_code==404
    assert client.post('/api/quality/comparisons',json={}).status_code==400
    assert client.post('/api/quality/investigations',json={}).status_code==400
    assert client.post('/api/quality/comparisons',data='{}').status_code==415

def test_post_starts_persisted_job_with_offline_provider(tmp_path):
    import time
    app=create_app({'TESTING':True,'DATABASE':str(tmp_path/'api.sqlite'),'AI_PROVIDER':FixtureProvider()});client=app.test_client()
    response=client.post('/api/quality/comparisons',json={'split':'development','model':'qwen2.5:3b','task_ids':['D01']})
    assert response.status_code==202
    id=response.json['id']
    for _ in range(100):
        record=client.get('/api/quality/records/'+id).json
        if record['state'] not in ('queued','running'):break
        time.sleep(.01)
    assert record['state']=='completed' and len(record['results'])==2
    assert client.get('/api/quality/records').json['records'][0]['id']==id
