"""Read-only reliability evidence, grounded failure packets and AI-only fault credit."""
from pathlib import Path
from copy import deepcopy
import hashlib,json
from healthcare_quality.ai_schema import digest
from healthcare_quality.advanced_reference import Oracle
from healthcare_quality.advanced_schema import duplicate_groups,semantic_key
from healthcare_quality.advanced_lab import check
from healthcare_quality.advanced_runner import run
from healthcare_quality import reliability_protocol as protocol
from healthcare_quality.deductible_evaluator import evaluate
from healthcare_quality.rule_review import review
from tools.fingerprints import source_hash

def authored_cases():
 """Explicit reference-authored engineering journeys; never counted as AI cases."""
 result=[]
 for task in protocol.cohort()['tasks']:
  case=deepcopy(task['plan']['case']);oracle=Oracle()
  for step in case['steps']:step['expect']=oracle.step(step)
  result.append(case)
 # Cross-claim credit must not reprice later claims; reset is by service year.
 base=deepcopy(protocol.cohort()['tasks'][9]['plan']['case'])
 base['id']='AB-J87-credit';base['title']='Shared family claims retain later allocations after credit'
 first=base['steps'][0]['data']['claim_id'];last=base['steps'][2]['data']['claim_id']
 base['steps']+= [protocol.step('pay',first,5,expected_revision=1),protocol.step('adjust',first,6,expected_revision=2,lines=[protocol.line(5001)]),protocol.step('reverse',first,7,expected_revision=3),protocol.step('read',last,8,member='M300')]
 reset=deepcopy(protocol.cohort()['tasks'][0]['plan']['case']);reset['id']='AB-J87-year';reset['title']='New service year gets separate allocations'
 prior=reset['steps'][0];prior['data']['lines'][0]['allowed_cents']=194217
 later=deepcopy(prior);later['data'].update(claim_id='CLAIM-J87-2027',operation_key='year-reset-J87',service_date='2027-01-01');later['data']['lines'][0]['allowed_cents']=17003
 reset['steps']=[prior,later,protocol.step('read',prior['data']['claim_id'],3)]
 for case in (base,reset):
  oracle=Oracle()
  for step in case['steps']:step['expect']=oracle.step(step)
  result.append(case)
 return result

def investigation(task,record):
 plan=next(t['plan'] for t in protocol.cohort()['tasks'] if t['id']==task)
 row=record['rows'][0];answer=row.get('first',{}).get('answer');assessment=evaluate(plan,answer) if answer else dict(eligible=False,error='No frozen complete answer')
 # Keep every step/account history, not only a speculative AI explanation.
 oracle=Oracle();history=[]
 for index,step in enumerate(plan['case']['steps'],1):history.append(dict(step=index,action=step['action'],request=step['data'],independent_observation=oracle.step(step)))
 facts=[]
 for mismatch in assessment.get('worksheet_mismatches',[]):facts.append(dict(id='F'+str(len(facts)+1),kind='model_expected_value_mismatch',detail=mismatch))
 for case in assessment.get('cases',[]):
  from healthcare_quality.advanced_reference import assess
  for step in assess(case)['steps']:
   for mismatch in step['mismatches']:facts.append(dict(id='F'+str(len(facts)+1),kind='observation_mismatch',step=step['step'],detail=mismatch))
 if not answer or not assessment.get('schema_valid',False):facts.append(dict(id='F1',kind='incomplete_model_output',detail=row.get('first',{}).get('error',record.get('error','No complete answer'))))
 return dict(task=task,source_hash=source_hash(),rules=plan['case']['rule_ids'],account_history=history,facts=facts,eligible=assessment.get('eligible',False),raw_model_calls=row['calls'],ai_explanation=None,label='Deterministic evidence packet; AI explanations remain optional hypotheses, never automatic fixes. Reference observations are post-freeze investigation only.')

def collect(study):
 study=Path(study);results=json.loads((study/'results.json').read_text());plan=json.loads((study/'plan.json').read_text())
 if results['plan_hash']!=digest(plan):raise ValueError('Plan integrity mismatch')
 if results['source_hash']!=source_hash():raise ValueError('Study source is stale; do not rescore as current')
 ai=[];packets=[];provenance=[]
 for entry in results['entries']:
  if not entry.get('file'):continue
  filename=entry['file']
  if Path(filename).name!=filename:raise ValueError('Invalid evidence filename')
  raw=(study/filename).read_bytes()
  if hashlib.sha256(raw).hexdigest()!=entry['sha256']:raise ValueError('Raw model evidence changed')
  record=json.loads(raw);row=record['rows'][0]
  from healthcare_quality.reliability_scorecard import scorecard
  if row['task_id']!=entry['task'] or scorecard(record)['outcomes'][0]['outcome']!=entry['outcome']:raise ValueError('Trial identity/outcome mismatch')
  if record['protocol']['source_hash']!=results['source_hash']:raise ValueError('Mixed source study')
  packets.append(investigation(entry['task'],record));p=record['protocol']
  provenance.append(dict(task=entry['task'],repeat=entry['repeat'],raw_file=filename,sha256=entry['sha256'],model_digests=p['model_digests'],settings=p['provider_settings'],profile=p['provider_profile'],prompt_hashes=p['prompt_hashes'],schema_hash=p['answer_schema_hash'],source_hash=p['source_hash'],calls=len(row['calls'])))
  if entry['role']=='fresh' and entry['outcome']=='first_pass':
   task=next(t for t in protocol.cohort()['tasks'] if t['id']==entry['task']);gate=evaluate(task['plan'],row['first']['answer'])
   if not gate.get('eligible'):raise ValueError('Previously passing model answer no longer passes')
   ai.extend(gate['cases'])
 unique=[];seen=set()
 for c in ai:
  key=semantic_key(c)
  if key not in seen:unique.append(c);seen.add(key)
 return results,unique,packets,provenance

def build(study):
 from healthcare_quality.effectiveness import variants,suite_run
 results,ai,packets,provenance=collect(study);authored=authored_cases();rows=[]
 for label,cases in [('ai_original_first_attempt',ai),('reference_authored_engineering',authored)]:
  row=dict(label=label,case_count=len(cases),scored=False,detected=0,total=len(variants()),trials=[])
  if cases:
   assert all(check([c])['review_ready'] for c in cases)
   baseline=suite_run(cases)
   if not baseline['passed']:raise ValueError('Unhealthy baseline cannot receive defect credit')
   for v in variants():
    observed=suite_run(cases,v);row['trials'].append(dict(mutant=v['id'],detected=not observed['passed'],witness=observed['witness']))
   row.update(scored=True,detected=sum(t['detected'] for t in row['trials']),survived=[t['mutant'] for t in row['trials'] if not t['detected']])
  else:row['reason']='No eligible frozen AI cases; no AI mutation score claimed'
  rows.append(row)
 actual=run(authored,'http')
 assert actual['failed']==0
 return dict(kind='reliability_dashboard',source_hash=source_hash(),study=results,rule_review=review(),journeys=dict(transport='actual HTTP',case_count=len(authored),passed=actual['passed'],failed=actual['failed'],execution=actual,authorship='reference-authored engineering; no AI credit'),defect_detection=rows,provenance=provenance,investigations=packets,duplicates=duplicate_groups(ai),ai_cases=ai,coverage=[dict(task=t['id'],scenario=t['plan']['case']['title'],actions=[s['action'] for s in t['plan']['case']['steps']],outcomes=[e['outcome'] for e in results['entries'] if e['task']==t['id']]) for t in protocol.cohort()['tasks']],release_decision='Engineering validation and independent human review must be considered separately; model failures stay blocked.',scope='AI-only defect credit excludes reference-authored and repaired cases; semantic duplicates removed. Scores from unequal suite sizes are not an AI superiority comparison.')

def seal(payload):return dict(payload=payload,content_hash=digest(payload))
def read(path):
 record=json.loads(Path(path).read_text())
 if digest(record['payload'])!=record.get('content_hash'):raise ValueError('Dashboard evidence integrity mismatch')
 result=deepcopy(record['payload']);result['matches_current_source']=result['source_hash']==source_hash();return result
