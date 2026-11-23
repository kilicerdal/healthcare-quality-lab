"""Two frozen model stages; composition copies values, never solves them."""
from copy import deepcopy
import json
from jsonschema import Draft202012Validator
from healthcare_quality.compact_expectations import ANSWER,parse,assemble,inputs,context,answer_schema
from healthcare_quality.compact_expectations_v83 import cohort as previous_cohort,CHECKLIST
from healthcare_quality.expectation_protocol import RULES_TEXT
from healthcare_quality.advanced_schema import obj,parse_model_json
from healthcare_quality.expectation_lab import ExpectationLab
VERSION='staged-expectations-v84-1'
KIND='model_expectations_v84'
PRICING=obj(dict(quotes=deepcopy(ANSWER['properties']['quotes'])))
LIFECYCLE=obj(dict(observations=deepcopy(ANSWER['properties']['observations'])))
PRICING_RULES=RULES_TEXT.split('Submit returns status=201')[0]+"""
Return only quotes with quote_id, calculation and values. Quote values are USED account balances after the action, never limits. Author a quote for every distinct financial/account snapshot needed by the input steps. Rejected coverage: nominal deductible, copay, coinsurance base, preliminary payer, member and payout are ALL zero; eligible goes to noncovered. Remaining-cap fields still show limits minus prior USED balances. Rejected-only fresh accounts remain zero. For reused snapshots reuse your own quote ID. For reverse/adjust/resolve apply the allocation rules in the supplied facts. No lifecycle predictions in this phase. Quote values contain all twelve financial/account/policy fields; quote calculation contains the fifteen required per-line fields. All expected numbers must be yours, not computed by assembly.
"""
LIFECYCLE_RULES="""Return only observations: step_id, quote_id, ledger_calculation and the six lifecycle fields. Select a quote from YOUR OWN unverified pricing output; do not modify its values. No calculator or evaluator feedback is available.
A new submit: status201, adjudicated, revision1, event_count1, ledger0, ledger_count0. Submit is not payment. Pay: status200, paid, revision and event_count EACH increase by ONE, ledger delta equals YOUR quote payout (not allowed amount or noncovered), ledger_count increases by ONE EVEN FOR ZERO payout. Read: status200 and stored state/counters/balance unchanged. Reversal credits original payout, adds one revision/event/ledger entry; adjustment adds two ledger entries, one revision/event; appeal/resolve increment revision/event without ledger movement. Exact replay returns ORIGINAL response counters and status, but stored ledger_calculation has delta zero and reflects CURRENT stored ledger. Never copy a request's expected_revision as the resulting revision. Write ledger_before, signed delta, ledger_after before final lifecycle values. All step IDs in original order. No pricing recalculation in this phase."""
def cohort():
 data=previous_cohort();data['request_multiplier']=2
 for id,source,amount in [('H84-01','D83-01',27137),('H84-02','D82-01',71379)]:
  task=deepcopy(next(t for t in data['tasks'] if t['id']==source));task.update(id=id,split='reserved_until_exposed');task['plan']['case']['id']='AB-'+id;task['plan']['case']['title']='V8.4 fresh input-only '+id
  for step in task['plan']['case']['steps']:
   step['data']['claim_id']='CLAIM-'+id
   if 'operation_key' in step['data']:step['data']['operation_key']=step['action']+'-'+id
  task['plan']['case']['steps'][0]['data']['lines'][0]['allowed_cents']=amount
  data['tasks'].append(task)
 return data

def prompt(plan,stage='first',original=None,step=None,previous=None):
 if stage not in ('first','self_review'):raise ValueError('Unknown stage')
 facts=context(plan);facts.pop('actors');facts.pop('rules')
 return json.dumps(dict(facts=facts,inputs=inputs(plan),step=step,previous=previous or [],stage=stage,original=original),separators=(',',':'))

PRICING_RULES += "\n"+CHECKLIST

class StagedLab(ExpectationLab):
 def _call(self,r,row,stage,text,token,schema):
  common='IMMUTABLE SYNTHETIC FACTS AND INPUTS (no numeric solutions): '+text
  pricing_text=PRICING_RULES+'\n'+common
  first=super()._call(r,row,stage,pricing_text,token,PRICING)
  if first is None:return None
  row['calls'][-1]['generation_phase']='pricing';self._save(r,token)
  try:quotes=parse_model_json(first['text']);Draft202012Validator(PRICING).validate(quotes)
  except Exception:return dict(text='{}',composition_error='invalid_pricing_stage')
  lifecycle=deepcopy(LIFECYCLE);target=schema['properties']['observations'];lifecycle['properties']['observations']=deepcopy(target)
  second=super()._call(r,row,stage,LIFECYCLE_RULES+'\n'+common+'\nYOUR OWN UNVERIFIED PRICING: '+json.dumps(quotes,separators=(',',':')),token,lifecycle)
  if second is None:return None
  row['calls'][-1]['generation_phase']='lifecycle';self._save(r,token)
  try:observations=parse_model_json(second['text']);Draft202012Validator(lifecycle).validate(observations)
  except Exception:return dict(text='{}',composition_error='invalid_lifecycle_stage')
  return dict(text=json.dumps(dict(**quotes,**observations)),composition='exact model fields only; no arithmetic or evaluator feedback')
