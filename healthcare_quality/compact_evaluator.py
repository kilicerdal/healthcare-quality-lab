"""Independent post-freeze complete-observation and pricing-worksheet gate."""
from healthcare_quality.compact_expectations import assemble
from healthcare_quality.advanced_lab import check
from healthcare_quality.ai_schema import digest
from healthcare_quality.expectation_evaluator import worksheets as basic_worksheets
from copy import deepcopy
from healthcare_quality.advanced_reference import Oracle,FAMILY
from healthcare_quality.benefit_reference import price
from healthcare_quality.compact_expectations import context

def worksheets(plan):
 rows=basic_worksheets(plan);oracle=Oracle()
 for index,step in enumerate(plan['case']['steps']):
  before=deepcopy(oracle);oracle.step(step)
  if not rows[index]:continue
  d=step['data']
  if step['action']=='submit':member=d['member_id'];pid=d['plan_id'];day=d['service_date'];allocation=None
  else:
   claim=before.claims[d['claim_id']];member=claim['member'];pid=claim['plan'];day=claim['date'];allocation=claim['allocation']
  year=int(day[:4]);ind=deepcopy(before.accounts.get(('member',member,year),dict(deductible=0,oop=0,benefit=0)));fam=deepcopy(before.accounts.get(('family',FAMILY[member],year),dict(deductible=0,oop=0,benefit=0)))
  if allocation:
   for account in (ind,fam):
    for key,value in allocation.items():account[key]-=value
  policy=next(p for p in context(plan)['policies'] if p['start']<=day<p['end'])
  for line,worksheet in zip(d['lines'],rows[index]):
   worksheet.update(individual_oop_remaining_cents=max(0,policy['individual_oop']-ind['oop']),family_oop_remaining_cents=max(0,policy['family_oop']-fam['oop']),capped_member_cents=worksheet['member_cents'],annual_benefit_remaining_cents=max(0,policy['annual_benefit']-ind['benefit']))
   priced=price(day,pid,[line],ind,fam);ind=priced['individual'];fam=priced['family']
 return rows

def ledger_states(plan):
 oracle=Oracle();rows=[]
 for step in plan['case']['steps']:
  id=step['data']['claim_id'];prior=sum(oracle.claims.get(id,{}).get('ledger',[]));oracle.step(step);after=sum(oracle.claims.get(id,{}).get('ledger',[]));rows.append(dict(ledger_before_cents=prior,ledger_delta_cents=after-prior,ledger_after_cents=after))
 return rows

def evaluate(plan,answer):
 try:
  case=assemble(plan,answer);assessment=check([case]);valid=assessment['valid'];correct=assessment['review_ready'];expected=worksheets(plan);mismatches=[dict(step=i+1,model=o['calculation'],reference=lines) for i,(o,lines) in enumerate(zip(answer['observations'],expected)) if lines and digest(o['calculation'])!=digest(lines)]
  ledger=ledger_states(plan);mismatches.extend(dict(step=i+1,kind='stored_ledger',model=o['ledger_calculation'],reference=expected_ledger) for i,(o,expected_ledger) in enumerate(zip(answer['observations'],ledger)) if digest(o['ledger_calculation'])!=digest(expected_ledger))
  return dict(schema_valid=valid,input_preserved=valid,observations_correct=correct,calculations_correct=not mismatches,worksheet_mismatches=mismatches,eligible=bool(correct and not mismatches),assessment=assessment,cases=[case] if valid else [],answer_hash=digest(answer),reference_assisted_corrections=0,scoring_contract='complete_observations_pricing_and_ledger_worksheets_v82; no revision/event worksheet claim')
 except (ValueError,TypeError,KeyError,RecursionError) as e:return dict(schema_valid=False,eligible=False,cases=[],error=type(e).__name__+': '+str(e)[:600],reference_assisted_corrections=0)
