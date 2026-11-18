import pytest
pytestmark=[pytest.mark.api,pytest.mark.regression]
def test_experiment_metadata_and_invalid_requests_never_start_model(client):
 r=client.get('/api/advanced/experiments');assert r.status_code==200 and len(r.json['tasks'])==8 and not r.json['records'];assert client.post('/api/advanced/experiments',json={}).status_code==400
