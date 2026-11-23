"""V8.6: model-authored coverage and remaining-deductible worksheets."""
from copy import deepcopy
import json
from jsonschema import Draft202012Validator
from healthcare_quality import lean_expectations as v85
from healthcare_quality.compact_expectations import ANSWER as LEGACY_ANSWER,parse as legacy_parse,assemble,inputs,answer_schema as legacy_schema
from healthcare_quality.advanced_schema import obj,parse_model_json
from healthcare_quality.expectation_lab import ExpectationLab
from healthcare_quality.lean_expectations import selected_steps,quote_limit,shape,lifecycle_schema,lifecycle_prompt,PRICING_ACTION_RULES
VERSION='deductible-expectations-v86-1'
KIND='model_expectations_v86'
EXTRA=('coverage_decision','individual_deductible_remaining_cents','family_deductible_remaining_cents')
POLICY_NAMES={k:k+'_limit_cents' for k in ('individual_deductible','family_deductible','individual_oop','family_oop','annual_benefit')}
POLICY_NAMES['copay']='copay_cents'
ANSWER=deepcopy(LEGACY_ANSWER)
old_line=ANSWER['properties']['quotes']['items']['properties']['calculation']['items']
fields={}
for key,value in old_line['properties'].items():
 fields[key]=deepcopy(value)
 if key=='line_id':
  fields['coverage_decision']={'enum':['covered','rejected'],'description':'Decide from service/network/authorization/formulary facts BEFORE cost sharing.'}
  for name in EXTRA[1:]:fields[name]={'type':'integer','minimum':0,'maximum':500000000,'description':'Policy deductible LIMIT minus cumulative USED before this line, floored at zero. Model computes this value.'}
EXTENDED_LINE=obj(fields)
ANSWER['properties']['quotes']['items']['properties']['calculation']['items']=EXTENDED_LINE
PRICING_RULES="""Return only quotes, each with quote_id, calculation and values. Author every number yourself from the supplied synthetic facts. No calculator, reference answer, SUT response or correction tool is supplied. All money is integer cents.
INPUT POLICY *_limit_cents fields are LIMITS, never account usage. OUTPUT values individual_deductible, family_deductible, individual_oop, family_oop, individual_benefit and family_benefit are cumulative USED amounts after the snapshot. Accounts initially have zero used balances per member/family/service year; preserve prior claims in that year. Select the half-open policy interval by service_date.
For EACH line in order, FIRST emit coverage_decision, individual_deductible_remaining_cents, family_deductible_remaining_cents, then eligible and cost sharing. Remaining values describe accounts immediately BEFORE this particular line, including rejected lines:
individual_deductible_remaining_cents = max(0, policy.individual_deductible_limit_cents - individual_deductible_used).
family_deductible_remaining_cents = max(0, policy.family_deductible_limit_cents - family_deductible_used).
other = other_payer_cents or zero; eligible_cents = allowed_cents - other.
coverage_decision is covered ONLY if service belongs to selected plan services, required network and authorization conditions pass, and prescription formulary passes. Missing in_network, authorized and formulary default TRUE.
REJECTED BRANCH: nominal_deductible_cents=0, copay_cents=0, coinsurance_base_cents=0, payer_before_caps_cents=0, member_before_oop_cents=0, capped_member_cents=0, payer_after_oop_cents=0, member_cents=0, payout_cents=0; noncovered_cents=eligible_cents. Do NOT apply the covered formulas to rejected lines. Keep all used accounts unchanged. Still emit actual remaining deductible/OOP/benefit BEFORE that line; do not reset them to limits.
COVERED BRANCH, in this exact order:
nominal_deductible_cents = min(eligible_cents, individual_deductible_remaining_cents, family_deductible_remaining_cents). The entire eligible amount is deductible ONLY if BOTH remaining deductible balances cover it. Never let nominal deductible exceed either emitted remaining deductible.
copay_cents = min(eligible_cents - nominal_deductible_cents, policy.copay_cents).
coinsurance_base_cents = eligible_cents - nominal_deductible_cents - copay_cents.
payer_before_caps_cents = (coinsurance_base_cents * policy.payer_bps) // 10000, FLOOR.
member_before_oop_cents = eligible_cents - payer_before_caps_cents.
individual_oop_remaining_cents = max(0, policy.individual_oop_limit_cents - individual_oop_used); family_oop_remaining_cents = max(0, policy.family_oop_limit_cents - family_oop_used).
capped_member_cents = min(member_before_oop_cents, individual_oop_remaining_cents, family_oop_remaining_cents).
payer_after_oop_cents = eligible_cents - capped_member_cents.
annual_benefit_remaining_cents = max(0, policy.annual_benefit_limit_cents - individual_benefit_used).
payout_cents = min(payer_after_oop_cents, annual_benefit_remaining_cents); member_cents=capped_member_cents; noncovered_cents=eligible_cents-member_cents-payout_cents.
Only covered lines update accounts: increase BOTH individual and family USED deductible by min(nominal_deductible_cents,member_cents), USED OOP by member_cents and USED benefit by payout_cents. Process the next line with these UPDATED balances. Nominal deductible is before OOP clipping.
Sum line money, including other payer, into final values. partial is true only when both covered and rejected-coverage lines exist; benefit cap excess alone is not partial. Submit reserves accounts; pay/read/appeal do not change a financial snapshot. Reuse one quote for unchanged values. No state/revision/event/ledger fields in this stage. No prose or private deliberation."""

def cohort():
 data=v85.cohort()
 for task in data['tasks']:
  if task['split']=='reserved_until_exposed':task['split']='historical_exposed'
 for id,source,amount,denied in [('H86-01','H85-02',68423,None),('H86-02','H85-03',58317,7921)]:
  t=deepcopy(next(t for t in data['tasks'] if t['id']==source));t.update(id=id,split='reserved_until_exposed');c=t['plan']['case'];c['id']='AB-'+id;c['title']='V8.6 fresh input-only '+id
  for i,s in enumerate(c['steps']):
   s['data']['claim_id']='CLAIM-'+id
   if 'operation_key' in s['data']:s['data']['operation_key']=s['action']+'-'+id+'-'+str(i)
  c['steps'][0]['data']['lines'][0]['allowed_cents']=amount
  if denied is not None:c['steps'][0]['data']['lines'][1]['allowed_cents']=denied
  data['tasks'].append(t)
 return data

def prompt(plan,stage='first',original=None,step=None,previous=None):
 spec=json.loads(v85.prompt(plan,stage,original,step,previous))
 spec['facts']['policies']=[{POLICY_NAMES.get(k,k):v for k,v in policy.items()} for policy in spec['facts']['policies']]
 return json.dumps(spec,separators=(',',':'))

def pricing_schema(spec):
 schema=v85.pricing_schema(spec);schema['properties']['quotes']['items']['properties']['calculation']['items']=deepcopy(EXTENDED_LINE);return schema

def pricing_prompt(spec):
 steps=selected_steps(spec);actions={s['action'] for s in steps};payload=dict(facts=spec['facts'],inputs={**spec['inputs'],'steps':steps},requested_step=spec['step'],own_previous_predictions=spec['previous'])
 if spec['stage']=='self_review':payload['blind_original_model_output']=spec['original']
 return PRICING_RULES+'\n'+'\n'.join(v for k,v in PRICING_ACTION_RULES.items() if k in actions)+f'\nMaximum {quote_limit(spec)} quote(s), no duplicate unchanged snapshots. Only the requested step needs a quote in stepwise mode.\nINPUTS: '+json.dumps(payload,separators=(',',':'))

def answer_schema(plan,step=None):
 schema=legacy_schema(plan,step);schema['properties']['quotes']=deepcopy(ANSWER['properties']['quotes']);return schema

def normalize(raw):
 Draft202012Validator(ANSWER).validate(raw);quotes={q['quote_id']:q for q in raw['quotes']}
 if len(quotes)!=len(raw['quotes']):raise ValueError('Duplicate quote IDs')
 used={o['quote_id'] for o in raw['observations']}
 if not used<=set(quotes):raise ValueError('Missing quote reference')
 def content(q):return json.dumps({k:v for k,v in q.items() if k!='quote_id'},sort_keys=True)
 discarded=[]
 for id,q in quotes.items():
  if id not in used:
   if not any(content(q)==content(quotes[u]) for u in used):raise ValueError('Unused nonidentical quote')
   discarded.append(id)
 result=deepcopy(raw);result['quotes']=[q for q in result['quotes'] if q['quote_id'] in used]
 return result,dict(kind='unused_exact_aliases_only_including_v86_fields',discarded_quote_ids=discarded,expected_fields_changed=0)

def parse(text):
 canonical,audit=normalize(parse_model_json(text));legacy=deepcopy(canonical)
 for q in legacy['quotes']:
  for line in q['calculation']:
   for key in EXTRA:line.pop(key)
 answer=legacy_parse(json.dumps(legacy));quotes={q['quote_id']:q for q in canonical['quotes']}
 for o,expanded in zip(canonical['observations'],answer['observations']):expanded['calculation']=deepcopy(quotes[o['quote_id']]['calculation'])
 return answer

class LeanLab(ExpectationLab):
 def _call(self,r,row,stage,text,token,schema):
  spec=json.loads(text);metadata=shape(spec);ps=pricing_schema(spec)
  first=ExpectationLab._call(self,r,row,stage,pricing_prompt(spec),token,ps,generation_metadata=dict(phase='pricing',shape=metadata))
  if first is None:return None
  try:
   quotes=parse_model_json(first['text']);Draft202012Validator(ps).validate(quotes);ids=[q['quote_id'] for q in quotes['quotes']]
   if len(ids)!=len(set(ids)):raise ValueError('Duplicate quote IDs')
  except Exception:return dict(text='{}',composition_error='invalid_pricing_stage')
  ls=lifecycle_schema(schema,quotes);second=ExpectationLab._call(self,r,row,stage,lifecycle_prompt(spec,quotes),token,ls,generation_metadata=dict(phase='lifecycle',shape=metadata))
  if second is None:return None
  try:observations=parse_model_json(second['text']);Draft202012Validator(ls).validate(observations)
  except Exception:return dict(text='{}',composition_error='invalid_lifecycle_stage')
  return dict(text=json.dumps({**quotes,**observations}),composition='exact model fields; no arithmetic, correction, retry or resume')
