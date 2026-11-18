import pytest
pytestmark=[pytest.mark.api,pytest.mark.regression]

def test_design_listing_and_invalid_request_do_not_call_models(client):
    r=client.get('/api/advanced/designs');assert r.status_code==200 and r.json['records']==[];assert len(r.json['modes'])==2
    assert client.post('/api/advanced/designs/generate',json={}).status_code==400

def test_failed_design_cannot_export(client,app):
    lab=app.extensions['designs'];r={'id':'blocked','created_at':'2026-11-18','state':'failed','assessment':None};lab.store.create(r);assert client.post('/api/advanced/designs/blocked/export',json={}).status_code==409
