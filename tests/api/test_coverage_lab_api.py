import pytest
from tests.support.ai_fixtures import FixtureProvider,sample_case,generation_request,review_request
from tests.unit.test_coverage_lab import suggestions
pytestmark=[pytest.mark.api,pytest.mark.ai,pytest.mark.regression]
def test_dashboard_is_read_only_and_scoring_requires_review(app):
    studio=app.extensions['studio'];studio.provider=FixtureProvider();client=app.test_client()
    r=client.get('/api/coverage/dashboard');assert r.status_code==200 and r.json['counts']['authored']==32 and not studio.provider.calls
    record=studio.generate(generation_request());body={'experiments':[{'id':record['id'],'expected_revision':1}]}
    assert client.post('/api/coverage/score',json=body).status_code==409
    reviewed=studio.review(record['id'],review_request(record));body['experiments'][0]['expected_revision']=reviewed['revision']
    score=client.post('/api/coverage/score',json=body);assert score.status_code==201 and score.json['state']=='scored'
    evidence=client.get('/api/coverage/records/'+score.json['id']).json;assert evidence['matches_current_implementation'] and evidence['approval_snapshots_current']

def test_gap_suggestion_to_unapproved_proposal(app):
    studio=app.extensions['studio'];studio.provider=FixtureProvider(suggestions());client=app.test_client()
    analysis=client.post('/api/coverage/analyze',json={'model':'qwen2.5-coder:3b'});assert analysis.status_code==201
    studio.provider.output={'cases':[sample_case()]}
    proposal=client.post('/api/coverage/analyses/'+analysis.json['id']+'/propose',json={'suggestion_index':0})
    assert proposal.status_code==201 and proposal.json['approval'] is None
    assert client.get('/api/coverage/records').json['records']

@pytest.mark.parametrize('path,body',[('analyze',{'model':'cloud'}),('score',{}),('score',{'experiments':[]})])
def test_rejected_public_inputs(client,path,body):assert client.post('/api/coverage/'+path,json=body).status_code==400


def test_readiness_checks_coverage_store(client,app):
    assert client.get('/api/ready').json['storage']['coverage']=='ready'
    with app.extensions['coverage_lab'].store.transaction() as db:db.execute('DROP TABLE ai_experiments')
    assert client.get('/api/ready').status_code==503


def test_focused_api_config_and_generation(app):
    from tests.unit.test_focused_v57 import output
    client=app.test_client();studio=app.extensions['studio'];studio.provider=FixtureProvider(output())
    assert 'commercial_ppo' in client.get('/api/ai/focused-evaluator/config').json['plans']
    r=client.post('/api/ai/focused-evaluator',json={'data':output()['cases'][0]['steps'][0]['data'],'model':'qwen2.5-coder:3b'})
    assert r.status_code==201 and r.json['focused_validation']['status']=='matched'
    assert r.json['approval'] is None
    assert client.post('/api/coverage/assemble-evaluators',json={}).status_code==400

@pytest.mark.parametrize('id',['invented','invalid-zero','payment-replay'])
def test_gap_generation_rejects_unknown_model(client,id):
    assert client.post('/api/coverage/gaps/'+id+'/generate',json={'model':'cloud'}).status_code==400
