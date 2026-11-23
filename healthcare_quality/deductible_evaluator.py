"""Post-freeze independent coverage/deductible gate; never imported by prompts."""
from copy import deepcopy
from healthcare_quality.compact_evaluator import evaluate as legacy_evaluate,worksheets as legacy_worksheets
from healthcare_quality.advanced_reference import Oracle,FAMILY
from healthcare_quality.benefit_reference import price
from healthcare_quality.compact_expectations import context
from healthcare_quality.ai_schema import digest
EXTRA=('coverage_decision','individual_deductible_remaining_cents','family_deductible_remaining_cents')

def worksheets(plan):
 old=legacy_worksheets(plan);oracle=Oracle();rows=[]
 for index,step in enumerate(plan['case']['steps']):
  before=deepcopy(oracle);oracle.step(step)
  if not old[index]:rows.append([]);continue
  d=step['data']
  if step['action']=='submit':member=d['member_id'];pid=d['plan_id'];day=d['service_date'];allocation=None
  else:
   c=before.claims[d['claim_id']];member=c['member'];pid=c['plan'];day=c['date'];allocation=c['allocation']
  year=int(day[:4]);ind=deepcopy(before.accounts.get(('member',member,year),dict(deductible=0,oop=0,benefit=0)));fam=deepcopy(before.accounts.get(('family',FAMILY[member],year),dict(deductible=0,oop=0,benefit=0)))
  if allocation:
   for account in (ind,fam):
    for k,v in allocation.items():account[k]-=v
  facts=context(plan);policy=next(p for p in facts['policies'] if p['start']<=day<p['end']);selected=next(p for p in facts['plans'] if p['id']==pid);extra=[]
  for line in d['lines']:
   covered=line['service'] in selected['services'] and (not selected['network_required'] or line.get('in_network',True)) and (line['service'] not in selected['authorization_services'] or line.get('authorized',True)) and (line['service']!='prescription' or line.get('formulary',True))
   extra.append(dict(coverage_decision='covered' if covered else 'rejected',individual_deductible_remaining_cents=max(0,policy['individual_deductible']-ind['deductible']),family_deductible_remaining_cents=max(0,policy['family_deductible']-fam['deductible'])))
   result=price(day,pid,[line],ind,fam);ind=result['individual'];fam=result['family']
  rows.append(extra)
 return rows

def evaluate(plan,answer):
 try:
  legacy=deepcopy(answer)
  for observation in legacy['observations']:
   for line in observation['calculation']:
    if line['coverage_decision'] not in ('covered','rejected'):raise ValueError('Invalid coverage decision')
    if any(type(line[k]) is not int or line[k]<0 for k in EXTRA[1:]):raise ValueError('Remaining deductibles must be nonnegative integer cents')
    for key in EXTRA:line.pop(key)
  result=legacy_evaluate(plan,legacy);reference=worksheets(plan);mismatches=[]
  for i,(observation,expected) in enumerate(zip(answer['observations'],reference)):
   actual=[{k:line[k] for k in EXTRA} for line in observation['calculation']]
   if expected and digest(actual)!=digest(expected):mismatches.append(dict(step=i+1,kind='v86_coverage_deductible',model=actual,reference=expected))
  result['worksheet_mismatches']=result.get('worksheet_mismatches',[])+mismatches;result['calculations_correct']=bool(result.get('calculations_correct') and not mismatches);result['eligible']=bool(result.get('eligible') and not mismatches);result['answer_hash']=digest(answer);result['scoring_contract']='v86_complete_observations_pricing_ledger_plus_coverage_and_remaining_deductibles; no numeric repairs';return result
 except (ValueError,TypeError,KeyError) as error:return dict(schema_valid=False,eligible=False,cases=[],error=type(error).__name__+': '+str(error),reference_assisted_corrections=0)
