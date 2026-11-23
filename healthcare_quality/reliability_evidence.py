"""Read-only reliability evidence, grounded failure packets and AI-only fault credit."""
from pathlib import Path
from copy import deepcopy
import hashlib,json,subprocess,tarfile,io,re
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
 cap=deepcopy(protocol.cohort()['tasks'][9]['plan']['case']);cap['id']='AB-J87-family-oop';cap['title']='Family OOP exhaustion across three members'
 for step in cap['steps'][:3]:step['data']['lines'][0]['allowed_cents']=190013
 cap['steps']=cap['steps'][:3]+[protocol.step('pay',cap['steps'][2]['data']['claim_id'],4,member='M300',expected_revision=1),protocol.step('reverse',cap['steps'][2]['data']['claim_id'],5,member='M300',expected_revision=2),protocol.step('read',cap['steps'][1]['data']['claim_id'],6,member='M200')]
 for case in (cap,base,reset):
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

def source_compatibility(study_source,plan):
 """A post-study builder repair cannot silently relabel the frozen model source."""
 current=source_hash()
 if study_source==current:return dict(mode='exact_source',model_source=study_source,evaluation_source=current)
 commit=plan.get('code_commit','')
 if not re.fullmatch('[0-9a-f]{40}',commit):raise ValueError('Missing frozen Git commit')
 root=Path(__file__).resolve().parents[1]
 archive=subprocess.check_output(['git','archive',commit,'healthcare_quality','tests','tools','requirements.txt','requirements-dev.txt','pytest.ini','.github/workflows','.github/runner'],cwd=root)
 frozen={}
 def included(name):
  path=Path(name)
  return '__pycache__' not in path.parts and ((path.parts[0] in ('healthcare_quality','tests','tools') and path.suffix in ('.py','.json','.html','.css','.js')) or name in ('requirements.txt','requirements-dev.txt','pytest.ini') or name.startswith('.github/workflows/') and path.suffix in ('.yml','.yaml') or name.startswith('.github/runner/'))
 with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
  for member in tar.getmembers():
   if member.isfile() and included(member.name):frozen[member.name]=tar.extractfile(member).read()
 hashed=hashlib.sha256()
 for name in sorted(frozen):hashed.update(name.encode()+b'\0'+frozen[name]+b'\0')
 if hashed.hexdigest()!=study_source:raise ValueError('Frozen commit does not match model study source')
 current_files={str(f.relative_to(root)):f.read_bytes() for folder in ('healthcare_quality','tests','tools','.github/workflows','.github/runner') for f in (root/folder).rglob('*') if f.is_file() and included(str(f.relative_to(root)))}
 for name in ('requirements.txt','requirements-dev.txt','pytest.ini'):current_files[name]=(root/name).read_bytes()
 changed=sorted(name for name in set(frozen)|set(current_files) if frozen.get(name)!=current_files.get(name))
 allowed={'healthcare_quality/reliability_evidence.py','healthcare_quality/static/reliability.js','tests/unit/test_reliability_study.py'}
 if not changed or set(changed)-allowed:raise ValueError('Generation, evaluator or unrelated source changed; historical study cannot receive current credit')
 return dict(mode='postprocessing_only',frozen_commit=commit,model_source=study_source,evaluation_source=current,changed_paths=changed,generation_and_evaluator_files_unchanged=True,scope='Frozen model source retained; only evidence processing, authored engineering journeys, compatibility display and their tests changed. Original answers rechecked unchanged.')

def collect(study):
 study=Path(study);results=json.loads((study/'results.json').read_text());plan=json.loads((study/'plan.json').read_text())
 if results['plan_hash']!=digest(plan):raise ValueError('Plan integrity mismatch')
 source_compatibility(results['source_hash'],plan)
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
 executions=[run(authored[start:start+3],'http') for start in range(0,len(authored),3)]
 actual=dict(results=[case for execution in executions for case in execution['results']],passed=sum(x['passed'] for x in executions),failed=sum(x['failed'] for x in executions),actions=sum(x['actions'] for x in executions),transport='http',batches=len(executions))
 assert actual['failed']==0
 return dict(kind='reliability_dashboard',source_hash=source_hash(),study=results,source_compatibility=source_compatibility(results['source_hash'],json.loads((Path(study)/'plan.json').read_text())),rule_review=review(),journeys=dict(transport='actual HTTP',case_count=len(authored),passed=actual['passed'],failed=actual['failed'],execution=actual,authorship='reference-authored engineering; no AI credit'),defect_detection=rows,provenance=provenance,investigations=packets,duplicates=duplicate_groups(ai),ai_cases=ai,coverage=[dict(task=t['id'],scenario=t['plan']['case']['title'],actions=[s['action'] for s in t['plan']['case']['steps']],outcomes=[e['outcome'] for e in results['entries'] if e['task']==t['id']]) for t in protocol.cohort()['tasks']],release_decision='Engineering validation and independent human review must be considered separately; model failures stay blocked.',scope='AI-only defect credit excludes reference-authored and repaired cases; semantic duplicates removed. Scores from unequal suite sizes are not an AI superiority comparison.')

def seal(payload):return dict(payload=payload,content_hash=digest(payload))
def read(path):
 record=json.loads(Path(path).read_text())
 if digest(record['payload'])!=record.get('content_hash'):raise ValueError('Dashboard evidence integrity mismatch')
 result=deepcopy(record['payload']);result['matches_current_source']=result['source_hash']==source_hash();return result
