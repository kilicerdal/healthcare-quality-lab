"""Bounded evidence assistant: deterministic findings, optional existing local AI planner.
No tools, approval authority, arbitrary commands or automatic execution.
"""
from healthcare_quality.coverage_packs import packs
from healthcare_quality.scenario_quality import inspect
from healthcare_quality.test_design import plan_from_case
from healthcare_quality.ai_schema import digest
from jsonschema import ValidationError

def cases_of(record):
 cases=record.get("cases",[])
 return cases if isinstance(cases,list) else []

def quality_of(case):
 try:return inspect(plan_from_case(case))
 except (ValidationError,ValueError,KeyError,TypeError,RecursionError):return dict(valid=False,ready=False,features=[],issues=[dict(code="INVALID_PLAN",detail="Saved proposal is structurally invalid; inspect original evidence before redesign")])

def explain(record):
 facts=[]
 for index,c in enumerate(cases_of(record)):
  quality=quality_of(c);case_id=str(c.get('id',index)) if isinstance(c,dict) else str(index);facts.append(dict(id=case_id,kind='scenario_check',features=quality['features'],issues=quality['issues'],citation='proposal:'+record['id']+':case:'+case_id))
 assessment=record.get('assessment',{})
 facts.append(dict(id='assessment',kind='independent_gate',valid=assessment.get('valid',False),matched=assessment.get('matched',False),review_ready=assessment.get('review_ready',False),citation='proposal:'+record['id']+':assessment'))
 for i,run in enumerate(record.get('runs',[])):
  facts.append(dict(id=f'run-{i}',kind='execution',passed=run['passed'],failed=run['failed'],citation='proposal:'+record['id']+f':runs:{i}'))
 return dict(kind='deterministic_evidence_assistant',proposal=record['id'],snapshot=digest(record.get('cases',[])),facts=facts,recommendations=[dict(action='inspect_issue',citation=f['citation'],issue=x) for f in facts for x in f.get('issues',[])],uncertainty='Findings describe supplied saved evidence. They do not establish real insurance compliance or prove a root cause.',can_approve=False,can_execute=False,live_model_calls=0)

def gap_analysis(records):
 covered=set()
 for r in records:
  for c in cases_of(r):
   if not quality_of(c)['valid']:continue
   for s in c['steps']:
    if s['action']=='submit':covered.add(s['data']['plan_id'])
 return dict(kind='deterministic_gap_assistant',proposed_packs=[dict(id=p['id'],reason='No submitted scenario in supplied proposal records',citation='pack:'+p['id']) for p in packs() if p['id'] not in covered],scope='Presence in proposal inputs only, not executed or passing coverage. No model calls.')
