"""Versioned synthetic coverage packs; shared cost model, distinct service/network rules."""
from copy import deepcopy
from healthcare_quality.advanced_schema import PLAN_FACTS
from healthcare_quality.test_design import compile_plan

def plan_for(plan_id,variant='covered',number=1):
 p=next(p for p in PLAN_FACTS if p['id']==plan_id)
 service=p['services'][0];claim=f'PACK-{number}-{variant}'
 line=dict(id='LINE-ONE',service=service,allowed_cents=97003,in_network=True,authorized=True,formulary=True)
 if variant=='noncovered':line['service']='vision' if 'vision' not in p['services'] else 'skilled_nursing'
 elif variant=='network':line['in_network']=False
 elif variant=='authorization':line['service']=p['authorization_services'][0];line['authorized']=False
 elif variant=='formulary':line['service']='prescription';line['formulary']=False
 elif variant=='deductible':line['allowed_cents']=5003
 steps=[dict(action='submit',actor='customer-m100',data=dict(claim_id=claim,operation_key=f'submit-{claim}',member_id='M100',plan_id=plan_id,service_date='2026-03-01',lines=[line])),dict(action='pay',actor='finance-demo',data=dict(claim_id=claim,operation_key=f'payment-{claim}',expected_revision=1)),dict(action='read',actor='customer-m100',data=dict(claim_id=claim))]
 return dict(objective='Verify synthetic '+p['name']+' '+variant+' lifecycle and all financial observations',risk='financial',case=dict(id=f'AB-{claim}',title=p['name']+' '+variant,rule_ids=['BN-001','BN-002','BN-003','BN-004','BN-005','BN-006'],rationale='Authored teaching coverage boundary with independent calculator expectations; not an actual insurance policy.',assumptions=[],steps=steps))
def packs():
 result=[]
 for i,p in enumerate(PLAN_FACTS,1):
  variants=['covered','noncovered','deductible']
  if p['network_required']:variants.append('network')
  if p['authorization_services']:variants.append('authorization')
  if 'prescription' in p['services']:variants.append('formulary')
  result.append(dict(id=p['id'],name=p['name'],version='synthetic-pack-1',effective_scope='2026 teaching fixtures; shared BN cost-sharing rules',real_world_policy=False,services=p['services'],assumptions=['Amounts are invented','Part C and Medicare Advantage are one pack','No real Medicare phases, eligibility or policy certification'],plans=[plan_for(p['id'],v,i) for v in variants]))
 return result

def journeys():
 result=[]
 # Each scenario starts with an independent fresh lifecycle/account state.
 for n,kind in enumerate(('multi_line','adjust_reverse','appeal_resolve','year_transition','coordination','partial_payment','replay'),1):
  p=plan_for('commercial_ppo','covered',n+20);p['case']['id']='AB-JOURNEY-'+str(n);p['case']['title']='Synthetic '+kind;p['objective']='Verify complete '+kind+' financial and event history journey'
  steps=p['case']['steps'];submit=steps[0];claim=submit['data']['claim_id'];line=submit['data']['lines'][0]
  def read():return dict(action='read',actor='customer-m100',data=dict(claim_id=claim))
  def mutation(a,rev,**extra):return dict(action=a,actor='customer-m100' if a=='appeal' else 'adjuster-demo' if a in ('adjust','resolve') else 'finance-demo',data=dict(claim_id=claim,operation_key=f'{kind}-{a}-key',expected_revision=rev,**extra))
  if kind=='multi_line':submit['data']['lines'].append(dict(id='LINE-TWO',service='outpatient',allowed_cents=34567))
  if kind=='coordination':line['other_payer_cents']=23671
  if kind=='partial_payment':submit['data']['lines'].append(dict(id='LINE-TWO',service='vision',allowed_cents=34567))
  if kind=='adjust_reverse':
   new=[dict(id='LINE-ONE',service='medical',allowed_cents=56789)]
   steps.extend([mutation('adjust',2,note='Synthetic correction',lines=new),read(),mutation('reverse',3,note='Synthetic reversal'),read()])
  if kind=='appeal_resolve':
   line['authorized']=False;line['service']='hospital'
   steps[:]=[submit,mutation('appeal',1,note='Synthetic appeal'),read(),mutation('resolve',2,note='Synthetic resolution',lines=[dict(id='LINE-ONE',service='hospital',allowed_cents=97003,authorized=True)]),read(),mutation('pay',3),read()]
  if kind=='year_transition':
   submit['data']['service_date']='2026-12-31';second=deepcopy(submit);second['data'].update(claim_id=claim+'-NEW',operation_key='year-new-submission',service_date='2027-01-01');steps.extend([second,dict(action='read',actor='customer-m100',data=dict(claim_id=claim+'-NEW')),read()])
  if kind=='replay':steps.extend([deepcopy(steps[1]),read()])
  compile_plan(p);result.append(p)
 return result
