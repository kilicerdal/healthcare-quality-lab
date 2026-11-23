"""V8.5 first-attempt stages. Constraints describe structure, never answers."""
from copy import deepcopy
import json
from jsonschema import Draft202012Validator
from healthcare_quality.staged_expectations import cohort as old_cohort,parse,normalize,PRICING,LIFECYCLE
from healthcare_quality.compact_expectations import ANSWER,assemble,inputs,context,answer_schema
from healthcare_quality.advanced_schema import parse_model_json
from healthcare_quality.expectation_lab import ExpectationLab
VERSION='lean-expectations-v85-1'
KIND='model_expectations_v85'
PRICING_RULES="""Author pricing JSON only: quotes with quote_id, calculation and values. No observations, state, revision, events or ledger in this stage. All money is integer cents; no tools, numeric reference answers or application responses are supplied.
All six individual/family deductible, OOP and benefit values mean cumulative USED amounts, NEVER policy limits or remaining balances. Accounts begin at zero per member/family/service calendar year and persist across claims. Service date selects a half-open policy interval.
Process lines in order. other=other_payer_cents or zero; eligible=allowed-other. Coverage requires the plan's service, required network/authorization and formulary conditions. Missing in_network, authorized and formulary flags default TRUE.
If coverage is rejected: nominal_deductible_cents, copay_cents, coinsurance_base_cents, payer_before_caps_cents, member_before_oop_cents, capped_member_cents, payer_after_oop_cents, member_cents and payout_cents are ALL ZERO; noncovered=eligible. Do not allocate used accounts. Remaining-cap fields still show the actual balances immediately before that line.
Otherwise nominal deductible=min(eligible,remaining individual deductible,remaining family deductible); copay=min(eligible-deductible,policy copay); base=eligible-deductible-copay; preliminary payer=(base*payer_bps)//10000, FLOOR. member_before_oop=eligible-preliminary payer. Individual/family OOP remaining=max(0,limit-used). capped_member=min(member_before_oop,both OOP remaining). payer_after_oop=eligible-capped_member. annual benefit remaining=max(0,annual_benefit-individual benefit used); payout=min(payer_after_oop,annual benefit remaining). member=capped_member; noncovered=eligible-member-payout.
Increase BOTH individual and family used deductible by min(nominal deductible,member), OOP by member, benefit by payout. Capture remaining fields BEFORE each line using updated accounts from earlier lines, including a later rejected line. Never reset balances on rejected coverage.
Sum line money, including other-payer, into quote values. partial is true only when BOTH a covered and a rejected-coverage line exist. It is false for an entirely rejected claim and for benefit-cap excess alone. Nominal deductible is before OOP clipping.
Submit reserves accounts. Pay/read/appeal do not change the financial/account quote. Reuse the SAME quote for an unchanged snapshot; do not make a quote per lifecycle step. Keep quote IDs in first-needed snapshot order. Never fill an account from a similarly named policy limit."""
PRICING_ACTION_RULES={
 'reverse':'Reversal credits only this claim original allocation, not earlier claims. Keep original quote payout/member but return current used balances.',
 'adjust':'Adjustment undoes original allocation then prices replacement lines, preserving other claims and current family/year balances.',
 'resolve':'Resolution undoes original allocation then prices corrected lines under original plan/date; no coverage exceptions.'}
LIFECYCLE_RULES="""Author observations only, in the requested step order. Reference only the listed quote IDs from YOUR OWN unverified pricing; never change those values. Predict only HTTP status, state, revision, event_count, stored ledger balance/count, and ledger_before/delta/after worksheets. No calculator or evaluator feedback is supplied. These scenarios contain successful valid actions.
Submit: status201, adjudicated, revision1, event_count1, stored ledger0, ledger_count0. Adjudication is NOT payment. Pay: status200, paid; increment revision and event_count by ONE each; ledger delta=the model quote payout, not allowed/noncovered money; ledger_count increases by ONE EVEN WHEN payout is ZERO. Read: status200 and current stored counters/state/balances unchanged. Read ledger delta is zero.
Exact actor/action/key/input replay returns the ORIGINAL response snapshot and status without new stored events or payments. Its ledger worksheet describes CURRENT stored before/after balances with delta zero. A request expected_revision is not the resulting revision. Write the stored ledger worksheet before final counters. Every nonreplayed mutation increments revision and event_count once. Quote reuse does not reuse HTTP status or lifecycle counters."""
LIFECYCLE_ACTION_RULES={
 'reverse':'Reverse: status200, reversed, credit original payout, ledger_count+1.',
 'adjust':'Adjust: status200, paid, credit old payout/debit replacement payout, ledger_count+2.',
 'appeal':'Appeal: status200, appealed, no ledger change.',
 'resolve':'Resolve: status200, adjudicated, no ledger change.'}

def cohort():
 data=old_cohort()
 for task in data['tasks']:
  if task['split']=='reserved_until_exposed':task['split']='historical_exposed'
 for id,source,amount,denied in [('H85-01','D83-01',28613,None),('H85-02','D82-01',76391,None),('H85-03','D83-02',54731,6193)]:
  task=deepcopy(next(t for t in data['tasks'] if t['id']==source));task.update(id=id,split='reserved_until_exposed');case=task['plan']['case'];case['id']='AB-'+id;case['title']='V8.5 fresh input-only '+id
  for i,step in enumerate(case['steps']):
   step['data']['claim_id']='CLAIM-'+id
   if 'operation_key' in step['data']:step['data']['operation_key']=step['action']+'-'+id+'-'+str(i)
  case['steps'][0]['data']['lines'][0]['allowed_cents']=amount
  if denied is not None:case['steps'][0]['data']['lines'][1]['allowed_cents']=denied
  data['tasks'].append(task)
 return data

def prompt(plan,stage='first',original=None,step=None,previous=None):
 if stage not in ('first','self_review'):raise ValueError('Unknown stage')
 facts=context(plan);facts.pop('actors');facts.pop('rules');facts['plans']=[{k:v for k,v in plan.items() if k in ('id','services','network_required','authorization_services')} for plan in facts['plans']]
 return json.dumps(dict(facts=facts,inputs=inputs(plan),step=step,previous=previous or [],stage=stage,original=original),separators=(',',':'))

def selected_steps(spec):
 steps=spec['inputs']['steps']
 if spec['step'] is not None:
  ids=[s['step_id'] for s in steps]
  if spec['step'] not in ids:raise ValueError('Unknown immutable step')
  return steps[:ids.index(spec['step'])+1]
 return steps

def quote_limit(spec):
 if spec['step'] is not None:return 1 # Exactly one requested observation.
 steps=selected_steps(spec);claims={s['data']['claim_id'] for s in steps};actions=[s['action'] for s in steps]
 if len(claims)==1 and actions.count('submit')==1 and set(actions)<={'submit','pay','read','appeal'}:return 1
 return len(steps) # Reads after other claims can expose changed family snapshots.

def shape(spec):
 return dict(quote_limit=quote_limit(spec),line_limit=max([len(s['data'].get('lines',[])) for s in selected_steps(spec)]+[0]),observations=1 if spec['step'] else len(selected_steps(spec)))

def pricing_schema(spec):
 schema=deepcopy(PRICING);limit=quote_limit(spec);q=schema['properties']['quotes'];q['maxItems']=limit;q['items']['properties']['quote_id']={'enum':[f'Q{i:02}' for i in range(1,limit+1)]}
 for key,value in q['items']['properties']['values']['properties'].items():
  if key.startswith(('individual_','family_')):value['description']='Cumulative USED account after this snapshot, not a policy limit or remaining balance.'
 return schema

def pricing_prompt(spec):
 steps=selected_steps(spec);actions={s['action'] for s in steps};text=PRICING_RULES+'\n'+'\n'.join(v for k,v in PRICING_ACTION_RULES.items() if k in actions)
 payload=dict(facts=spec['facts'],inputs={**spec['inputs'],'steps':steps},requested_step=spec['step'],own_previous_predictions=spec['previous'])
 if spec['stage']=='self_review':payload['blind_original_model_output']=spec['original']
 return text+f'\nMaximum {quote_limit(spec)} quote(s); do not duplicate an unchanged snapshot. Only the requested step needs a quote in stepwise mode.\nINPUTS: '+json.dumps(payload,separators=(',',':'))

def lifecycle_schema(schema,quotes):
 result=deepcopy(LIFECYCLE);result['properties']['observations']=deepcopy(schema['properties']['observations']);result['properties']['observations']['items']['properties']['quote_id']={'enum':[q['quote_id'] for q in quotes['quotes']]};return result

def lifecycle_prompt(spec,quotes):
 steps=selected_steps(spec);actions={s['action'] for s in steps};metadata=[{**s,'data':{k:v for k,v in s['data'].items() if k!='lines'}} for s in steps]
 payload=dict(steps=metadata,requested_step=spec['step'],own_unverified_quotes=quotes,own_previous_predictions=spec['previous'])
 if spec['stage']=='self_review':payload['blind_original_model_output']=spec['original']
 return LIFECYCLE_RULES+'\n'+'\n'.join(v for k,v in LIFECYCLE_ACTION_RULES.items() if k in actions)+'\nALLOWED QUOTE IDS: '+','.join(q['quote_id'] for q in quotes['quotes'])+'\nLIFECYCLE INPUTS: '+json.dumps(payload,separators=(',',':'))

class LeanLab(ExpectationLab):
 def _call(self,r,row,stage,text,token,schema):
  spec=json.loads(text);request_shape=shape(spec);ps=pricing_schema(spec)
  first=ExpectationLab._call(self,r,row,stage,pricing_prompt(spec),token,ps,generation_metadata=dict(phase='pricing',shape=request_shape))
  if first is None:return None
  try:
   quotes=parse_model_json(first['text']);Draft202012Validator(ps).validate(quotes)
   ids=[q['quote_id'] for q in quotes['quotes']]
   if len(ids)!=len(set(ids)):raise ValueError('Duplicate quote IDs')
  except Exception:return dict(text='{}',composition_error='invalid_pricing_stage')
  ls=lifecycle_schema(schema,quotes)
  second=ExpectationLab._call(self,r,row,stage,lifecycle_prompt(spec,quotes),token,ls,generation_metadata=dict(phase='lifecycle',shape=request_shape))
  if second is None:return None
  try:observations=parse_model_json(second['text']);Draft202012Validator(ls).validate(observations)
  except Exception:return dict(text='{}',composition_error='invalid_lifecycle_stage')
  return dict(text=json.dumps({**quotes,**observations}),composition='exact model values; no retry, resume or numeric repair')
