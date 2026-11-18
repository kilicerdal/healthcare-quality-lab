import json
from copy import deepcopy
import pytest
from healthcare_quality.evidence_investigator import seal,inspect,explain,rehearsal
from healthcare_quality.advanced_runner import run
from healthcare_quality.ai_schema import digest
from tests.unit.test_advanced_cases import CASES
pytestmark=[pytest.mark.unit,pytest.mark.regression]

def test_real_seed_detected_and_original_function_restored():
    r=rehearsal('service');assert r['passed'] and r['restored']['failed']==0;assert r['analysis']['findings'][0]['category']=='potential_application_fault';assert r['analysis']['facts'][0]['observed']==71201

def test_harness_injection_is_not_application_root_cause():
    b=seal(CASES[:1],run(CASES[:1],fault='payout_cents'));assert inspect(b)['findings'][0]['category']=='harness_injection'

def test_wrong_expectations_are_classified_separately():
    c=deepcopy(CASES[0]);c['steps'][0]['expect']['payout_cents']+=1;b=seal([c],run([c]));assert inspect(b)['findings'][0]['category']=='expected_value_error'

def test_tampered_bundle_rejected():
    b=seal(CASES[:1],run(CASES[:1]));b['execution']['passed']=99
    with pytest.raises(ValueError,match='integrity'):inspect(b)

def test_stale_bundle_abstains():
    b=seal(CASES[:1],run(CASES[:1]));b['source_hash']='old';b['content_hash']=digest({k:v for k,v in b.items() if k!='content_hash'});assert inspect(b)['findings'][0]['category']=='stale_evidence'

def test_http_captures_request_response_and_request_id():
    r=run(CASES[:1],'http');s=r['results'][0]['steps'][0];assert s['request']['actor']=='customer-m100' and s['response']['calculation']['totals']['payout_cents']==71200 and len(s['request_id'])==32

@pytest.mark.parametrize('citation,accepted',[('F1',True),('F999',False)])
def test_hallucinated_evidence_citations_are_rejected(citation,accepted):
    a=inspect(seal(CASES[:1],run(CASES[:1],fault='payout_cents')))
    class Provider:
        def generate(self,*args):return {'text':json.dumps({'hypotheses':[{'category':'harness_injection','statement':'The observation was deliberately changed in the harness.','evidence_ids':[citation]}],'uncertainty':'This is a bounded control, not proof of a real product defect.'})}
    assert explain(Provider(),'qwen2.5-coder:3b',a)['accepted']==accepted
