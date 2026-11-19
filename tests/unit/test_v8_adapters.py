import pytest
from healthcare_quality.coverage_packs import plan_for
from healthcare_quality.test_design import compile_plan
from healthcare_quality.system_adapters import execute,reference_peer
import urllib.request,urllib.error,json
pytestmark=[pytest.mark.unit,pytest.mark.regression]

def test_reference_peer_contract_and_replay():
 p=plan_for('commercial_ppo');p['case']['steps'].extend([p['case']['steps'][1],p['case']['steps'][2]])
 c=compile_plan(p);r=execute([c],'reference_peer');assert r['passed']==1 and not r['failed']
 c['steps'][-1]['expect']['ledger_count']+=1;assert execute([c],'reference_peer')['failed']==1
 with pytest.raises(ValueError):execute([c],'http://malicious.example')

def test_reference_peer_rejects_untrusted_step():
 with reference_peer() as url:
  req=urllib.request.Request(url+'/contract/v1/step',data=json.dumps({'action':'shell','command':'whoami'}).encode(),headers={'Content-Type':'application/json'})
  with pytest.raises(urllib.error.HTTPError) as e:urllib.request.urlopen(req)
  assert e.value.code==400
