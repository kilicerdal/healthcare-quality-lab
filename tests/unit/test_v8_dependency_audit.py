import pytest
from tools.dependency_audit import audit
pytestmark=[pytest.mark.unit,pytest.mark.regression]
def test_dependency_scan_separates_clean_findings_and_unknown():
 q=[dict(package=dict(name='example',ecosystem='PyPI'),version='1')]
 assert audit(q,lambda _:dict(results=[{}]))['status']=='no_known_findings'
 r=audit(q,lambda _:dict(results=[dict(vulns=[dict(id='EXAMPLE-1')])]))
 assert r['status']=='findings' and r['packages'][0]['vulnerability_ids']==['EXAMPLE-1']
 assert audit(q,lambda _:dict(results=[]))['status']=='unknown'
 def offline(_):raise TimeoutError()
 assert audit(q,offline)['status']=='unknown'
