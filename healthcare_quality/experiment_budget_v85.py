"""Explicit operator budget with stage/shape-specific timing and censor warnings."""
import json,statistics
from healthcare_quality.experiment_budget import request as base_request
from healthcare_quality.expectation_lab import selection
from healthcare_quality.ai_studio import StudioError
from healthcare_quality import lean_expectations as p

def request(body):
 if not isinstance(body,dict) or 'max_seconds' not in body:raise StudioError('TIME_BUDGET_REQUIRED','Explicitly choose max_seconds between 1 and 300')
 return base_request(body)

def estimate(body,records,cohort=None):
 data,seconds=request(body);cohort=cohort or p.cohort();chosen=selection(data,cohort);tasks={t['id']:t for t in cohort['tasks']};samples={};censored={}
 for record in records:
  if record.get('protocol',{}).get('version')!=p.VERSION:continue
  for row in record['rows']:
   for call in row['calls']:
    meta=call.get('generation',{});phase=meta.get('phase')
    if phase not in ('pricing','lifecycle'):continue
    key=(row['model'],phase,json.dumps(meta.get('shape'),sort_keys=True));ms=call.get('response',{}).get('latency_ms')
    if call['phase']=='response_frozen' and type(ms) in (int,float) and ms>0:samples.setdefault(key,[]).append(ms/1000)
    elif (call['phase']=='provider_error' and 'timeout' in call.get('error','').lower()) or (call['phase']=='interrupted' and record.get('stop_reason')=='time_budget'):
     bound=call.get('elapsed_ms',0)/1000 or call.get('timeout_seconds',0) or 0;censored.setdefault(key,[]).append(bound)
 totals={'pricing':0.,'lifecycle':0.};details=[]
 for model in data['models']:
  for id in data['tasks']:
   plan=tasks[id]['plan'];ids=[s['step_id'] for s in p.inputs(plan)['steps']] if data['strategy']=='stepwise' else [None]
   scopes=ids+([None] if data['self_review'] else [])
   for step in scopes:
    spec=json.loads(p.prompt(plan,step=step));shape=p.shape(spec)
    for phase in totals:
     key=(model,phase,json.dumps(shape,sort_keys=True));history=samples.get(key,[]);timeouts=censored.get(key,[]);fallback=(130 if phase=='pricing' else 90) if model=='qwen3.5:27b' else 15
     value=max(statistics.median(history) if history else fallback,max(timeouts,default=0));totals[phase]+=value*data['repeats'];details.append(dict(model=model,task=id,step=step,phase=phase,shape=shape,seconds=round(value,1),samples=len(history),timeouts=len(timeouts),basis='same-version stage/shape completed-response median' if history else 'conservative stage fallback; not measured V8.5 latency'))
 total=round(sum(totals.values()),1)
 return dict(request_budget=chosen['request_budget'],estimated_seconds=total,stage_totals={k:round(v,1) for k,v in totals.items()},max_seconds=seconds,estimate_fits_budget=total<=seconds,details=details,estimate_basis='Stage and input-shape timing. Timeout observations are censored lower bounds, not successful fast responses. Samples may use different recorded model digests/hardware; not a completion guarantee.',budget_scope='Operator-selected admission-time wall clock; preflight separate, backend cancellation best effort.')
