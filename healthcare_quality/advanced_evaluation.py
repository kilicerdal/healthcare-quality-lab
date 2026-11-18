"""Frozen raw-versus-assisted evaluation. No approval or application execution."""
from copy import deepcopy
from pathlib import Path
from datetime import datetime,timezone
import json,statistics,time
from uuid import uuid4
from healthcare_quality import operations
from healthcare_quality.ai_schema import digest,json_loads,MODELS
from healthcare_quality.advanced_schema import semantic_key,SCHEMA,parse_model_json
from healthcare_quality.advanced_lab import check,prompt_for,contract_hash
from healthcare_quality.ai_studio import ExperimentStore,StudioError
from tools.fingerprints import source_hash

COHORT=Path(__file__).with_name('data')/'advanced_cohort_v64.json'
def cohort():return json_loads(COHORT.read_text())
def assessment(task,response):
    try:
        answer=parse_model_json(response['text']);cases=answer['cases'];result=check(cases)
        fixed=result['valid'] and len(cases)==1 and semantic_key(cases[0])==semantic_key(task['case'])
        return dict(**result,fixed_inputs=fixed,eligible=bool(fixed and result['review_ready']),cases=cases)
    except (KeyError,TypeError,ValueError,RecursionError) as error:return dict(valid=False,matched=False,fixed_inputs=False,eligible=False,error=type(error).__name__,cases=[])

def request_for(task):
    frozen=deepcopy(task['case'])
    for s in frozen['steps']:s.pop('expect')
    return prompt_for(task['requirement'])+'\nUse EXACTLY this case action sequence, actors and data; fill every expect object. Do not simplify or rename inputs.\n'+json.dumps(frozen,sort_keys=True)

def summarize(rows):
    result={}
    for model in sorted({r['model'] for r in rows}):
        items=[r for r in rows if r['model']==model];raw=[r.get('raw_assessment',{}) for r in items];corrected=[r.get('corrected_assessment') for r in items if r.get('corrected_assessment') is not None]
        lat=[r['latency_ms'] for r in items if r.get('latency_ms') is not None];groups={}
        for r in items:groups.setdefault(r['task_id'],[]).append(digest([(semantic_key(c),[s['expect'] for s in c['steps']]) for c in r['raw_assessment']['cases']]) if r.get('raw_assessment',{}).get('fixed_inputs') else None)
        result[model]=dict(requested=len(items),raw_completed=sum('raw_assessment' in r for r in items),unknown_outcomes=sum(r.get('phase') in ('raw_running','correction_running','interrupted') for r in items),raw_eligible=sum(bool(x.get('eligible')) for x in raw),raw_schema_valid=sum(bool(x.get('valid')) for x in raw),wrong_or_incomplete=sum(not x.get('eligible',False) for x in raw if x),provider_errors=sum('error' in r for r in items),correction_requests=sum(bool(r.get('correction_requested')) for r in items),assisted_eligible=sum(bool(x.get('eligible')) for x in corrected),stable_tasks=sum(len(v)>1 and None not in v and len(set(v))==1 for v in groups.values()),repeated_tasks=sum(len(v)>1 for v in groups.values()),latency_median_ms=statistics.median(lat) if lat else None,raw_latency_median_ms=statistics.median([r['raw_latency_ms'] for r in items if 'raw_latency_ms' in r]) if any('raw_latency_ms' in r for r in items) else None,correction_provider_errors=sum(bool(r.get('correction_requested')) and not r.get('corrected') for r in items),assisted_input_tokens=sum((r.get('corrected') or {}).get('input_tokens') or 0 for r in items),assisted_output_tokens=sum((r.get('corrected') or {}).get('output_tokens') or 0 for r in items),input_tokens=sum((r.get('raw') or {}).get('input_tokens') or 0 for r in items),output_tokens=sum((r.get('raw') or {}).get('output_tokens') or 0 for r in items),paid_api_calls=0)
    return result

def recover(store):
    with store.transaction() as db:
        for row in db.execute('SELECT record_json FROM ai_experiments').fetchall():
            r=json_loads(row[0])
            if r.get('kind')=='advanced_evaluation' and r['state']=='running':
                lease=db.execute('SELECT expires_at FROM studio_operations WHERE experiment_id=?',(r['id'],)).fetchone()
                if not lease or lease[0]<=time.time():
                    r.update(state='interrupted',error='Evaluation lease expired; partial observations and exposure retained')
                    for item in r['rows']:
                        if item.get('phase') in ('raw_running','correction_running'):
                            item['interrupted_phase']=item['phase'];item['phase']='interrupted'
                    if all('model' in item for item in r['rows']):r['summary']=summarize(r['rows'])
                    db.execute('DELETE FROM studio_operations WHERE experiment_id=?',(r['id'],));store.save(db,r)

def measure(provider,model,task_ids,repeats,state,output,correct=False):
    if model not in MODELS or type(repeats) is not int or not 1<=repeats<=3 or not isinstance(task_ids,list) or not 1<=len(task_ids)<=8 or len(set(task_ids))!=len(task_ids) or len(task_ids)*repeats*(2 if correct else 1)>24:raise ValueError('At most 24 bounded local requests; unique known tasks, 1–3 repeats')
    data=cohort();tasks={t['id']:t for t in data['tasks']}
    if any(t not in tasks for t in task_ids):raise ValueError('Unknown task')
    output=Path(output)
    if output.exists():raise ValueError('Evidence exists; choose a fresh file')
    output.parent.mkdir(parents=True,exist_ok=True);store=ExperimentStore(state);recover(store);id=uuid4().hex
    runtime=getattr(provider,'status',lambda:{'models':[]})()
    protocol=dict(provider_settings=deepcopy(getattr(provider,'settings',None)),model_digest=next((m.get('digest') for m in runtime.get('models',[]) if m['name']==model),None),cohort_hash=digest(data),contract_hash=contract_hash(),source_hash=source_hash(),model=model,task_ids=task_ids,repeats=repeats,correction_enabled=correct,prompts={t:digest(request_for(tasks[t])) for t in task_ids},scope=data['scope'],approval='unapproved',application_execution=False)
    # Reserve exposure atomically in the shared ledger BEFORE the first request.
    with store.transaction() as db:
        previous=[json_loads(r[0]) for r in db.execute('SELECT record_json FROM ai_experiments')]
        exposed={t for r in previous if r.get('protocol',{}).get('cohort_hash')==protocol['cohort_hash'] for t in r['protocol']['task_ids']}
        record=dict(id=id,kind='advanced_evaluation',created_at=datetime.now(timezone.utc).isoformat(),state='running',protocol=protocol,previously_exposed_tasks=sorted(exposed&set(task_ids)),first_recorded_in_this_ledger=not bool(exposed&set(task_ids)),rows=[],summary={})
        if db.execute('SELECT 1 FROM studio_operations WHERE expires_at>?',(time.time(),)).fetchone():raise StudioError('EVALUATION_BUSY','Another worker owns an active evaluation lease',409)
        token=operations.start(db,record,'advanced-evaluation',30)
        db.execute('INSERT INTO ai_experiments VALUES(?,?,?)',(id,record['created_at'],json.dumps(record)))
    def save(final=False):
        record['summary']=summarize(record['rows'])
        with store.transaction() as db:
            if final:operations.finish(db,record,token)
            else:
                lease=db.execute('SELECT expires_at FROM studio_operations WHERE token=?',(token,)).fetchone()
                if not lease or lease[0]<=time.time():raise operations.LeaseLost('Evaluation completion fenced')
            store.save(db,record)
        temporary=output.with_suffix(output.suffix+'.tmp');temporary.write_text(json.dumps(record,indent=2)+'\n');temporary.replace(output)
    save()
    with operations.keepalive(store.path,token,30,5):
        try:
            for repeat in range(repeats):
                for task_id in task_ids:
                    if source_hash()!=protocol['source_hash'] or digest(cohort())!=protocol['cohort_hash']:
                        raise ValueError('Protocol/source changed; partial measurements retained')
                    task=tasks[task_id]
                    row=dict(task_id=task_id,split=task['split'],model=model,repeat=repeat+1,
                             phase='raw_running',latency_ms=None)
                    record['rows'].append(row)
                    save()  # Attempt is durable before starting the provider request.
                    started=time.monotonic()
                    try:
                        row['raw']=provider.generate(model,request_for(task),SCHEMA)
                        row['raw_latency_ms']=round((time.monotonic()-started)*1000,2)
                        row['raw_assessment']=assessment(task,row['raw'])
                        row['phase']='raw_completed'
                    except Exception as error:
                        row['error']=dict(stage='raw',type=type(error).__name__,message=str(error)[:500])
                        row['phase']='failed'
                        if getattr(error,'raw_response',None) is not None:row['provider_error_raw']=error.raw_response
                    row['latency_ms']=round((time.monotonic()-started)*1000,2)
                    save()  # Completed raw output must survive an interrupted correction.
                    if correct and row.get('raw_assessment') and not row['raw_assessment']['eligible']:
                        if source_hash()!=protocol['source_hash']:
                            raise ValueError('Source changed before correction; raw output retained')
                        prompt=request_for(task)+'\nONE REFERENCE-ASSISTED CORRECTION. Preserve fixed action/data inputs.\nORIGINAL OUTPUT: '+row['raw']['text']+'\nINDEPENDENT FEEDBACK: '+json.dumps(row['raw_assessment'])+'\nINDEPENDENT EXPECTATIONS: '+json.dumps([s['expect'] for s in task['case']['steps']])
                        row.update(correction_requested=True,phase='correction_running')
                        save()
                        try:
                            row['corrected']=provider.generate(model,prompt,SCHEMA)
                            row['corrected_assessment']=assessment(task,row['corrected'])
                            row['reference_assisted']=True
                        except Exception as error:
                            row['error']=dict(stage='correction',type=type(error).__name__,message=str(error)[:500])
                            if getattr(error,'raw_response',None) is not None:row['provider_error_raw']=error.raw_response
                    row['phase']='failed' if row.get('error') else 'completed'
                    row['latency_ms']=round((time.monotonic()-started)*1000,2)
                    save()
            if source_hash()!=protocol['source_hash'] or digest(cohort())!=protocol['cohort_hash']:
                raise ValueError('Protocol/source changed during final request; observations retained')
            record['state']='completed'
        except Exception as error:
            record.update(state='interrupted',error=str(error)[:500])
    record['finished_at']=datetime.now(timezone.utc).isoformat()
    save(final=True)
    return record
