"""Post-freeze independent scoring. Never imported by prompt construction."""
from copy import deepcopy
from jsonschema import ValidationError
from healthcare_quality.expectation_protocol import assemble,parse,FIELDS,context
from healthcare_quality.advanced_lab import check
from healthcare_quality.advanced_reference import Oracle,FAMILY
from healthcare_quality.benefit_reference import price
from healthcare_quality.ai_schema import digest

def worksheets(plan):
 oracle=Oracle();rows=[]
 for s in plan['case']['steps']:
  before=deepcopy(oracle);observation=oracle.step(s);lines=[];d=s['data'];a=s['action']
  # Replay responses carry the original response and do not reprice.
  replay=a!='read' and d.get('operation_key') in before.operations
  if a in ('submit','adjust','resolve') and observation['status']<400 and not replay:
   if a=='submit':member=d['member_id'];pid=d['plan_id'];day=d['service_date'];allocation=None
   else:r=before.claims[d['claim_id']];member=r['member'];pid=r['plan'];day=r['date'];allocation=r['allocation']
   year=int(day[:4]);ind=deepcopy(before.accounts.get(('member',member,year),dict(deductible=0,oop=0,benefit=0)));fam=deepcopy(before.accounts.get(('family',FAMILY[member],year),dict(deductible=0,oop=0,benefit=0)))
   if allocation:
    for account in (ind,fam):
     for k,v in allocation.items():account[k]-=v
   facts=context(plan);policy=next(p for p in facts['policies'] if p['start']<=day<p['end']);planfacts=next(p for p in facts['plans'] if p['id']==pid)
   for line in d['lines']:
    eligible=line['allowed_cents']-line.get('other_payer_cents',0);accepted=line['service'] in planfacts['services'] and (not planfacts['network_required'] or line.get('in_network',True)) and (line['service'] not in planfacts['authorization_services'] or line.get('authorized',True)) and (line['service']!='prescription' or line.get('formulary',True))
    ded=min(eligible,max(0,policy['individual_deductible']-ind['deductible']),max(0,policy['family_deductible']-fam['deductible'])) if accepted else 0;copay=min(eligible-ded,policy['copay']) if accepted else 0;base=eligible-ded-copay if accepted else 0;result=price(day,pid,[line],ind,fam)
    lines.append(dict(line_id=line['id'],eligible_cents=eligible,nominal_deductible_cents=ded,copay_cents=copay,coinsurance_base_cents=base,payer_before_caps_cents=base*policy['payer_bps']//10000,member_before_oop_cents=eligible-base*policy['payer_bps']//10000 if accepted else 0,payer_after_oop_cents=eligible-result['member_cents'] if accepted else 0,**{k:result[k] for k in ('member_cents','payout_cents','noncovered_cents')}));ind=result['individual'];fam=result['family']
  rows.append(lines)
 return rows

def states(plan):
 oracle=Oracle();result=[]
 def counters(id):
  r=oracle.claims.get(id)
  return (r['revision'],r['events'],len(r['ledger']),sum(r['ledger'])) if r else (0,0,0,0)
 for step in plan['case']['steps']:
  prior=counters(step['data']['claim_id']);oracle.step(step);after=counters(step['data']['claim_id'])
  result.append(dict(zip(('prior_revision','prior_event_count','prior_ledger_count','prior_ledger_cents','stored_revision_after','stored_event_count_after','stored_ledger_count_after','stored_ledger_cents_after'),prior+after)))
 return result

def evaluate(plan,answer):
 try:
  case=assemble(plan,answer);assessment=check([case]);expected_lines=worksheets(plan);expected_states=states(plan);differences=[]
  for index,(o,expected) in enumerate(zip(answer['observations'],expected_lines),1):
   actual=o['calculation']['lines']
   if o['calculation']['state']!=expected_states[index-1]:differences.append(dict(step_id=f'S{index:02}',kind='state_worksheet',model=o['calculation']['state'],reference=expected_states[index-1]))
   if actual!=expected:differences.append(dict(step_id=f'S{index:02}',model=actual,reference=expected))
  return dict(schema_valid=True,input_preserved=True,observations_correct=assessment['review_ready'],calculations_correct=not differences,eligible=bool(assessment['review_ready'] and not differences),assessment=assessment,worksheet_mismatches=differences,cases=[case],answer_hash=digest(answer),expectation_author='local model; no calculator assistance',reference_assisted_corrections=0)
 except (ValidationError,ValueError,KeyError,TypeError,RecursionError) as e:return dict(schema_valid=False,input_preserved=False,eligible=False,error=type(e).__name__+': '+str(e)[:600],cases=[],reference_assisted_corrections=0)
