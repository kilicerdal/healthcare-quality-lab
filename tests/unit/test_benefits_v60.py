from copy import deepcopy
import random,sqlite3
import pytest
from healthcare_quality.benefits import calculate,policy_for
from healthcare_quality.benefit_reference import price
from healthcare_quality.benefit_claims import BenefitClaims
from healthcare_quality.workflow import WorkflowError
pytestmark=[pytest.mark.unit,pytest.mark.regression]
def line(amount=100000,**change):return dict(id='L1',service='medical',allowed_cents=amount,**change)
def submit(s,id='BEN-100',member='M100',**change):return s.operate('customer-'+member.lower(),dict(operation_key='submit-'+id,id=id,member_id=member,plan_id='commercial_ppo',service_date='2026-03-01',lines=[line()],**change),'submit')
def action(s,r,kind,key=None,**extra):return s.operate('finance-demo' if kind in ('pay','reverse') else 'adjuster-demo',dict(operation_key=key or kind+'-operation',expected_revision=r['revision'],**extra),kind,r['id'])
@pytest.mark.parametrize('day,expected',[('2026-03-01',71200),('2026-07-01',70800),('2027-01-01',68000)])
def test_effective_policies_literal(day,expected):assert calculate(policy_for(day,'commercial_ppo'),[line()])['totals']['payout_cents']==expected
def test_cob_partial_and_money_conservation():
    c=calculate(policy_for('2026-03-01','commercial_ppo'),[line(other_payer_cents=50000),dict(id='L2',service='dental',allowed_cents=5000)])
    assert c['partial'] and c['totals']['payout_cents']==31200 and c['totals']['member_cents']==18800 and c['totals']['noncovered_cents']==5000
    assert sum(c['totals'][k] for k in ('other_payer_cents','member_cents','payout_cents','noncovered_cents'))==105000
@pytest.mark.parametrize('bad',[True,0,-1,1.5,'100'])
def test_invalid_money(bad):
    with pytest.raises(WorkflowError):calculate(policy_for('2026-03-01','commercial_ppo'),[line(bad)])
def test_random_properties_against_independent_fraction_reference():
    rng=random.Random(602)
    for _ in range(500):
        amount=rng.randint(1,1000000);other=rng.randint(0,amount);i=dict(deductible=rng.randint(0,10000),oop=rng.randint(0,30000),benefit=rng.randint(0,200000));f={k:v*2 for k,v in i.items()};p=policy_for('2026-03-01','commercial_ppo');lines=[line(amount,other_payer_cents=other)];actual=calculate(p,lines,i,f);expected=price('2026-03-01','commercial_ppo',lines,i,f)
        for k in ('payout_cents','member_cents','other_payer_cents','noncovered_cents'):assert actual['totals'][k]==expected[k]
        assert sum(actual['totals'][k] for k in ('payout_cents','member_cents','other_payer_cents','noncovered_cents'))==amount
        assert actual['individual']==expected['individual'];assert actual['individual']['oop']<=30000 and actual['individual']['benefit']<=200000

def test_pay_adjust_reverse_and_idempotency(tmp_path):
    s=BenefitClaims(tmp_path/'b.sqlite');r=submit(s);r=action(s,r,'pay');assert sum(x['amount'] for x in r['ledger'])==71200
    assert action(s,dict(r,revision=1),'pay')==r
    with pytest.raises(WorkflowError):action(s,r,'pay',key='second-pay')
    r=action(s,r,'adjust',lines=[line(50000)],note='Correct allowed amount');assert sum(x['amount'] for x in r['ledger'])==31200 and r['revision']==3
    r=action(s,r,'reverse',note='Reverse corrected payment');assert sum(x['amount'] for x in r['ledger'])==0 and r['current_member_accumulators']==dict(deductible=0,oop=0,benefit=0)

def test_individual_family_and_year_reset(tmp_path):
    s=BenefitClaims(tmp_path/'b.sqlite');a=submit(s);b=submit(s,'BEN-200','M200');assert b['current_family_accumulators']['deductible']==20000
    c=submit(s,'BEN-300');assert c['calculation']['totals']['member_cents']==1200
    newer=s.operate('customer-m100',dict(operation_key='next-year',id='BEN-2027',member_id='M100',plan_id='commercial_ppo',service_date='2027-01-02',lines=[line()]),'submit');assert newer['calculation']['totals']['payout_cents']==68000

def test_failed_adjustment_rolls_back_ledger_and_accumulators(tmp_path):
    s=BenefitClaims(tmp_path/'b.sqlite');r=action(s,submit(s),'pay');before=s.get('auditor-demo',r['id'])
    with pytest.raises(WorkflowError):action(s,r,'adjust',lines=[line(-1)],note='Invalid amount')
    assert s.get('auditor-demo',r['id'])==before

def test_appeal_resolution_and_ownership(tmp_path):
    s=BenefitClaims(tmp_path/'b.sqlite');r=submit(s)
    with pytest.raises(WorkflowError):s.get('customer-m200',r['id'])
    r=s.operate('customer-m100',dict(operation_key='appeal-100',expected_revision=1,note='Correct service information'),'appeal',r['id']);r=action(s,r,'resolve',lines=[line(50000)],note='Reprocess corrected lines');assert r['state']=='adjudicated' and r['calculation']['totals']['payout_cents']==31200


def test_family_cap_binds_for_third_member_before_individual_deductible(tmp_path):
    s=BenefitClaims(tmp_path/'b.sqlite');submit(s,'FAM-100','M100');submit(s,'FAM-200','M200');r=submit(s,'FAM-300','M300')
    assert r['calculation']['allocation']['deductible']==0
    assert r['current_family_accumulators']['deductible']==20000 and r['current_family_accumulators']['oop']==60000
