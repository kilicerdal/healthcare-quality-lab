"""V8.2 compact model-only quotes. Expansion is exact copying, never arithmetic."""
from copy import deepcopy
import json
from jsonschema import Draft202012Validator
from healthcare_quality.advanced_schema import obj,success,parse_model_json
from healthcare_quality.expectation_protocol import inputs,context,DATA,LINE
VERSION='compact-expectations-v82-4'
KIND='model_expectations_v82'
STATE_KEYS=('status','state','revision','event_count','ledger_cents','ledger_count')
QUOTE_KEYS=tuple(k for k in success if k not in STATE_KEYS)
CAP_LINE=deepcopy(LINE)
cap_properties={}
for key,value in CAP_LINE['properties'].items():
 if key=='payer_after_oop_cents':
  for name in ('individual_oop_remaining_cents','family_oop_remaining_cents','capped_member_cents','annual_benefit_remaining_cents'):cap_properties[name]={'type':'integer','minimum':0,'maximum':500000000}
 cap_properties[key]=value
CAP_LINE=obj(cap_properties)
QUOTE=obj(dict(quote_id={'type':'string','pattern':'^Q[0-9]{2}$'},calculation={'type':'array','maxItems':5,'items':deepcopy(CAP_LINE)},values=obj({k:deepcopy(success[k]) for k in QUOTE_KEYS})))
LEDGER=obj(dict(ledger_before_cents={'type':'integer','minimum':0,'maximum':500000000},ledger_delta_cents={'type':'integer','minimum':-500000000,'maximum':500000000},ledger_after_cents={'type':'integer','minimum':0,'maximum':500000000}))
OBS=obj(dict(step_id={'type':'string','pattern':'^S[0-9]{2}$'},quote_id={'type':'string','pattern':'^Q[0-9]{2}$'},ledger_calculation=deepcopy(LEDGER),**{k:deepcopy(success[k]) for k in STATE_KEYS}))
WIRE=obj(dict(quotes={'type':'array','minItems':1,'maxItems':16,'items':QUOTE},observations={'type':'array','minItems':1,'maxItems':16,'items':OBS}))
ANSWER=WIRE
RULES="""Author every expected number yourself. No calculator, application responses, tools or numeric solutions are supplied. Fixed inputs cannot be changed. Return ONLY compact JSON. For each new quote FIRST emit the per-line calculation worksheet (line_id, eligible_cents, nominal_deductible_cents, copay_cents, coinsurance_base_cents, payer_before_caps_cents, member_before_oop_cents, individual_oop_remaining_cents, family_oop_remaining_cents, capped_member_cents, annual_benefit_remaining_cents, payer_after_oop_cents, member_cents, payout_cents, noncovered_cents), THEN its final values. Explicitly write remaining individual/family OOP and annual benefit BEFORE choosing capped_member_cents. capped_member_cents = min(member_before_oop_cents, individual_oop_remaining_cents, family_oop_remaining_cents). payer_after_oop_cents = eligible_cents - capped_member_cents. payout_cents = min(payer_after_oop_cents, annual_benefit_remaining_cents). For rejected coverage use capped_member_cents=0 and payer_after_oop_cents=0; remaining caps still show the actual remaining balances. Finish the arithmetic before writing the final quote. Rejected-coverage line worksheets have member_before_oop_cents=0 and payer_after_oop_cents=0, not eligible. Nominal deductible is before OOP clipping. The final payer_after_oop is eligible minus FINAL capped member, not the preliminary payer. Write financial quote values once and reference YOUR OWN quote_id on each observation. Reuse only when ALL 12 quote values (including current used accounts) are unchanged. If accounts or money change, author another complete quote. Before each observation's lifecycle fields write ledger_calculation: stored ledger_before_cents, signed ledger_delta_cents, stored ledger_after_cents. These are actual stored balances, not a replayed response snapshot. A new submit has before=0, delta=0, after=0: adjudication is NOT payment. A pay has delta=payout; a read or replay has delta=0; reversal delta=-payout. Then write the six lifecycle fields; submit ledger_cents must be zero, not the calculated payout. Never omit one of the six lifecycle fields. All cents are integers; used accounts start at zero PER calendar year and persist across claims in the same year. M100/M200/M300 share family F100; M400 has F400. Accounts reserve on submit, not payment.
For each line: other = supplied other_payer or zero; eligible=allowed-other. Coverage requires allowed service, required network/authorization and formulary. If REJECTED: payout=member=0; noncovered=eligible; used accounts unchanged. Rejected coverage does NOT make partial true by itself.
If covered: deductible=min(eligible,max(0,individual_deductible_limit-individual_used),max(0,family_deductible_limit-family_used)); copay=min(eligible-deductible,policy.copay); base=eligible-deductible-copay; preliminary=(base*payer_bps)//10000 (FLOOR).
CAP CHECK REQUIRED: preliminary member=eligible-preliminary; remaining individual OOP=max(0,individual_oop_limit-individual_oop_used); remaining family OOP=max(0,family_oop_limit-family_oop_used). Final member=min(preliminary member,remaining individual OOP,remaining family OOP). If the OOP cap lowers member cost, payer becomes eligible-FINAL member; do NOT keep the preliminary payer. Final payout=min(eligible-final member,max(0,annual_benefit-individual_benefit_used)). Noncovered=eligible-member-payout. Increase BOTH member/family used deductible by min(nominal deductible,final member), used OOP by final member and used benefit by payout. Process lines in order using updated accounts. Used account values are not policy limits. On a second claim subtract prior USED balances from limits, never add them.
partial is true ONLY if the claim contains BOTH a covered line and a rejected-coverage line. It is false for a wholly unauthorized/out-of-network claim and false for benefit-cap excess on otherwise covered lines.
Submit:201/adjudicated/revision1/events1/ledger0/count0; reserve accounts immediately. Pay by finance:200/paid, revision+1/events+1, ledger+payout/count+1 EVEN FOR ZERO payout; quote/accounts unchanged. Read:200; no changes. Exact replay returns ORIGINAL saved response (including its status, revision, ledger and account snapshot), makes no changes; a later read sees CURRENT state. Do not increase anything for replay.
Reverse by finance:200/reversed, revision+1/events+1, ledger-payout/count+1; credit ONLY this claim's original allocation, not previous claims' allocations. Keep the original quote money, return current used accounts. Adjustment by adjuster while paid: undo original allocation, reprice replacement lines, add credit old/debit new ledger entries, revision+1/events+1/count+2. Appeal by owner:200/appealed, revision+1/events+1, no financial changes. Resolve by adjuster:200/adjudicated, revision+1/events+1, undo old allocation/reprice new lines, ledger unchanged. Date selects half-open policy interval; new year starts new accounts.
These scenarios use successful valid actions only. Return all step IDs in order. Quote aliases are a compression of your own numbers, not calculator assistance. Only the requested numeric pricing records and JSON fields; no prose, code or private deliberation. A reused quote also reuses its worksheet. Pricing-action worksheets and stored-ledger worksheets are independently scored; no revision/event state worksheet is claimed."""
def cohort():return json.loads((DATA/'expectation_cohort_v82.json').read_text())
def prompt(plan,stage='first',original=None,step=None,previous=None):
 if stage not in ('first','self_review'):raise ValueError('Unknown stage')
 facts=context(plan);facts.pop('rules');facts.pop('actors');text=RULES+'\nRAW SYNTHETIC FACTS: '+json.dumps(facts,separators=(',',':'))+'\nIMMUTABLE INPUTS: '+json.dumps(inputs(plan),separators=(',',':'))
 if step is not None:text+='\nReturn only '+step+'. Prior observations are YOUR OWN unverified predictions, never reference/application results: '+json.dumps(previous or [],separators=(',',':'))
 if stage=='self_review':
  if original is None:raise ValueError('Original required')
  text+='\nBLIND SELF REVIEW of your own raw answers only, no evaluator feedback: '+json.dumps(original,separators=(',',':'))
 return text
def answer_schema(plan,step=None):
 ids=[s['step_id'] for s in inputs(plan)['steps'] if step is None or s['step_id']==step]
 if not ids:raise ValueError('Unknown step')
 schema=deepcopy(WIRE);obs=schema['properties']['observations'];obs.update(minItems=len(ids),maxItems=len(ids));obs['items']['properties']['step_id']={'enum':ids};return schema
def parse(text):
 raw=parse_model_json(text);Draft202012Validator(WIRE).validate(raw);quotes={q['quote_id']:q for q in raw['quotes']}
 if len(quotes)!=len(raw['quotes']):raise ValueError('Duplicate quote IDs')
 used={o['quote_id'] for o in raw['observations']}
 if used!=set(quotes):raise ValueError('Missing or unused quote')
 observations=[]
 for o in raw['observations']:observations.append(dict(step_id=o['step_id'],calculation=deepcopy(quotes[o['quote_id']]['calculation']),ledger_calculation=deepcopy(o['ledger_calculation']),expect={**deepcopy(quotes[o['quote_id']]['values']),**{k:deepcopy(o[k]) for k in STATE_KEYS}}))
 return dict(observations=observations)
def assemble(plan,answer):
 if not isinstance(answer,dict) or set(answer)!={'observations'}:raise ValueError('Observations required')
 actual=[o['step_id'] for o in answer['observations']];ids=[s['step_id'] for s in inputs(plan)['steps']]
 if actual!=ids:raise ValueError('Exactly one observation per immutable step in order')
 c=deepcopy(plan['case'])
 for s,o in zip(c['steps'],answer['observations']):
  if set(o)!={'step_id','expect','calculation','ledger_calculation'}:raise ValueError('Unexpected observation fields')
  s['expect']=deepcopy(o['expect'])
 return c
