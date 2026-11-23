"""V8.3 development guidance. Raw historical predictions are never repaired."""
import json
from healthcare_quality.compact_expectations import ANSWER,parse,assemble,inputs,answer_schema,DATA
from healthcare_quality.compact_expectations import prompt as base_prompt
VERSION='compact-expectations-v83-1'
KIND='model_expectations_v83'
CHECKLIST="""V8.3 WORKSHEET CHECKLIST (rules, not numeric solutions):
1. Determine coverage BEFORE cost sharing. For a rejected line member_before_oop_cents, capped_member_cents, payer_after_oop_cents, member_cents and payout_cents are ALL ZERO. The eligible amount is noncovered; it is not pre-cap member cost. Never use eligible as member_before_oop on a rejected line.
2. Every remaining-cap field is the account snapshot IMMEDIATELY BEFORE THAT LINE, including rejected lines. Within a claim, a prior covered line has ALREADY increased used deductible/OOP/benefit before the next line starts. A rejected line leaves those updated accounts unchanged; it does not reset them to policy limits. Across claims, preserve current member/family/year balances.
3. Emit line worksheets in original input order. For each line: capture current used balances; write remaining caps; process that line; update used accounts; only then start the next line. Whole-claim starting limits are not every-line starting limits.
4. Keep observations and worksheets consistent. Final API expectations can be correct while a worksheet is wrong; both are independently checked. Never copy a reference answer or invent a correction tool."""
def cohort():return json.loads((DATA/'expectation_cohort_v83.json').read_text())
def prompt(plan,stage='first',original=None,step=None,previous=None):
 return base_prompt(plan,stage,original,step,previous)+'\n'+CHECKLIST
