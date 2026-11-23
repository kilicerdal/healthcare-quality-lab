"""Durable model-only trials. Blind self review precedes all independent scoring."""
from copy import deepcopy,copy
from itertools import product
from pathlib import Path
from uuid import uuid4
import json,threading,time,statistics
from healthcare_quality.expectation_protocol import cohort,prompt,parse,ANSWER,VERSION,inputs,answer_schema
from healthcare_quality.ai_studio import ExperimentStore,StudioError,now
from healthcare_quality.ai_schema import MODELS,digest
from healthcare_quality.advanced_lab import contract_hash
from healthcare_quality import operations
from tools.fingerprints import source_hash

def selection(body,data=None):
 if not isinstance(body,dict) or set(body)!={'models','tasks','repeats','strategy','self_review'}:raise StudioError('INVALID_REQUEST','Provide models,tasks,repeats,strategy,self_review')
 tasks={t['id']:t for t in (data or cohort())['tasks']}
 for key,allowed in (('models',MODELS),('tasks',tasks)):
  values=body[key]
  if not isinstance(values,list) or not values or any(type(v) is not str or v not in allowed for v in values) or len(set(values))!=len(values):raise StudioError('INVALID_REQUEST','Select unique known '+key)
 if type(body['repeats']) is not int or not 1<=body['repeats']<=2 or body['strategy'] not in ('whole_case','stepwise') or type(body['self_review']) is not bool:raise StudioError('INVALID_REQUEST','Choose 1–2 trials, whole_case/stepwise and explicit self_review boolean')
 requests=len(body['models'])*body['repeats']*sum((len(tasks[id]['plan']['case']['steps']) if body['strategy']=='stepwise' else 1)+int(body['self_review']) for id in body['tasks'])
 if requests>24:raise StudioError('BUDGET_EXCEEDED','At most 24 model requests, including every step and self review')
 return dict(**deepcopy(body),request_budget=requests)

def summary(rows):
 result=[]
 for model in sorted({r['model'] for r in rows}):
  items=[r for r in rows if r['model']==model]
  for stage in ('first','self_review'):
   selected=[r for r in items if stage=='first' or r.get('self_review_requested')];assessed=[r for r in selected if r.get(stage,{}).get('assessment') is not None];correct=sum(r[stage]['assessment'].get('eligible',False) for r in assessed);calls=[c for r in selected for c in r['calls'] if c['stage']==stage];latencies=[c['response']['latency_ms'] for c in calls if c.get('response',{}).get('latency_ms') is not None];hashes={}
   for r in assessed:hashes.setdefault(r['task_id'],[]).append(r[stage]['assessment'].get('answer_hash'))
   unique={r['task_id'] for r in selected};heldout={r['task_id'] for r in selected if r['split']=='reserved_until_exposed'}
   result.append(dict(model=model,stage=stage,trials=len(selected),unique_tasks=len(unique),unique_heldout_tasks=len(heldout),assessed=len(assessed),not_assessed=len(selected)-len(assessed),eligible=correct,strict_percent=round(100*correct/len(selected),2) if selected else None,schema_valid=sum(r[stage]['assessment'].get('schema_valid',False) for r in assessed),observations_correct=sum(r[stage]['assessment'].get('observations_correct',False) for r in assessed),calculations_correct=sum(r[stage]['assessment'].get('calculations_correct',False) for r in assessed),input_preservation='immutable server assembly; model cannot supply inputs',provider_errors=sum(c['phase']=='provider_error' for c in calls),unknown_requests=sum(c['phase'] in ('request_running','interrupted') for c in calls),model_calls=len(calls),latency_median_ms=statistics.median(latencies) if latencies else None,input_tokens=sum(c.get('response',{}).get('input_tokens') or 0 for c in calls),output_tokens=sum(c.get('response',{}).get('output_tokens') or 0 for c in calls),stable_repeated_tasks=sum(len(v)>1 and None not in v and len(set(v))==1 for v in hashes.values()),repeated_tasks=sum(len(v)>1 for v in hashes.values()),target_percent=80,target_met=bool(len(heldout)>=10 and selected and all(r['phase']=='assessed' for r in selected) and correct/len(selected)>=.8),mode='experimental',reference_assisted_corrections=0))
 for group in result:
  selected=[r for r in rows if r['model']==group['model'] and (group['stage']=='first' or r.get('self_review_requested'))];calls=[c for r in selected for c in r['calls'] if c['stage']==group['stage']];elapsed=sorted(c['elapsed_ms'] for c in calls if c.get('elapsed_ms') is not None)
  group.update(worksheet_mismatch_trials=sum(a.get('schema_valid',False) and a.get('calculations_correct') is False for row in selected for a in [row.get(group['stage'],{}).get('assessment',{})]),timeout_requests=sum(c['phase']=='provider_error' and 'timeout' in c.get('error','').lower() for c in calls),schema_failure_trials=sum(bool(r.get(group['stage'],{}).get('error')) and r.get(group['stage'],{}).get('error')!='provider_error' for r in selected),incorrect_observation_trials=sum(a.get('schema_valid',False) and not a.get('observations_correct',False) for r in selected for a in [r.get(group['stage'],{}).get('assessment',{})]),elapsed_median_ms=statistics.median(elapsed) if elapsed else None,elapsed_max_ms=max(elapsed) if elapsed else None)
  group['planned_progress_percent']=group['strict_percent']
  if any(row['phase']!='assessed' for row in selected):group['strict_percent']=None
 return result

class ExpectationLab:
 def __init__(self,path,provider,lock,protocol=None,evaluator=None):
  from healthcare_quality import expectation_protocol
  self.protocol=protocol or expectation_protocol;self.evaluator=evaluator;self.store=ExperimentStore(path);self.provider=provider;self.lock=lock;self.recover()
 def recover(self):
  with self.store.transaction() as db:
   for raw, in db.execute('SELECT record_json FROM ai_experiments'):
    r=json.loads(raw)
    if r['state']=='running':
     lease=db.execute('SELECT expires_at FROM studio_operations WHERE experiment_id=?',(r['id'],)).fetchone()
     budget_expired=bool(r.get('budget',{}).get('deadline_epoch',float('inf'))<=time.time())
     if budget_expired or not lease or lease[0]<=time.time():
      if budget_expired:r['stop_reason']='time_budget'
      r.update(state='interrupted',error='TOTAL_TIME_BUDGET_EXCEEDED' if budget_expired else 'Expired lease; raw answers, exposure and unknown requests retained')
      if budget_expired:r['budget'].update(expired=True,ended_epoch=time.time())
      for row in r['rows']:
       for call in row['calls']:
        if call['phase']=='request_running':call['phase']='interrupted'
      r['summary']=summary(r['rows']);db.execute('DELETE FROM studio_operations WHERE experiment_id=?',(r['id'],));self.store.save(db,r)
 def get(self,id):self.recover();return self.store.get(id)
 def records(self):
  self.recover()
  with self.store.transaction() as db:return [json.loads(r[0]) for r in db.execute('SELECT record_json FROM ai_experiments ORDER BY created_at DESC LIMIT 30')]
 def start(self,body,background=False,max_seconds=None):
  if max_seconds is not None and (type(max_seconds) is not int or not 1<=max_seconds<=300):raise StudioError('INVALID_TIME_BUDGET','Choose integer max_seconds between1and300')
  s=selection(body,self.protocol.cohort());data=self.protocol.cohort();metadata=self.provider.status();installed={m['name'] for m in metadata['models']}
  if not set(s['models'])<=installed:raise StudioError('MODEL_UNAVAILABLE','Choose installed local models; no download or cloud fallback',409)
  protocol=dict(version=self.protocol.VERSION,selection=s,source_hash=source_hash(),contract_hash=contract_hash(),cohort_hash=digest(data),installed_models=metadata['models'],model_digests={m['name']:m.get('digest') for m in metadata['models'] if m['name'] in s['models']},provider_settings=deepcopy(getattr(self.provider,'settings',{})),request_timeout_seconds=getattr(self.provider,'timeout',None),provider_profile=getattr(self.provider,'profile',type(self.provider).__name__),native_reasoning=getattr(self.provider,'reasoning_enabled',False),target=data['target'],prompt_hashes={t['id']:digest(self.protocol.prompt(t['plan'])) for t in data['tasks'] if t['id'] in s['tasks']},answer_schema_hash=digest(self.protocol.ANSWER),evaluation_timing='Only after original and optional blind self-review responses are frozen',scope='No expected values, reference feedback, SUT responses or arithmetic tools supplied. First and self review scored separately; immutable input assembly does not measure model input-following skill.')
  r=dict(id=uuid4().hex,created_at=now(),kind=getattr(self.protocol,'KIND','model_expectations_v81'),state='running',protocol=protocol,rows=[],summary=[],approval=None)
  tasks={t['id']:t for t in data['tasks']}
  r['rows']=[dict(model=m,task_id=id,split=tasks[id]['split'],repeat=repeat,calls=[],self_review_requested=s['self_review'],phase='pending') for m,id,repeat in product(s['models'],s['tasks'],range(1,s['repeats']+1))]
  with self.store.transaction() as db:
   if db.execute('SELECT 1 FROM studio_operations WHERE expires_at>?',(time.time(),)).fetchone():raise StudioError('EXPERIMENT_BUSY','Another expectation experiment is active',409)
   old=[json.loads(row[0]) for row in db.execute('SELECT record_json FROM ai_experiments')];exposed={t for p in old if p['protocol']['cohort_hash']==protocol['cohort_hash'] for t in p['protocol']['selection']['tasks']};r['previously_exposed_tasks']=sorted(exposed&set(s['tasks']));
   if max_seconds is not None:r['budget']=dict(max_seconds=max_seconds,admitted_epoch=time.time(),deadline_epoch=time.time()+max_seconds,scope='Admitted job wall clock; preflight/model status is separate. Backend cancellation is best effort; late output is fenced.')
   token=operations.start(db,r,'expectations-only',30);db.execute('INSERT INTO ai_experiments VALUES(?,?,?)',(r['id'],r['created_at'],json.dumps(r)))
  if max_seconds is not None:
   timer=threading.Timer(max_seconds,self._expire,args=(r['id'],));timer.daemon=True
   def bounded_work():
    try:self._work(r,token)
    finally:timer.cancel()
   worker=threading.Thread(target=bounded_work,daemon=True);timer.start();worker.start()
   if not background:
    while worker.is_alive():
     worker.join(.02)
     if self.store.get(r['id'])['state']!='running':break
  elif background:threading.Thread(target=self._work,args=(r,token),daemon=True).start()
  else:self._work(r,token)
  return self.store.get(r['id'])
 def _save(self,r,token,final=False):
  r['summary']=summary(r['rows'])
  with self.store.transaction() as db:
   lease=db.execute('SELECT expires_at FROM studio_operations WHERE token=?',(token,)).fetchone()
   if not lease or lease[0]<=time.time():raise operations.LeaseLost('Late model completion fenced')
   if final:operations.finish(db,r,token)
   self.store.save(db,r)
 def cancel(self,id):
  with self.store.transaction() as db:
   r=self.store.load(db,id)
   if r['state']!='running':raise StudioError('NOT_RUNNING','No active expectation request',409)
   r.update(state='interrupted',error='Explicit cancellation; late response cannot complete the record')
   for row in r['rows']:
    for call in row['calls']:
     if call['phase']=='request_running':call['phase']='interrupted'
   r['summary']=summary(r['rows']);db.execute('DELETE FROM studio_operations WHERE experiment_id=?',(id,));self.store.save(db,r);return r
 def _expire(self,id):
  with self.store.transaction() as db:
   r=self.store.load(db,id)
   if r['state']!='running':return
   r.update(state='interrupted',stop_reason='time_budget',error='TOTAL_TIME_BUDGET_EXCEEDED: remaining work was not run; late output is fenced')
   r['budget'].update(expired=True,ended_epoch=time.time())
   for row in r['rows']:
    for call in row['calls']:
     if call['phase']=='request_running':call['phase']='interrupted'
   r['summary']=summary(r['rows']);db.execute('DELETE FROM studio_operations WHERE experiment_id=?',(id,));self.store.save(db,r)
 def _call(self,r,row,stage,text,token,schema):
  if r['protocol']['source_hash']!=source_hash() or r['protocol']['cohort_hash']!=digest(self.protocol.cohort()) or r['protocol']['contract_hash']!=contract_hash():raise ValueError('Source/cohort/contract changed during inference')
  if sum(len(x['calls']) for x in r['rows'])>=r['protocol']['selection']['request_budget']:raise ValueError('Request budget exhausted')
  provider=self.provider
  if r.get('budget'):
   remaining=r['budget']['deadline_epoch']-time.time()
   if remaining<=0:self._expire(r['id']);raise operations.LeaseLost('Total time budget ended')
   provider=copy(self.provider)
   if hasattr(provider,'timeout'):provider.timeout=min(provider.timeout,remaining)
  started=time.monotonic();call=dict(timeout_seconds=getattr(provider,'timeout',None),started_at=now(),stage=stage,prompt=text,prompt_hash=digest(text),generation_schema=deepcopy(schema),schema_hash=digest(schema),phase='request_running');row['calls'].append(call);self._save(r,token)
  try:response=provider.generate(row['model'],text,schema)
  except Exception as e:
   call.update(elapsed_ms=round((time.monotonic()-started)*1000,2),phase='provider_error',error=(type(e).__name__+': '+str(e))[:900])
   if getattr(e,'raw_response',None) is not None:call['provider_raw']=e.raw_response
   self._save(r,token);return None
  call.update(elapsed_ms=round((time.monotonic()-started)*1000,2),phase='response_frozen',response=response);self._save(r,token);return response
 def _work(self,r,token):
  acquired=False
  try:
   with operations.keepalive(self.store.path,token,30,5):
    if not self.lock.acquire(False):raise StudioError('MODEL_BUSY','Another local model job is active',429)
    acquired=True;s=r['protocol']['selection'];tasks={t['id']:t for t in self.protocol.cohort()['tasks']}
    for row in r['rows']:
     plan=tasks[row['task_id']]['plan'];row['phase']='predicting';observations=[];raw=[];first_error=None
     ids=[None] if s['strategy']=='whole_case' else [x['step_id'] for x in self.protocol.inputs(plan)['steps']]
     for step in ids:
      response=self._call(r,row,'first',self.protocol.prompt(plan,step=step,previous=observations),token,self.protocol.answer_schema(plan,step))
      if response is None:first_error='provider_error';break
      raw.append(response['text'])
      try:
       answer=self.protocol.parse(response['text'])
       if step is not None and [o['step_id'] for o in answer['observations']]!=[step]:raise ValueError('Stepwise response must contain only requested step')
       observations.extend(answer['observations'])
      except Exception as e:first_error=type(e).__name__;break
     first=dict(observations=observations);row['first']=dict(answer=first,error=first_error);self._save(r,token)
     if s['self_review'] and raw:
      original=dict(original_responses=raw) # Original model text only; no assessment or feedback.
      response=self._call(r,row,'self_review',self.protocol.prompt(plan,'self_review',original=original),token,self.protocol.answer_schema(plan))
      if response is not None:
       try:row['self_review']=dict(answer=self.protocol.parse(response['text']))
       except Exception as e:row['self_review']=dict(error=type(e).__name__)
     row['phase']='responses_frozen';self._save(r,token)
     # Independent evaluation is deliberately loaded only after both model stages.
     from healthcare_quality.expectation_evaluator import evaluate
     for stage in ('first','self_review'):
      if row.get(stage,{}).get('answer') is not None and not row[stage].get('error'):row[stage]['assessment']=(self.evaluator or evaluate)(plan,row[stage]['answer'])
     row['phase']='assessed';self._save(r,token)
    if r['protocol']['source_hash']!=source_hash():raise ValueError('Source changed before experiment completion')
    r['state']='completed'
  except operations.LeaseLost:return
  except Exception as e:r.update(state='failed',error=type(e).__name__+': '+str(e)[:800])
  finally:
   if acquired:self.lock.release()
   try:self._save(r,token,True)
   except operations.LeaseLost:pass


def aggregate(records):
 if not records:raise ValueError('Choose completed frozen experiment records')
 if any(r.get('budget',{}).get('max_seconds')!=records[0].get('budget',{}).get('max_seconds') for r in records):raise ValueError('Do not pool different total time budgets')
 first=records[0]['protocol'];keys=('version','source_hash','contract_hash','cohort_hash','provider_settings','model_digests','provider_profile','native_reasoning','answer_schema_hash')
 if any(any(k not in r['protocol'] for k in keys) for r in records):raise ValueError('Incomplete frozen protocol metadata')
 if any(any(r['protocol'][k]!=first[k] for k in keys) or r['protocol']['selection']['strategy']!=first['selection']['strategy'] or r['protocol']['selection']['self_review']!=first['selection']['self_review'] or r['protocol'].get('request_timeout_seconds')!=first.get('request_timeout_seconds') for r in records):raise ValueError('Do not pool different protocols, source versions or strategies')
 rows=[row for r in records for row in r['rows'] if row['split']=='reserved_until_exposed'];ids=[(r['model'],r['task_id'],r['repeat']) for r in rows]
 if len(ids)!=len(set(ids)):raise ValueError('Duplicate trial identities; do not inflate sample size')
 complete=all(r['state']=='completed' for r in records);groups=summary(rows)
 if not complete:
  for g in groups:g['target_met']=False
 return dict(protocol_version=first['version'],source_hash=first['source_hash'],cohort_hash=first['cohort_hash'],records=[r['id'] for r in records],complete=complete,summary=groups,scope='Reserved cases only; all planned trial rows remain denominators. First and blind self-review results are separate. 80 percent requires at least 10 unique reserved inputs per model. Correlated repeats do not enlarge the unique sample.')
