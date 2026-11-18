"""Frozen, no-repair, repeated local-model evaluation with persisted exposure evidence."""
from pathlib import Path
from copy import deepcopy
from datetime import datetime,timezone
import json,statistics,threading,time
from uuid import uuid4
from jsonschema import Draft202012Validator
from healthcare_quality import focused,operations,reference
from healthcare_quality.ai_schema import MODELS,digest,generation_schema,json_loads
from healthcare_quality.ai_studio import ExperimentStore,StudioError,checked_cases
from healthcare_quality.ollama_provider import OllamaProvider,SETTINGS
DATASET=Path(__file__).with_name('data')/'reserved_v58.json'
def dataset():return json_loads(DATASET.read_text())
def stamp():return datetime.now(timezone.utc).isoformat()
def summary(rows):
    groups={}
    for row in rows:
        key=row['model'];groups.setdefault(key,[]).append(row)
    result={}
    for model,items in groups.items():
        lat=sorted(x['latency_ms'] for x in items);by_task={}
        for x in items:by_task.setdefault(x['task_id'],[]).append(x['correct'])
        n=len(items);passed=sum(x['correct'] for x in items)
        # Wilson interval is descriptive; repeated identical inputs are not independent samples.
        z=1.96;den=1+z*z/n;center=(passed/n+z*z/(2*n))/den;half=z*((passed/n*(1-passed/n)/n+z*z/(4*n*n))**.5)/den
        result[model]=dict(requests=n,correct=passed,errors=sum(bool(x.get('error')) for x in items),rate=passed/n,latency_median_ms=statistics.median(lat),latency_p95_ms=lat[max(0,__import__('math').ceil(.95*n)-1)],stable_tasks=sum(all(v==vals[0] for v in vals) for vals in by_task.values()),tasks=len(by_task),wilson_95=[max(0,center-half),min(1,center+half)],interval_limit='Descriptive only; repeated tasks and deterministic seeds are correlated.')
    return result
class ReliabilityLab:
    def __init__(self,path,provider=None,generation_lock=None):
        self.store=ExperimentStore(path);self.provider=provider or OllamaProvider();self.lock=threading.Lock();self.generation_lock=generation_lock or threading.BoundedSemaphore(1)
        self.recover()
    def recover(self):
        with self.store.transaction() as db:
            for row in db.execute('SELECT record_json FROM ai_experiments'):
                r=json_loads(row['record_json'])
                if r['state']=='running':
                    lease=db.execute('SELECT expires_at FROM studio_operations WHERE experiment_id=?',(r['id'],)).fetchone()
                    if not lease or lease[0]<=time.time():
                        r.update(state='interrupted',error='Heartbeat expired; partial observations retained. Start a new explicit batch.');self.store.save(db,r);db.execute('DELETE FROM studio_operations WHERE experiment_id=?',(r['id'],))
    def records(self):
        self.recover()
        with self.store.transaction() as db:return [json_loads(x[0]) for x in db.execute('SELECT record_json FROM ai_experiments ORDER BY created_at DESC LIMIT 50')]
    def start(self,body,background=True):
        if not isinstance(body,dict) or set(body)!={'models','task_ids','repeats'}:raise StudioError('INVALID_REQUEST','Provide models, task_ids and repeats')
        models,ids,repeats=body['models'],body['task_ids'],body['repeats'];tasks={t['id']:t for t in dataset()['tasks']}
        if not isinstance(models,list) or not 1<=len(models)<=3 or any(type(m) is not str or m not in MODELS for m in models) or len(set(models))!=len(models) or not isinstance(ids,list) or not 1<=len(ids)<=8 or any(type(i) is not str or i not in tasks for i in ids) or len(set(ids))!=len(ids) or type(repeats) is not int or not 1<=repeats<=3 or len(models)*len(ids)*repeats>24:raise StudioError('INVALID_REQUEST','Select known unique models/tasks; 1–3 repeats and at most 24 requests')
        if not self.lock.acquire(False):raise StudioError('EVALUATION_BUSY','A reliability batch is running',409)
        try:
            d=dataset();fp=digest(d);previous=self.records();r=dict(id=uuid4().hex,kind='reliability',created_at=stamp(),state='running',dataset_version=d['version'],dataset_hash=fp,first_exposure=not any(x['dataset_hash']==fp for x in previous),models=models,task_ids=ids,repeats=repeats,rows=[],summary={},reference_fingerprint=reference.fingerprint(),protocol_hash=focused.protocol_hash(),settings=deepcopy(SETTINGS),scope=d['scope'])
            with self.store.transaction() as db:
                for lease in db.execute('SELECT experiment_id FROM studio_operations WHERE expires_at>?',(time.time(),)):
                    prior=self.store.load(db,lease[0])
                    if prior.get('kind')=='reliability':raise StudioError('EVALUATION_BUSY','Another worker owns the reliability lease',409)
                r['first_exposure']=not any(json_loads(row[0]).get('dataset_hash')==fp for row in db.execute('SELECT record_json FROM ai_experiments'))
                token=operations.start(db,r,'reliability',30);db.execute('INSERT INTO ai_experiments VALUES(?,?,?)',(r['id'],r['created_at'],json.dumps(r)))
        except BaseException:self.lock.release();raise
        if background:threading.Thread(target=self._run,args=(r,token,tasks),daemon=True).start()
        else:self._run(r,token,tasks)
        return self.store.get(r['id'])
    def _run(self,r,token,tasks):
        try:
            with operations.keepalive(self.store.path,token,30,5):
                for model in r['models']:
                    for repeat in range(r['repeats']):
                        for id in r['task_ids']:
                            if focused.protocol_hash()!=r['protocol_hash'] or reference.fingerprint()!=r['reference_fingerprint']:raise ValueError('Protocol/reference changed; partial results retained')
                            t=tasks[id];ctx=focused.context_for(t['data']);prompt,schema=focused.prepare(ctx,generation_schema(1,ctx['source_ids']));row=dict(task_id=id,model=model,repeat=repeat+1,prompt_hash=digest(prompt),schema_hash=digest(schema),correct=False,error=None,raw=None);at=time.monotonic()
                            try:
                                if not self.generation_lock.acquire(False):raise StudioError('MODEL_BUSY','Another inference is active',429)
                                try:row['raw']=self.provider.generate(model,prompt,schema)
                                finally:self.generation_lock.release()
                                answer=json_loads(row['raw']['text']);Draft202012Validator(schema).validate(answer);cases=checked_cases(answer['cases'],ctx['source_ids']);row['assessment_check']=focused.check(ctx,answer['assessment'],answer['cases']);row['literal_match']=answer['cases'][0]['steps'][0]['expect']==t['expect'];row['correct']=row['literal_match'] and all(c['review_ready'] for c in cases) and row['assessment_check']['status']=='matched'
                            except Exception as error:row['error']=f'{type(error).__name__}: {error}'[:1000]
                            row['latency_ms']=round((time.monotonic()-at)*1000,2);r['rows'].append(row);r['summary']=summary(r['rows'])
                            with self.store.transaction() as db:
                                lease=db.execute('SELECT expires_at FROM studio_operations WHERE token=?',(token,)).fetchone()
                                if not lease or lease[0]<=time.time():raise operations.LeaseLost('Reliability lease lost')
                                self.store.save(db,r)
                r['state']='completed'
        except Exception as error:r.update(state='failed',error=f'{type(error).__name__}: {error}'[:1000])
        finally:
            try:
                with self.store.transaction() as db:
                    try:operations.finish(db,r,token)
                    except operations.LeaseLost:return
                    r['finished_at']=stamp();self.store.save(db,r)
            finally:self.lock.release()

    def cancel(self,id):
        with self.store.transaction() as db:
            r=self.store.load(db,id)
            if r['state']!='running':raise StudioError('INVALID_STATE','Only a running batch can be cancelled',409)
            db.execute('DELETE FROM studio_operations WHERE experiment_id=?',(id,));r.update(state='cancelled',finished_at=stamp(),error='Cancelled explicitly; in-flight provider may take up to its timeout to return. Late completion is fenced.');self.store.save(db,r)
        return r
