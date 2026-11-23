"""Bounded sealed first-attempt study, repetition, provenance and honest partial results."""
import argparse,json,threading,time,statistics,hashlib,subprocess
from pathlib import Path
from healthcare_quality import reliability_protocol as protocol
from healthcare_quality.deductible_evaluator import evaluate
from healthcare_quality.reliability_scorecard import scorecard
from healthcare_quality.ollama_provider import CompactExpectationProvider
from healthcare_quality.ai_schema import digest
from healthcare_quality.ai_studio import StudioError
from tools.fingerprints import source_hash

REPEATS=('R87-03','R87-09')
def prepare():
 tasks=protocol.cohort()['tasks']
 return dict(version=protocol.VERSION,code_commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),source_hash=source_hash(),cohort_hash=digest(protocol.cohort()),model='qwen3.5:27b',case_max_seconds=180,admission_window_seconds=2100,max_calls=28,retries=0,resumes=0,corrections=0,trials=[dict(task=t['id'],repeat=1,role='fresh',inputs=protocol.inputs(t['plan'])) for t in tasks[:9]]+[dict(task=t,repeat=2,role='repeat_exposed') for t in REPEATS]+[dict(task=t['id'],repeat=1,role='fresh',inputs=protocol.inputs(t['plan'])) for t in tasks[9:]],scope='12 new scenarios once; two preselected repeats follow first nine simple cases before the final stateful cases; repeats excluded from fresh accuracy. Single frozen protocol. Stop after provider uncertainty or insufficient budget; retain all planned trials.')

def save(path,data):
 path=Path(path);temp=path.with_suffix(path.suffix+'.tmp');temp.write_text(json.dumps(data,indent=2)+'\n');temp.replace(path)

def summarize(plan,entries,elapsed):
 fresh=[e for e in entries if e['role']=='fresh'];repeats=[e for e in entries if e['role']=='repeat_exposed'];complete=len(fresh)==12 and all(e['outcome'] in ('first_pass','incorrect_values','invalid_output','nonfirst_pass') for e in fresh)
 lat=[e['provider_seconds'] for e in entries if e.get('provider_seconds') is not None];passed=sum(e['outcome']=='first_pass' for e in fresh)
 pairs=[dict(task=e['task'],both_passed=e['outcome']=='first_pass' and next(x for x in fresh if x['task']==e['task'])['outcome']=='first_pass',same_answer_hash=bool(e.get('answer_hash')) and e.get('answer_hash')==next(x for x in fresh if x['task']==e['task']).get('answer_hash')) for e in repeats]
 return dict(kind='sealed_reliability_study',source_hash=plan['source_hash'],plan_hash=digest(plan),entries=entries,fresh_planned=12,fresh_assessed=sum(e['outcome'] in ('first_pass','incorrect_values','invalid_output','nonfirst_pass') for e in fresh),fresh_passed=passed,fresh_complete=complete,fresh_percent=round(100*passed/12,2) if complete else None,repeat_pairs=pairs,actual_calls=sum(e.get('calls',0) for e in entries),provider_seconds_median=statistics.median(lat) if lat else None,provider_seconds_max=max(lat) if lat else None,elapsed_seconds=round(elapsed,2),reference_assisted_corrections=0,qualification=False,scope='Repeat consistency is distinct from unseen accuracy. Small synthetic cohort; no universal reliability claim. Missing, interrupted and invalid trials stay visible.')

def run(plan,output,state,lab=None,clock=time.monotonic):
 if plan!=prepare():raise ValueError('Sealed plan does not match current source/input cohort')
 output=Path(output);state=Path(state)
 if state.exists() or output.exists():raise ValueError('Fresh state and output required; no overwrite/resume')
 output.mkdir(parents=True);save(output/'plan.json',plan)
 lab=lab or protocol.LeanLab(state,CompactExpectationProvider(),threading.BoundedSemaphore(1),protocol=protocol,evaluator=evaluate)
 start=clock();entries=[];stop=None;identity=None
 for trial in plan['trials']:
  if not stop and source_hash()!=plan['source_hash']:stop='Source changed'
  if not stop and plan['admission_window_seconds']-(clock()-start)<plan['case_max_seconds']+5:stop='Insufficient full-case time budget'
  if not stop and sum(e.get('calls',0) for e in entries)+2>plan['max_calls']:stop='Call budget exhausted'
  entry=dict(task=trial['task'],repeat=trial['repeat'],role=trial['role'])
  if stop:entry.update(outcome='not_run',reason=stop)
  else:
   try:
    record=lab.start(dict(models=[plan['model']],tasks=[trial['task']],strategy='whole_case',repeats=1,self_review=False),max_seconds=plan['case_max_seconds'])
    card=scorecard(record);record['first_attempt_scorecard']=card;filename=trial['task']+'-r'+str(trial['repeat'])+'.json';save(output/filename,record)
    row=record['rows'][0];calls=[c for r in record['rows'] for c in r['calls']];current=digest({k:record['protocol'].get(k) for k in ('model_digests','provider_profile','provider_settings')})
    entry.update(outcome=card['outcomes'][0]['outcome'],calls=len(calls),file=filename,sha256=hashlib.sha256((output/filename).read_bytes()).hexdigest(),answer_hash=row.get('first',{}).get('assessment',{}).get('answer_hash'),provider_seconds=(sum(c.get('response',{}).get('latency_ms',0) or 0 for c in calls)/1000 if len(calls)==2 and all(c['phase']=='response_frozen' for c in calls) else None),record_id=record['id'])
    if identity is None:identity=current
    if identity!=current or source_hash()!=plan['source_hash']:entry['outcome']='protocol_changed';stop='Source or model identity/settings changed'
    if record['state']!='completed' or any(c['phase'] in ('provider_error','interrupted','request_running') for c in calls):stop='Provider uncertainty/interruption; no further requests'
   except StudioError as error:entry.update(outcome='preflight_error',reason=str(error),calls=0);stop='Preflight failed'
  entries.append(entry);save(output/'results.json',summarize(plan,entries,clock()-start))
 return summarize(plan,entries,clock()-start)

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--prepare',type=Path);ap.add_argument('--plan',type=Path);ap.add_argument('--output',type=Path);ap.add_argument('--state',type=Path);args=ap.parse_args()
 if args.prepare:
  with args.prepare.open('x') as f:json.dump(prepare(),f,indent=2);f.write('\n')
  print('Input-only plan sealed; zero inference.');return 0
 if not all((args.plan,args.output,args.state)):ap.error('Provide plan, output, state or --prepare')
 result=run(json.loads(args.plan.read_text()),args.output,args.state);print(json.dumps(result,indent=2));return 0 if result['fresh_complete'] and result['fresh_passed']==12 else 1
if __name__=='__main__':raise SystemExit(main())
