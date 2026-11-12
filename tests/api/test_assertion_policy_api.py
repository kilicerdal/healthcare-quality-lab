import pytest
from tests.support.ai_fixtures import FixtureProvider,sample_case,generation_request,review_request
pytestmark=[pytest.mark.api,pytest.mark.ai,pytest.mark.regression]

def test_api_distinguishes_structure_from_completeness_and_blocks_approval(client,app):
    case=sample_case();del case['steps'][0]['expect']['payout_cents'];app.extensions['studio'].provider=FixtureProvider({'cases':[case]})
    record=client.post('/api/ai/experiments',json=generation_request()).json;p=record['proposals'][0]
    assert p['valid'] and not p['review_ready'] and p['quality']['steps'][0]['missing_fields']==['payout_cents']
    response=client.post('/api/ai/experiments/'+record['id']+'/review',json=review_request(record))
    assert response.status_code==409 and response.json['error']=='INCOMPLETE_ASSERTIONS'
    assert client.get('/api/ai/config').json['assertion_policy_fingerprint']


def test_selection_of_complete_case_is_not_blocked_by_unselected_incomplete_case(client,app):
    first=sample_case();second=sample_case('AI-INCOMPLETE',20000,10000);del second['steps'][0]['expect']['payout_cents'];app.extensions['studio'].provider=FixtureProvider({'cases':[first,second]})
    record=client.post('/api/ai/experiments',json=generation_request(2)).json
    reviewed=client.post('/api/ai/experiments/'+record['id']+'/review',json=review_request(record,[first['id']]))
    assert reviewed.status_code==200 and reviewed.json['approval']['assertion_policy_fingerprint']
    run=client.post('/api/ai/experiments/'+record['id']+'/execute',json={'expected_revision':reviewed.json['revision']})
    assert run.status_code==200 and run.json['passed']==1
