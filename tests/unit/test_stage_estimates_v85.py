import json
import pytest
from healthcare_quality import lean_expectations as p
from healthcare_quality.experiment_budget_v85 import estimate,request
from tests.unit.test_compact_expectations import BASE
pytestmark=[pytest.mark.unit,pytest.mark.regression]
def sample(phase,seconds,timeout=False):
 s=p.shape(json.loads(p.prompt(p.cohort()['tasks'][0]['plan'])));call=dict(generation=dict(phase=phase,shape=s),phase='provider_error' if timeout else 'response_frozen',timeout_seconds=seconds)
 if timeout:call['error']='TimeoutError'
 else:call['response']={'latency_ms':seconds*1000}
 return dict(protocol={'version':p.VERSION},rows=[dict(model=BASE['models'][0],calls=[call])])
def test_explicit_budget_and_phase_specific_timings():
 with pytest.raises(ValueError):request(BASE)
 r=estimate({**BASE,'max_seconds':100},[sample('pricing',70),sample('lifecycle',20)]);assert r['estimated_seconds']==90 and r['stage_totals']=={'pricing':70,'lifecycle':20} and r['request_budget']==2

def test_timeouts_are_lower_bounds_not_fast_samples_and_old_protocol_is_excluded():
 old=sample('pricing',1);old['protocol']['version']='old'
 r=estimate({**BASE,'max_seconds':100},[sample('pricing',10),sample('pricing',120,True),sample('lifecycle',20),old]);assert r['estimated_seconds']==140 and not r['estimate_fits_budget'];assert r['details'][0]['samples']==1 and r['details'][0]['timeouts']==1

def test_stepwise_review_counts_and_conservative_fallback():
 r=estimate({**BASE,'strategy':'stepwise','self_review':True,'max_seconds':300},[]);assert r['request_budget']==8 and r['estimated_seconds']==120 and len(r['details'])==8
