import pytest
pytestmark=[pytest.mark.api,pytest.mark.regression]
def test_investigation_reads_and_invalid_requests_make_no_inference(client):
    assert client.get('/api/advanced/investigations').json['records']==[];assert client.post('/api/advanced/investigations',json={}).status_code==400;assert client.post('/api/advanced/investigations/rehearse',json={'arbitrary_fault':'code'}).status_code==400

def test_isolated_known_defect_rehearsal_saved(client):
    r=client.post('/api/advanced/investigations/rehearse',json={});assert r.status_code==201 and r.json['passed'];assert r.json['analysis']['facts'];assert client.get('/api/advanced/investigations/'+r.json['id']).json['restored']['failed']==0
