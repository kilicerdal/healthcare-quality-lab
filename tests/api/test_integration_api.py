import pytest
pytestmark=[pytest.mark.api,pytest.mark.regression]
def test_isolated_integration_receipt_and_no_existing_financial_writes(client,app):
    original=client.get('/api/claims',headers={'X-Demo-Actor':'auditor-demo'}).json
    r=client.post('/api/integrations/rehearse',json={'scenario':'lost_ack'})
    assert r.status_code==201 and r.json['passed'] and r.json['remote_payments']==1
    assert client.get('/api/integrations').json['records'][0]['id']==r.json['id']
    assert client.get('/api/claims',headers={'X-Demo-Actor':'auditor-demo'}).json==original
    assert client.post('/api/integrations/rehearse',json={'scenario':'arbitrary_url'}).status_code==400
    assert client.get('/api/advanced/evaluations').json=={'records':[]}
