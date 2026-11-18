import pytest
pytestmark=[pytest.mark.api,pytest.mark.regression]
def test_effectiveness_is_read_only_saved_evidence(client):
 r=client.get('/api/advanced/effectiveness');assert r.status_code==200;assert r.json.get('kind')=='test_effectiveness' or r.json.get('status')=='not_run';assert client.post('/api/advanced/effectiveness',json={'code':'arbitrary'}).status_code==405
