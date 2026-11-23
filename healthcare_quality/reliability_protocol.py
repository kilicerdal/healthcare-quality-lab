"""V8.7 input-only reliability cohort; unchanged V8.6 model instructions/schema."""
from copy import deepcopy
from healthcare_quality.deductible_expectations import *
VERSION='reliability-study-v87-1'
KIND='model_expectations_v87'

def step(action,claim,number,member='M100',**values):
 actor={'submit':'customer-'+member.lower(),'read':'customer-'+member.lower(),'pay':'finance-demo','reverse':'finance-demo','adjust':'adjuster-demo','appeal':'customer-'+member.lower(),'resolve':'adjuster-demo'}[action]
 data=dict(claim_id=claim,**values)
 if action!='read':data['operation_key']=claim+'-'+action+'-'+str(number)
 if action in ('adjust','reverse','appeal','resolve'):data['note']='Synthetic stateful reliability study'
 return dict(action=action,actor=actor,data=data)

def line(amount,service='medical',**extra):return dict(id='LINE-ONE',service=service,allowed_cents=amount,**extra)
def task(id,title,steps):
 return dict(id=id,split='reserved_until_exposed',plan=dict(objective='Predict complete synthetic observations without feedback',risk='financial',case=dict(id='AB-'+id,title=title,rule_ids=['BN-'+str(n).zfill(3) for n in range(1,8)],rationale='Sealed input-only boundary and lifecycle assessment; model authors all expectations.',assumptions=[],steps=steps)))

def cohort():
 tasks=[]
 def submit(id,amount,plan='commercial_ppo',service='medical',day='2026-03-19',**extra):
  return step('submit','CLAIM-'+id,1,member_id='M100',plan_id=plan,service_date=day,lines=[line(amount,service,**extra)])
 def finish(id,s):return [s,step('pay',s['data']['claim_id'],2,expected_revision=1),step('read',s['data']['claim_id'],3)]
 specs=[('R87-01','Deductible just below',9997,{}),('R87-02','Deductible just above',10007,{}),('R87-03','Hospital authorization and floor',71937,dict(plan='medicare_advantage',service='hospital',authorized=True)),('R87-04','OOP cap',194213,{}),('R87-05','Annual benefit cap',287651,{}),('R87-06','Other payer first',61739,dict(other_payer_cents=8137)),('R87-07','Half-open July policy',63271,dict(day='2026-07-01')),('R87-08','Prescription formulary rejection',15113,dict(plan='medicare_d',service='prescription',formulary=False))]
 for id,title,amount,kwargs in specs:tasks.append(task(id,title,finish(id,submit(id,amount,**kwargs))))
 id='R87-09';s=submit(id,62417);s['data']['lines'].append(dict(id='LINE-TWO',service='dental',allowed_cents=8513));tasks.append(task(id,'Mixed covered and rejected lines',finish(id,s)))
 id='R87-10';steps=[]
 for n,(member,amount) in enumerate([('M100',10003),('M200',10009),('M300',47123)]):
  claim='CLAIM-'+id+'-'+str(n)
  steps.append(step('submit',claim,n,member=member,member_id=member,plan_id='commercial_ppo',service_date='2026-03-19',lines=[line(amount)]))
 steps.append(step('read','CLAIM-'+id+'-0',4));tasks.append(task(id,'Shared family deductible across three members',steps))
 id='R87-11';s=submit(id,77431);claim=s['data']['claim_id'];steps=finish(id,s)[:2]+[step('adjust',claim,3,expected_revision=2,lines=[line(53213)]),step('reverse',claim,4,expected_revision=3),step('read',claim,5)];tasks.append(task(id,'Paid adjustment then reversal restores original allocation',steps))
 id='R87-12';s=submit(id,51113,plan='commercial_hmo',in_network=False);claim=s['data']['claim_id'];steps=[s,step('appeal',claim,2,expected_revision=1),step('resolve',claim,3,expected_revision=2,lines=[line(51113,in_network=True)]),step('pay',claim,4,expected_revision=3),step('read',claim,5)];tasks.append(task(id,'Appeal resolution corrects network facts',steps))
 return dict(version=VERSION,request_multiplier=2,target=dict(first_attempt_percent=80,minimum_unique_fresh=10),tasks=tasks)
