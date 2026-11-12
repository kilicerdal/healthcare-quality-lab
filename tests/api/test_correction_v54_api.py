import pytest
from healthcare_quality.app import create_app
from tests.support.ai_fixtures import FixtureProvider,sample_case,generation_request
from tests.unit.test_reference import correction_body
from tests.unit.test_correction_v54 import fallback_body
pytestmark=[pytest.mark.api,pytest.mark.ai,pytest.mark.regression]
def test_api_budget_and_confirmed_reference_child(tmp_path):
    provider=FixtureProvider({'cases':[sample_case(amount=10001,payout=9001)]})
    app=create_app({'TESTING':True,'DATABASE':str(tmp_path/'app.sqlite'),'AI_PROVIDER':provider});client=app.test_client()
    parent=client.post('/api/ai/experiments',json=generation_request()).get_json();current=parent
    for _ in range(2):
        response=client.post('/api/ai/experiments/'+current['id']+'/correct',json=correction_body(current));assert response.status_code==201;current=response.get_json()
    url='/api/ai/experiments/'+current['id']
    assert client.get(url).get_json()['correction_budget']['remaining']==0
    assert client.post(url+'/correct',json=correction_body(current)).get_json()['error']=='CORRECTION_LIMIT'
    preview=client.get(url+'/reference-preview').get_json();assert preview['changes'][0]['after']['payout_cents']==1
    body=fallback_body(preview);body['reference_confirmed']=False
    assert client.post(url+'/apply-reference',json=body).status_code==409
    body['reference_confirmed']=True;response=client.post(url+'/apply-reference',json=body);assert response.status_code==201
    child=response.get_json();assert child['expectation_origin']=='reviewer_confirmed_reference' and child['approval'] is None
    assert child['proposals'][0]['case']['steps'][0]['expect']['payout_cents']==1 and len(provider.calls)==3
    assert client.post('/api/ai/experiments/'+child['id']+'/execute',json={'expected_revision':1}).status_code==409
