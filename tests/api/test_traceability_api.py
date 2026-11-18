import pytest
from tests.unit.test_advanced_cases import CASES
pytestmark=[pytest.mark.api,pytest.mark.regression]
def test_empty_trace_is_not_complete_coverage(client):
    g=client.get('/api/advanced/traceability').json;assert len(g['requirements'])==7 and not g['scenarios'];assert all(x['current_passing_scenarios']==0 for x in g['coverage'])
def test_impact_snapshot_does_not_edit_cases(client):
    p=client.post('/api/advanced/import',json={'cases':CASES[:1]}).json;s=client.post('/api/advanced/traceability/snapshots',json={}).json;r=client.post('/api/advanced/traceability/impact',json={'snapshot_id':s['id'],'changes':[{'id':'BN-004','contract':'Proposed changed cost sharing contract'}]});assert r.status_code==200 and len(r.json['affected_scenarios'])==1 and not r.json['applied'];assert client.get('/api/advanced/'+p['id']).json['approval'] is None

@pytest.mark.parametrize('changes',[[],[{'id':[],'contract':'A changed contract'}],[{'id':'BN-004','contract':True}]])
def test_invalid_impact_is_client_error(client,changes):
    s=client.post('/api/advanced/traceability/snapshots',json={}).json;r=client.post('/api/advanced/traceability/impact',json={'snapshot_id':s['id'],'changes':changes});assert r.status_code==400
