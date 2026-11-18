import pytest
pytestmark=[pytest.mark.api,pytest.mark.regression]
def test_portfolio_labels_history_and_never_fakes_current_verification(client):
 r=client.get('/api/advanced/portfolio');assert r.status_code==200 and len(r.json['reports'])==6;assert r.json['verification']['status'] in ('stale','passed','not_run');assert all(x['historical'] for x in r.json['historical_model_comparison'])
def test_guided_control_does_not_approve_or_execute(client):
 r=client.post('/api/advanced/portfolio/control',json={});assert r.status_code==201 and r.json['approval'] is None and not r.json['runs'];assert r.json['provenance']['live_inference'] is False;assert client.post('/api/advanced/'+r.json['id']+'/execute',json={'transport':'http'}).status_code==409
@pytest.mark.parametrize('version',['6.8','6.9','6.10','6.11','6.12','7.0'])
def test_each_requested_version_has_a_detailed_report(client,version):
 r=client.get('/reports/v'+version);assert r.status_code==200 and ('V'+version+' Engineering Report').encode() in r.data

@pytest.mark.parametrize('store',['designs','advanced_investigations','traceability','experiments'])
def test_readiness_detects_missing_new_persistence(client,app,store):
    assert client.get('/api/ready').status_code==200;s=app.extensions[store];getattr(s,'store',s).path.unlink();assert client.get('/api/ready').status_code==503
