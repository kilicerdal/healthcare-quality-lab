"""Model-only expectation construction. No oracle, SUT or calculator imports.
Assembly copies immutable input steps and model-authored observations without
computing, filling or repairing any expected number.
"""
from copy import deepcopy
from pathlib import Path
import json
from jsonschema import Draft202012Validator
from healthcare_quality.advanced_schema import EXPECT,SCHEMA,obj,parse_model_json
from healthcare_quality.ai_schema import digest
DATA=Path(__file__).with_name('data')
VERSION='expectations-only-v81-6'
FIELDS=('eligible_cents','nominal_deductible_cents','copay_cents','coinsurance_base_cents','payer_before_caps_cents','member_before_oop_cents','payer_after_oop_cents','member_cents','payout_cents','noncovered_cents')
LINE=obj(dict(line_id=dict(type='string',minLength=3,maxLength=48),**{k:dict(type='integer',minimum=0,maximum=500000000) for k in FIELDS}))
STATE_FIELDS=('prior_revision','prior_event_count','prior_ledger_count','prior_ledger_cents','stored_revision_after','stored_event_count_after','stored_ledger_count_after','stored_ledger_cents_after')
STATE=obj({k:dict(type='integer',minimum=0,maximum=500000000) for k in STATE_FIELDS})
OBSERVATION=obj(dict(step_id=dict(type='string',pattern=r'^S[0-9]{2}$'),calculation=obj(dict(state=STATE,lines=dict(type='array',maxItems=5,items=LINE),accounting_note=dict(type='string',minLength=3,maxLength=500))),expect=deepcopy(EXPECT)))
ANSWER=obj(dict(observations=dict(type='array',minItems=1,maxItems=16,items=OBSERVATION)))
ANSWER['$defs']=deepcopy(SCHEMA['$defs'])
Draft202012Validator.check_schema(ANSWER)

def inputs(plan):
 c=deepcopy(plan['case'])
 if any('expect' in s for s in c['steps']):raise ValueError('Input plan must contain no expected answers')
 return dict(case_id=c['id'],steps=[dict(step_id=f'S{i:02}',**s) for i,s in enumerate(c['steps'],1)])

def context(plan):
 """Read facts directly. Never call retrieve/compile_plan to construct a prompt."""
 facts=json.loads((DATA/'benefits_v60.json').read_text());plans=json.loads((DATA/'plans.json').read_text());ids={s['data']['plan_id'] for s in plan['case']['steps'] if s['action']=='submit'};dates={s['data']['service_date'] for s in plan['case']['steps'] if s['action']=='submit'}
 return dict(scope=facts['scope'],policies=[p for p in facts['policies'] if any(p['start']<=d<p['end'] for d in dates)],plans=[p for p in plans if p['id'] in ids],rules=facts['rules'],families={'M100':'F100','M200':'F100','M300':'F100','M400':'F400'},actors=json.loads((DATA/'actors.json').read_text()))

RULES_TEXT="""You author ALL expected values. Return observations only, keyed by supplied step_id. No action, actor, inputs, code, tool calls or URLs. No numeric answers, calculator results or application responses are available.
Emit calculation BEFORE expect for each step. First fill its state worksheet: prior counters describe the actual stored claim before the action (zero if not yet created); stored_*_after describes the stored claim after it. A new nonreplayed pay increments revision and event_count by ONE; a read changes neither. Ledger_count increments on pay even when payout is zero. These are used counters, never request expected_revision values. Replays leave stored counters unchanged and return the original response snapshot. Never copy the old revision/event_count to a new payment. Then fill monetary line worksheets and finally the observation. Complete the numeric worksheet first, then copy the final monetary values into expect. All accumulator fields mean USED SO FAR, never policy limits or remaining balances. A policy cap is not an account balance. Do not convert cents to dollars in any field or note. All money is integer cents. For EACH line in order:
other = other_payer_cents or zero; eligible = allowed - other.
If service/network/authorization/formulary rejects coverage: payout=0, member=0, noncovered=eligible, all deductible/copay/coinsurance worksheet fields=0. Other-payer money is still counted. Do not allocate accounts.
Otherwise nominal_deductible=min(eligible,max(0,individual_limit-individual_used),max(0,family_limit-family_used)).
copay=min(eligible-nominal_deductible,policy.copay).
coinsurance_base=eligible-nominal_deductible-copay.
payer_before_caps=(coinsurance_base * payer_bps) // 10000. The remainder stays with the member; never round to nearest cent.
member_before_oop=eligible-payer_before_caps.
member=min(member_before_oop,max(0,individual_oop_limit-individual_oop_used),max(0,family_oop_limit-family_oop_used)).
payer_after_oop=eligible-member.
payout=min(payer_after_oop,max(0,annual_benefit-individual_benefit_used)); noncovered=eligible-member-payout.
Allocate deductible by min(nominal_deductible,member), OOP by member, benefit by payout to BOTH member and family accounts. OOP includes deductible/copay/member coinsurance, not other-payer or noncovered. Repeat per line with updated accounts.
Worksheet nominal_deductible_cents is BEFORE OOP clipping; deductible ACCUMULATOR increments may be smaller.
When neither OOP nor benefit cap binds, payout must equal payer_before_caps. Do not invent an OOP cap or change the preliminary payment without a binding cap. Independently verify the integer subtraction eligible-payer_before_caps in member_before_oop_cents.
Initial accounts are zero per member/family/service calendar year; do not reset for a second claim in the same year. Service dates select half-open policy intervals, not the current date.
Submit returns status=201,state=adjudicated,revision=1,event_count=1,ledger_cents=0,ledger_count=0. Adjudication reserves accounts BEFORE payment.
Only submit success is HTTP status 201. EVERY successful pay, read, reverse, adjust, appeal or resolve has HTTP status 200. Copying a prior quote does NOT copy its HTTP status. Successful nonreplayed mutations increment revision and event_count once. Reads return status=200, do not increment revision/events, and preserve current ledger/accounts.
Pay: finance, adjudicated -> paid, one debit of payout, ledger_count +1 even for zero payout. Keep only the financial quote and account amounts unchanged; status becomes 200, state becomes paid, revision and event_count each increment by one, ledger reflects the new debit.
Reverse: finance, paid -> reversed, credit payout once, ledger_count +1, undo only original allocations; keep original quote payout/member, not zero quotes.
Adjustment: adjuster, paid -> paid, undo original allocation then reprice replacement lines, credit old/debit new payout (ledger_count +2).
Appeal: owner, adjudicated -> appealed, no price/ledger changes. Resolve: adjuster, appealed -> adjudicated, credit old allocations then reprice; ledger unchanged.
Identical actor/action/input idempotency replay returns the ORIGINAL response snapshot, without new events/ledger or account changes. A later read sees current state.
Rejections have ONLY status,error; do not include successful observation fields. For a known claim add no state changes on rejection. New missing claim read is 404 NOT_FOUND; wrong role/owner 403 FORBIDDEN; changed key payload 409 IDEMPOTENCY_CONFLICT; stale revision 409 REVISION_CONFLICT; wrong state 409 INVALID_TRANSITION.
Successful expect must include ALL 18 fields: status,state,revision,event_count,payout_cents,member_cents,other_payer_cents,noncovered_cents,ledger_cents,ledger_count,individual_deductible,individual_oop,individual_benefit,family_deductible,family_oop,family_benefit,policy_id,partial.
partial means at least one covered and at least one noncovered line, not a cap excess on covered lines.
Provide line worksheets for successful submit/adjust/resolve; for read/pay/reverse/appeal/rejection use an empty lines array and a short accounting note. Do not provide private chain-of-thought; provide only auditable numeric records and a concise state/ledger note."""

def prompt(plan,stage='first',original=None,step=None,previous=None):
 if stage not in ('first','self_review'):raise ValueError('Unknown model stage')
 text=RULES_TEXT+'\nSYNTHETIC FACTS: '+json.dumps(context(plan),sort_keys=True)+'\nIMMUTABLE INPUTS: '+json.dumps(inputs(plan),sort_keys=True)
 if step is not None:text+='\nReturn ONLY observation for '+step+'. Earlier observations below are YOUR own unverified predictions, never application or reference responses: '+json.dumps(previous or [],sort_keys=True)
 if stage=='self_review':
  if original is None:raise ValueError('Self review requires original model output')
  text+='\nBLIND SELF REVIEW: Check your original answer against these rules and input IDs. Return a complete replacement observations object. No evaluator score, mismatch feedback, correct answer or application response is supplied. ORIGINAL MODEL OUTPUT: '+json.dumps(original,sort_keys=True)
 return text

def parse(text):
 a=parse_model_json(text);Draft202012Validator(ANSWER).validate(a);return a

def assemble(plan,answer):
 Draft202012Validator(ANSWER).validate(answer)
 expected=[s['step_id'] for s in inputs(plan)['steps']];actual=[s['step_id'] for s in answer['observations']]
 if actual!=expected:raise ValueError('Return each immutable step ID exactly once in input order')
 c=deepcopy(plan['case'])
 for s,o in zip(c['steps'],answer['observations']):s['expect']=deepcopy(o['expect'])
 return c

def cohort():return json.loads((DATA/'expectation_cohort_v81.json').read_text())


def answer_schema(plan,step=None):
 """Portable object-only JSON schema. Input IDs/counts only; no expected money.
 The installed small-model grammar rejects boolean item schemas. Assembly
 independently rejects duplicated, omitted or reordered step IDs.
 """
 steps=inputs(plan)['steps'];steps=[s for s in steps if step is None or s['step_id']==step]
 if not steps:raise ValueError('Unknown immutable step')
 item=deepcopy(OBSERVATION);item['properties']['step_id']={'enum':[s['step_id'] for s in steps]};item['properties']['expect']={'$ref':'#/$defs/expect'}
 lines=item['properties']['calculation']['properties']['lines']
 if step is not None and steps[0]['action'] not in ('submit','adjust','resolve'):item['properties']['calculation']['properties']['lines']={'type':'array','maxItems':0,'items':{}}
 else:lines['items']={'$ref':'#/$defs/worksheet_line'}
 schema=obj(dict(observations=dict(type='array',minItems=len(steps),maxItems=len(steps),items=item)));schema['$defs']=deepcopy(ANSWER['$defs']);schema['$defs']['worksheet_line']=deepcopy(LINE);return schema
