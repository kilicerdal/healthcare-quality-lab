"""Sealed first-attempt exercise: no retries, resumes, repair or result-based tuning."""
import argparse,json,threading,time
from pathlib import Path
from healthcare_quality import deductible_expectations as p
from healthcare_quality.ai_schema import digest
from healthcare_quality.ai_studio import StudioError
from healthcare_quality.expectation_scorecard_v86 import scorecard
from healthcare_quality.deductible_evaluator import evaluate
from healthcare_quality.ollama_provider import CompactExpectationProvider
from tools.fingerprints import source_hash
TASKS=('H85-02','H85-03','H86-01','H86-02')

def prepare():
 tasks={t['id']:t for t in p.cohort()['tasks']}
 return dict(version=p.VERSION,source_hash=source_hash(),cohort_hash=digest(p.cohort()),model='qwen3.5:27b',case_max_seconds=180,admission_window_seconds=600,max_calls=8,retries=0,resumes=0,self_review=False,trials=[dict(task=id,split=tasks[id]['split'],inputs=p.inputs(tasks[id]['plan'])) for id in TASKS],scope='Two exposed failed cases gate two fresh numeric variants. Fixed budget per case; no prompt/model/budget change after results. Not ten-input qualification.')

def run(plan,output,state,lab=None,clock=time.monotonic):
 sealed=prepare()
 if plan!=sealed:raise ValueError('Plan differs from frozen source, cohort or declared exercise')
 output=Path(output);state=Path(state)
 if state.exists() or any((output/(t['task']+'.json')).exists() for t in plan['trials']) or (output/'evaluation-results.json').exists():raise ValueError('Choose fresh state and output paths; never overwrite evidence')
 output.mkdir(parents=True,exist_ok=True)
 lab=lab or p.LeanLab(state,CompactExpectationProvider(),threading.BoundedSemaphore(1),protocol=p,evaluator=evaluate)
 started=clock();used=0;stop=None;entries=[];identity=None;stable=True;development_failed=False
 for trial in plan['trials']:
  if stop is None and trial['split']=='reserved_until_exposed' and development_failed:stop='Exposed development cases failed; fresh assessment not started'
  if stop is None and plan['admission_window_seconds']-(clock()-started)<plan['case_max_seconds']+5:stop='Insufficient full case budget plus preflight headroom remains'
  if stop is None and plan['max_calls']-used<2:stop='Insufficient request budget for one complete stage pair'
  if stop:
   entries.append(dict(task=trial['task'],split=trial['split'],outcome='not_run',reason=stop));continue
  try:r=lab.start(dict(models=[plan['model']],tasks=[trial['task']],strategy='whole_case',repeats=1,self_review=False),max_seconds=plan['case_max_seconds'])
  except StudioError as error:
   stop='Preflight/admission failed: '+str(error);entries.append(dict(task=trial['task'],split=trial['split'],outcome='preflight_error',reason=stop,calls=0));continue
  card=scorecard(r);r['first_attempt_scorecard']=card
  with (output/(trial['task']+'.json')).open('x') as f:json.dump(r,f,indent=2);f.write('\n')
  calls=sum(len(row['calls']) for row in r['rows']);used+=calls;entry=dict(task=trial['task'],split=trial['split'],record=r['id'],state=r['state'],calls=calls,outcome=card['outcomes'][0]['outcome']);current_identity=digest({k:r['protocol'].get(k) for k in ('model_digests','provider_profile','provider_settings')})
  if identity is None:identity=current_identity
  elif current_identity!=identity:stable=False;entry['outcome']='provider_changed';stop='Model digest/settings changed; do not pool results'
  if source_hash()!=plan['source_hash']:stable=False;entry['outcome']='source_changed';stop='Source changed; stop and retain evidence'
  entries.append(entry)
  with (output/'progress.json').open('w') as f:json.dump(dict(used_calls=used,entries=entries),f,indent=2)
  if trial['split']!='reserved_until_exposed' and entry['outcome']!='first_pass':development_failed=True
  if r['state']!='completed' or any(c['phase'] in ('provider_error','interrupted','request_running') for row in r['rows'] for c in row['calls']):stop='Interrupted/provider-error job: no further requests; backend cancellation is best effort'
  if source_hash()!=plan['source_hash']:stop='Source changed; stop and retain evidence'
 fresh=[e for e in entries if e['split']=='reserved_until_exposed'];complete=stable and all(e['outcome'] in ('first_pass','incorrect_values','invalid_output','nonfirst_pass') for e in fresh);passed=sum(e['outcome']=='first_pass' for e in fresh)
 result=dict(source_hash=plan['source_hash'],model=plan['model'],protocol_stable=stable,entries=entries,actual_calls=used,elapsed_seconds=round(clock()-started,2),fresh_planned=len(fresh),fresh_first_passes=passed,fresh_complete=complete,fresh_first_attempt_percent=round(100*passed/len(fresh),2) if complete and fresh else None,qualification=False,reference_assisted_corrections=0,scope='All planned fresh cases retained, including unattempted cases. No resume/retry. Known development case is separate. Timings are this run, not a controlled latency benchmark.')
 with (output/'evaluation-results.json').open('x') as f:json.dump(result,f,indent=2);f.write('\n')
 return result

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--prepare',type=Path);ap.add_argument('--plan',type=Path);ap.add_argument('--output-dir',type=Path);ap.add_argument('--state',type=Path);a=ap.parse_args()
 if a.prepare:
  with a.prepare.open('x') as f:json.dump(prepare(),f,indent=2);f.write('\n')
  print('Sealed input-only plan; no inference.');return 0
 if not a.plan or not a.output_dir or not a.state:ap.error('Provide --plan, --output-dir and --state, or --prepare')
 result=run(json.loads(a.plan.read_text()),a.output_dir,a.state);print(json.dumps(result,indent=2));return 0 if all(e['outcome']=='first_pass' for e in result['entries']) else 1
if __name__=='__main__':raise SystemExit(main())
