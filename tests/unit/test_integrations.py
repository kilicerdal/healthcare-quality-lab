from pathlib import Path
import pytest
pytestmark=[pytest.mark.unit,pytest.mark.regression]
from healthcare_quality.integration_scenarios import SCENARIOS,rehearse
from healthcare_quality.integration import Coordinator,IntegrationError

@pytest.mark.parametrize('scenario',SCENARIOS)
def test_actual_peer_boundary_and_reconciliation(scenario):
    result=rehearse(scenario);assert result['passed'],result
    assert result['assertions'] and all(x['passed'] for x in result['assertions'])

@pytest.mark.parametrize('url',['https://example.com','http://localhost:1234','http://127.0.0.1:1234/private','http://user:secret@127.0.0.1:1234','http://127.0.0.1:1234/?target=elsewhere'])
def test_arbitrary_peer_urls_are_rejected(tmp_path,url):
    with pytest.raises(IntegrationError):Coordinator(tmp_path/'coordinator.sqlite',None,url,'demo')


def test_competing_distinct_keys_cannot_create_two_claim_payment_intents(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    from healthcare_quality.benefit_claims import BenefitClaims
    service=BenefitClaims(tmp_path/'benefits.sqlite')
    service.operate('customer-m100',dict(operation_key='submit-race-control',id='RACE-CLAIM',member_id='M100',plan_id='commercial_ppo',service_date='2026-03-01',lines=[dict(id='LINE-1',service='medical',allowed_cents=100000)]),'submit')
    def enqueue(index):
        coordinator=Coordinator(tmp_path/'outbox.sqlite',service,'http://127.0.0.1:9999','demo')
        try:return coordinator.enqueue('finance-demo','RACE-CLAIM','intent-'+str(index).zfill(8))['key']
        except IntegrationError:return None
    with ThreadPoolExecutor(max_workers=4) as pool:results=list(pool.map(enqueue,range(8)))
    assert sum(x is not None for x in results)==1


def test_peer_redirects_are_not_followed():
    from healthcare_quality.integration import NoRedirect
    with pytest.raises(IntegrationError):NoRedirect().redirect_request(None,None,302,None,None,'https://example.com')
