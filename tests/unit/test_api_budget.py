import json
from concurrent.futures import ThreadPoolExecutor
import pytest
from healthcare_quality.api_budget import Budget, BudgetError
from healthcare_quality.openai_provider import OpenAIProvider
pytestmark = [pytest.mark.unit, pytest.mark.regression, pytest.mark.ai]

def test_cap_survives_restart_and_cannot_be_raised(tmp_path):
    path=tmp_path/'budget.sqlite'; b=Budget(path, '.05')
    key=b.reserve(b'{}'); b.complete(key, {'input_tokens':100,'output_tokens':10})
    assert Budget(path,'15').summary()['cap_usd']=='0.05'
    with pytest.raises(BudgetError): Budget(path,'15').reserve(b'{}')

def test_uncertain_request_blocks_spend_across_process_instances(tmp_path):
    p=tmp_path/'budget.sqlite'; b=Budget(p); key=b.reserve(b'{}'); b.uncertain(key)
    with pytest.raises(BudgetError):Budget(p).reserve(b'{}')
    assert b.summary()['unresolved']==1

def test_concurrent_reservations_cannot_double_spend(tmp_path):
    b=Budget(tmp_path/'budget.sqlite')
    def reserve(_):
        try:return b.reserve(b'{}')
        except BudgetError:return None
    with ThreadPoolExecutor(2) as pool:ids=list(pool.map(reserve,range(2)))
    assert len([i for i in ids if i])==1

@pytest.mark.parametrize('limit',['0','15.01','NaN','Infinity','-1'])
def test_invalid_caps_rejected(tmp_path,limit):
    with pytest.raises(BudgetError):Budget(tmp_path/'budget.sqlite',limit)

def test_missing_usage_retains_reservation_and_stops(tmp_path):
    b=Budget(tmp_path/'budget.sqlite');key=b.reserve(b'{}')
    with pytest.raises(BudgetError):b.complete(key,{})
    assert b.summary()['unresolved']==1

def test_provider_never_retries_or_exposes_key(tmp_path):
    calls=[]
    def fail(*args,**kwargs):calls.append(1);raise OSError('sensitive provider internals')
    b=Budget(tmp_path/'budget.sqlite');p=OpenAIProvider('not-a-real-key',b,transport=fail)
    with pytest.raises(BudgetError) as e:p.generate('Synthetic prompt',{'type':'object'})
    assert len(calls)==1 and 'not-a-real-key' not in str(e.value) and 'sensitive' not in str(e.value)
    assert b.summary()['unresolved']==1
