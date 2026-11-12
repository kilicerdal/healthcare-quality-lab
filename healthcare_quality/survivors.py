"""Deterministic survivor targeting; AI supplies case expectations, not coverage credit."""
from copy import deepcopy
from healthcare_quality.ai_schema import digest
from healthcare_quality.evaluation import signature

VERSION='survivor-targets-v2'
EVALUATOR_RULES=['HC-002','HC-003','HC-004','HC-005','HC-006','HC-007']
WORKFLOW_RULES=['WF-001','WF-002','WF-003','WF-004','WF-005']

def generation_groups(survivors,variant=False):
    amount=154321 if variant else 112345
    evaluations=[
        {'plan_id':'medicare_b' if variant else 'commercial_ppo','service':'medical','amount_cents':amount,'active':False},
        {'plan_id':'medicare_a' if variant else 'medicare_b','service':'dental','amount_cents':amount},
        {'plan_id':'commercial_hmo','service':'medical','amount_cents':amount,'in_network':False},
        {'plan_id':'medicare_a' if variant else 'medicare_advantage','service':'skilled_nursing' if variant else 'hospital','amount_cents':amount,'authorized':False},
        {'plan_id':'medicare_d','service':'prescription','amount_cents':amount,'formulary':False},
        {'plan_id':'medicare_b' if variant else 'commercial_ppo','service':'outpatient' if variant else 'medical','amount_cents':amount},
        {'plan_id':'medicare_a' if variant else 'commercial_ppo','service':'hospital' if variant else 'medical','amount_cents':310777 if variant else 245678}]
    evaluator=[{'action':'evaluate','actor':'none','data':data} for data in evaluations]
    claim='VAR-200' if variant else 'SURV-561';member='M200' if variant else 'M100';customer='customer-m200' if variant else 'customer-m100';other='customer-m100' if variant else 'customer-m200'
    submit={'claim_id':claim,'member_id':member,'service':'medical','amount_cents':156789 if variant else 112345}
    workflow=[{'action':'submit','actor':customer,'data':submit},
        {'action':'read','actor':other,'data':{'claim_id':claim}},
        {'action':'submit','actor':customer,'data':deepcopy(submit)},
        {'action':'read','actor':customer,'data':{'claim_id':claim}},
        {'action':'transition','actor':'finance-demo','data':{'claim_id':claim,'target':'paid'}},
        {'action':'read','actor':customer,'data':{'claim_id':claim}},
        {'action':'transition','actor':'adjuster-demo','data':{'claim_id':claim,'target':'approved'}},
        {'action':'transition','actor':'finance-demo','data':{'claim_id':claim,'target':'paid'}}]
    result=[]
    for id,rules,steps,prefix in [('evaluator',EVALUATOR_RULES,evaluator,'eval-'),('workflow',WORKFLOW_RULES,workflow,'workflow-')]:
        targets=[f for f in survivors if f.startswith(prefix)]
        if targets:result.append({'id':id,'source_ids':rules,'steps':steps,'target_fault_ids':targets,'variant':variant,
            'purpose':'Activate each relevant written rule separately; later denials must not mask the targeted rule.' if id=='evaluator' else 'Observe ownership, duplicate rejection/readback, forbidden early payment/readback, approval and positive ledger/history within eight steps.',
            'outcome_guidance':(['Each evaluate is stateless. Reset omitted flags to true on every step.','Steps 1-5 are independently denied for INACTIVE_POLICY, SERVICE_NOT_COVERED, OUT_OF_NETWORK, AUTH_REQUIRED, NON_FORMULARY respectively. HTTP status remains 200, payout is zero.','Steps 6 and 7 are approved / COVERED: calculate their payouts separately using deductible then payout cap. Do not carry inactive=false from step 1.'] if id=='evaluator' else ['Step 1: submit succeeds, status 201, submitted, revision/events 1; payment null.','Step 2: other customer read is 403 FORBIDDEN; error response has no state/money fields.','Step 3: duplicate submit is 409 DUPLICATE_CLAIM; step 4 owner read is unchanged submitted evidence.','Step 5: finance has the correct payment role but the claim is not approved. Expect 409 INVALID_TRANSITION, not 403. Step 6 owner read is unchanged submitted evidence.','Step 7: adjuster approval succeeds with revision/events 2 and null payment. Step 8: finance payment succeeds with revision/events 3 and payment exactly equal to the positive stored payout.','Rejections and reads do not add revisions or events. Calculate payout from this member plan and amount; do not copy a different example amount.']),
            'matching_scope':'Exact action/actor/data sequence with equivalent omitted true flags and consistently renamed valid claim IDs. Every selected rule must be cited.'})
    return result

def group_match(group,case):
    from healthcare_quality.coverage_lab import scenario_hash
    return isinstance(case,dict) and isinstance(case.get('rule_ids'),list) and set(case['rule_ids'])==set(group['source_ids']) and scenario_hash(case)==scenario_hash({'steps':group['steps']})

def compare(before,after):
    from healthcare_quality.ai_studio import StudioError
    required=('source_hash','contract_fingerprint','reference_fingerprint','assertion_policy_fingerprint')
    if any(r.get('coverage_kind')!='defect_score' or r.get('state')!='scored' or r.get('errors') for r in (before,after)):raise StudioError('INVALID_COMPARISON','Compare two completed error-free defect scores',409)
    if any(before.get(k)!=after.get(k) for k in required):raise StudioError('INCOMPATIBLE_SCORES','Scores must use the same implementation, contract, reference and assertion policy',409)
    if any(f['status'] not in ('detected','survived','not_applicable') for r in (before,after) for f in r['faults']):raise StudioError('INVALID_COMPARISON','Fault results must not contain errors or unknown statuses',409)
    a={f['id']:f for f in before['faults']};b={f['id']:f for f in after['faults']}
    if set(a)!=set(b) or any((a[id]['status']=='not_applicable')!=(b[id]['status']=='not_applicable') for id in a):raise StudioError('INCOMPATIBLE_SCORES','Profile sets and applicable denominators must match',409)
    rows=[{'id':id,'rule_id':a[id]['rule_id'],'before':a[id]['status'],'after':b[id]['status']} for id in a]
    return {'before_id':before['id'],'after_id':after['id'],'before_detected':before['detected'],'after_detected':after['detected'],'applicable':before['applicable'],
            'before_origins':{origin:sum(c['origin']==origin for c in before['cases']) for origin in sorted({c['origin'] for c in before['cases']})},
            'after_origins':{origin:sum(c['origin']==origin for c in after['cases']) for origin in sorted({c['origin'] for c in after['cases']})},
            'newly_detected':[r['id'] for r in rows if r['before']=='survived' and r['after']=='detected'],
            'regressed':[r['id'] for r in rows if r['before']=='detected' and r['after']=='survived'],
            'still_survived':[r['id'] for r in rows if r['after']=='survived'],'profiles':rows,
            'scope':'Before/after on identical known fault profiles and implementation. Not a blind accuracy benchmark or exhaustive mutation score.'}
