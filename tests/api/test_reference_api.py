import pytest
from healthcare_quality.app import create_app
from tests.support.ai_fixtures import FixtureProvider,sample_case,generation_request,review_request
pytestmark=[pytest.mark.api,pytest.mark.ai,pytest.mark.regression]
def test_api_reference_block_and_explicit_correction(tmp_path):
    provider=FixtureProvider({'cases':[sample_case(payout=1)]})
    app=create_app({'TESTING':True,'DATABASE':str(tmp_path/'app.sqlite'),'AI_PROVIDER':provider});client=app.test_client()
    parent=client.post('/api/ai/experiments',json=generation_request()).get_json();url='/api/ai/experiments/'+parent['id']
    response=client.post(url+'/review',json=review_request(parent));assert response.status_code==409 and response.get_json()['error']=='REFERENCE_MISMATCH'
    provider.output={'cases':[sample_case()]}
    response=client.post(url+'/correct',json={'expected_revision':1,'reviewer_label':'API fixture reviewer','review_note':'One correction requested explicitly.'})
    assert response.status_code==201
    child=response.get_json();assert child['correction_of']==parent['id'] and child['approval'] is None
    assert client.get(url).get_json()['raw_generation']==parent['raw_generation']
    assert child['proposals'][0]['reference']['status']=='matched'
