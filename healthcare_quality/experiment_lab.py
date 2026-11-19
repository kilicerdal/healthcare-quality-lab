"""Bounded frozen model/prompt comparisons. Raw answers, no correction or approval."""
from copy import deepcopy
from pathlib import Path
from itertools import product
from uuid import uuid4
import json,statistics,threading,time
from healthcare_quality.test_design import PROMPTS,expectation_prompt,evaluate_answer,compile_plan
from healthcare_quality.advanced_schema import SCHEMA,semantic_key
from healthcare_quality.advanced_lab import contract_hash
from healthcare_quality.ai_schema import digest,MODELS
from healthcare_quality.ai_studio import ExperimentStore,StudioError,now
from healthcare_quality import operations
from tools.fingerprints import source_hash
COHORT=Path(__file__).with_name('data')/'experiment_cohort_v612.json'
MODES=('ai_expectations','calculator_control')

def cohort():return json.loads(COHORT.read_text())
def config(body,cohort_data=None):
    if not isinstance(body,dict) or set(body)!={'models','prompts','tasks','repeats','modes'}:raise StudioError('INVALID_REQUEST','Provide models, prompts, tasks, repeats and modes')
    choices={'models':MODELS,'prompts':PROMPTS,'tasks':[t['id'] for t in (cohort_data or cohort())['tasks']],'modes':MODES}
    for key,allowed in choices.items():
        values=body[key]
        if not isinstance(values,list) or not values or any(type(v) is not str or v not in allowed for v in values) or len(set(values))!=len(values):raise StudioError('INVALID_REQUEST','Choose unique known '+key)
    repeats=body['repeats']
    if type(repeats) is not int or not 1<=repeats<=3:raise StudioError('INVALID_REQUEST','Choose 1–3 correlated repeats')
    rows=len(body['models'])*len(body['prompts'])*len(body['tasks'])*len(body['modes'])*repeats
    if rows>24:raise StudioError('BUDGET_EXCEEDED','At most 24 trial rows including calculator controls')
    return deepcopy(body)

def summarize(rows):
    groups={}
    for row in rows:groups.setdefault((row['model'],row['prompt_version'],row['mode']),[]).append(row)
    result=[]
    for (model,prompt,mode),items in groups.items():
        completed=[r for r in items if r['phase']=='completed'];evaluated=[r for r in completed if r.get('assessment') is not None];lat=[r['response']['latency_ms'] for r in items if r.get('response',{}).get('latency_ms') is not None];by_task={}
        for r in completed:
            if r.get('assessment'):by_task.setdefault(r['task_id'],[]).append(digest([(semantic_key(c),[s['expect'] for s in c['steps']]) for c in r['assessment'].get('cases',[])]))
        result.append(dict(model=model,prompt_version=prompt,mode=mode,attempted=len(items),completed=len(completed),unknown_outcomes=sum(r['phase'] in ('request_running','interrupted') for r in items),provider_errors=sum(bool(r.get('provider_error')) for r in items),schema_valid=sum(bool(r['assessment'].get('valid')) for r in evaluated),eligible=sum(bool(r['assessment'].get('eligible')) for r in evaluated),wrong_or_incomplete=sum(not r['assessment'].get('eligible',False) for r in evaluated),latency_median_ms=statistics.median(lat) if lat else None,input_tokens=sum(r.get('response',{}).get('input_tokens') or 0 for r in items),output_tokens=sum(r.get('response',{}).get('output_tokens') or 0 for r in items),stable_repeated_tasks=sum(len(v)>1 and len(set(v))==1 for v in by_task.values()),repeated_tasks=sum(len(v)>1 for v in by_task.values()),reference_assisted_corrections=0,ai_reasoning_metric=mode=='ai_expectations'))
    return result

class ExperimentLab:
    def __init__(self,path,provider,lock,cohort_data=None):self.store=ExperimentStore(path);self.provider=provider;self.lock=lock;self.cohort_data=deepcopy(cohort_data or cohort());self.recover()
    def recover(self):
        with self.store.transaction() as db:
            for row in db.execute('SELECT record_json FROM ai_experiments'):
                r=json.loads(row[0])
                if r['state']=='running':
                    lease=db.execute('SELECT expires_at FROM studio_operations WHERE experiment_id=?',(r['id'],)).fetchone()
                    if not lease or lease[0]<=time.time():
                        r.update(state='interrupted',error='Expired lease; completed responses and exposure remain recorded')
                        for item in r['rows']:
                            if item['phase']=='request_running':item['phase']='interrupted'
                        r['summary']=summarize(r['rows']);db.execute('DELETE FROM studio_operations WHERE experiment_id=?',(r['id'],));self.store.save(db,r)
    def get(self,id):self.recover();return self.store.get(id)
    def records(self):
        self.recover()
        with self.store.transaction() as db:return [json.loads(x[0]) for x in db.execute('SELECT record_json FROM ai_experiments ORDER BY created_at DESC LIMIT 30')]
    def start(self,body,background=False):
        selection=config(body,self.cohort_data);data=self.cohort_data;protocol=dict(selection=selection,cohort_hash=digest(data),source_hash=source_hash(),contract_hash=contract_hash(),provider_settings=deepcopy(getattr(self.provider,'settings',None)),installed_models=self.provider.status()['models'],prompts={t['id']:{v:digest(expectation_prompt(t['plan'],v)) for v in selection['prompts']} for t in data['tasks'] if t['id'] in selection['tasks']},scope='Fixed authored input plans. AI mode fills expectations once; calculator control makes zero model calls and is not AI reasoning. Repeats are correlated. No correction, approval or application execution.')
        r=dict(id=uuid4().hex,created_at=now(),kind='frozen_prompt_model_experiment',state='running',protocol=protocol,rows=[],summary=[],approval=None)
        with self.store.transaction() as db:
            if db.execute('SELECT 1 FROM studio_operations WHERE expires_at>?',(time.time(),)).fetchone():raise StudioError('EXPERIMENT_BUSY','An active experiment owns this ledger',409)
            prior=[json.loads(x[0]) for x in db.execute('SELECT record_json FROM ai_experiments')];exposed={t for old in prior if old.get('protocol',{}).get('cohort_hash')==protocol['cohort_hash'] for t in old['protocol']['selection']['tasks']};r['previously_exposed_tasks']=sorted(exposed&set(selection['tasks']));r['first_recorded_in_this_ledger']=not bool(r['previously_exposed_tasks']);token=operations.start(db,r,'frozen-experiment',30);db.execute('INSERT INTO ai_experiments VALUES(?,?,?)',(r['id'],r['created_at'],json.dumps(r)))
        if background:threading.Thread(target=self._work,args=(r,token),daemon=True).start()
        else:self._work(r,token)
        return self.store.get(r['id'])
    def _save(self,r,token,final=False):
        r['summary']=summarize(r['rows'])
        with self.store.transaction() as db:
            lease=db.execute('SELECT expires_at FROM studio_operations WHERE token=?',(token,)).fetchone()
            if not lease or lease[0]<=time.time():raise operations.LeaseLost('Experiment late completion fenced')
            if final:operations.finish(db,r,token)
            self.store.save(db,r)
    def cancel(self,id):
        with self.store.transaction() as db:
            r=self.store.load(db,id)
            if r['state']!='running':raise StudioError('NOT_RUNNING','Experiment is not running',409)
            r.update(state='interrupted',error='Explicit cancellation; an in-flight provider response is unknown and cannot overwrite this record')
            for row in r['rows']:
                if row['phase']=='request_running':row['phase']='interrupted'
            r['summary']=summarize(r['rows']);db.execute('DELETE FROM studio_operations WHERE experiment_id=?',(id,));self.store.save(db,r);return r
    def _work(self,r,token):
        acquired=False
        try:
            with operations.keepalive(self.store.path,token,30,5):
                if not self.lock.acquire(False):raise StudioError('MODEL_BUSY','Another local inference is active',429)
                acquired=True;s=r['protocol']['selection'];tasks={t['id']:t for t in self.cohort_data['tasks']}
                for model,prompt,task,mode,repeat in product(s['models'],s['prompts'],s['tasks'],s['modes'],range(1,s['repeats']+1)):
                    if source_hash()!=r['protocol']['source_hash'] or digest(self.cohort_data)!=r['protocol']['cohort_hash'] or contract_hash()!=r['protocol']['contract_hash']:raise ValueError('Source/cohort/contract changed during experiment')
                    row=dict(model=model,prompt_version=prompt,task_id=task,mode=mode,repeat=repeat,phase='request_running');r['rows'].append(row);self._save(r,token)
                    if mode=='calculator_control':
                        c=compile_plan(tasks[task]['plan']);row.update(phase='completed',assessment=dict(valid=True,eligible=True,cases=[c]),expectation_author='independent calculator; authored frozen plan; no AI call');self._save(r,token);continue
                    try:
                        row['response']=self.provider.generate(model,expectation_prompt(tasks[task]['plan'],prompt),SCHEMA);self._save(r,token)
                    except operations.LeaseLost:raise
                    except Exception as e:row.update(phase='provider_error',provider_error=type(e).__name__);self._save(r,token);continue
                    row.update(phase='completed',assessment=evaluate_answer(tasks[task]['plan'],row['response']),expectation_author='local model first attempt; no reference feedback');self._save(r,token)
                if source_hash()!=r['protocol']['source_hash']:raise ValueError('Source changed during final request')
                r['state']='completed'
        except operations.LeaseLost:return
        except Exception as e:r.update(state='failed',error=(type(e).__name__+': '+str(e))[:1200])
        finally:
            if acquired:self.lock.release()
            try:self._save(r,token,True)
            except operations.LeaseLost:pass
