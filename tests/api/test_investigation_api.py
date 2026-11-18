import pytest
pytestmark=[pytest.mark.api,pytest.mark.regression]
def test_investigation_reads_and_invalid_requests_make_no_inference(client):
    assert client.get('/api/advanced/investigations').json['records']==[];assert client.post('/api/advanced/investigations',json={}).status_code==400;assert client.post('/api/advanced/investigations/rehearse',json={'arbitrary_fault':'code'}).status_code==400

def test_isolated_known_defect_rehearsal_saved(client):
    r=client.post('/api/advanced/investigations/rehearse',json={});assert r.status_code==201 and r.json['passed'];assert r.json['analysis']['facts'];assert client.get('/api/advanced/investigations/'+r.json['id']).json['restored']['failed']==0

def test_explanation_provider_failure_is_persisted_and_not_silently_retried(client,monkeypatch):
    import healthcare_quality.investigation_api as module
    calls=[]
    class Broken:
        def __init__(self,*args):pass
        def generate(self,*args):calls.append(1);raise TimeoutError('offline fixture')
    monkeypatch.setattr(module,'OllamaProvider',Broken);r=client.post('/api/advanced/investigations/rehearse',json={}).json;path='/api/advanced/investigations/'+r['id']+'/explain';result=client.post(path,json={'model':'qwen2.5-coder:3b'});assert result.status_code==200 and result.json['ai_attempt']['state']=='failed' and not result.json['ai']['accepted'];assert client.post(path,json={'model':'qwen2.5-coder:3b'}).status_code==409 and len(calls)==1

@pytest.mark.parametrize('id',[None,[],{},123])
def test_investigation_identifiers_are_bounded_strings(client,id):assert client.post('/api/advanced/investigations',json={'proposal_id':id,'run_id':'valid'}).status_code==400
