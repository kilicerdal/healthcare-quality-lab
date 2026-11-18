from pathlib import Path
import threading
from flask import jsonify
from healthcare_quality.ai_studio import ExperimentStore,StudioError,now
from healthcare_quality.evidence_investigator import rehearsal,seal,inspect,explain
from healthcare_quality.ollama_provider import OllamaProvider
from healthcare_quality.ai_schema import MODELS
from uuid import uuid4

def register(app,body):
    store=ExperimentStore(Path(app.config['DATABASE']).with_name('investigations-v69.sqlite'));app.extensions['advanced_investigations']=store;lock=threading.BoundedSemaphore(1)
    @app.get('/api/advanced/investigations')
    def investigation_list():
        with store.transaction() as db:return jsonify(records=[jsonify_record(x[0]) for x in db.execute('SELECT record_json FROM ai_experiments ORDER BY created_at DESC LIMIT 30')])
    @app.get('/api/advanced/investigations/<id>')
    def investigation_get(id):return jsonify(store.get(id))
    @app.post('/api/advanced/investigations')
    def investigation_create():
        b=body()
        if not isinstance(b,dict) or set(b)!={'proposal_id','run_id'}:raise StudioError('INVALID_REQUEST','Select a saved advanced proposal and run')
        p=app.extensions['advanced'].get(b['proposal_id']);run=next((x for x in p['runs'] if x['id']==b['run_id']),None)
        if not run:raise StudioError('NOT_FOUND','Saved run not found',404)
        bundle=seal(p['cases'],run);bundle['source_hash']=p['source_hash'];bundle['contract_hash']=p['contract_hash']
        from healthcare_quality.ai_schema import digest
        bundle['content_hash']=digest({k:v for k,v in bundle.items() if k!='content_hash'})
        r=dict(id=uuid4().hex,created_at=now(),kind='advanced_investigation',bundle=bundle,analysis=inspect(bundle),ai=None);store.create(r);return jsonify(r),201
    @app.post('/api/advanced/investigations/<id>/explain')
    def investigation_explain(id):
        b=body()
        if not isinstance(b,dict) or set(b)!={'model'} or b['model'] not in MODELS:raise StudioError('INVALID_REQUEST','Choose an allowlisted local model')
        if not app.extensions['studio'].generation_lock.acquire(False):raise StudioError('MODEL_BUSY','Another inference is active',429)
        try:
            r=store.get(id)
            if r.get('ai'):raise StudioError('ALREADY_EXPLAINED','Use the saved explanation; no silent repeated inference',409)
            r['analysis']=inspect(r['bundle']);r['ai']=explain(OllamaProvider('advanced'),b['model'],r['analysis'])
            with store.transaction() as db:store.save(db,r)
        finally:app.extensions['studio'].generation_lock.release()
        return jsonify(r)
    @app.post('/api/advanced/investigations/rehearse')
    def investigation_rehearse():
        if body()!={}:raise StudioError('INVALID_REQUEST','Provide an empty object')
        # Run the fault control in its own process: never patch the interactive server.
        import subprocess,sys,json,tempfile
        if not lock.acquire(False):raise StudioError('REHEARSAL_BUSY','An isolated investigation is active',409)
        try:
            with tempfile.TemporaryDirectory(prefix='hql-investigation-') as tmp:
                path=Path(tmp)/'result.json';proc=subprocess.run([sys.executable,'-m','tools.investigate','--output',str(path)],capture_output=True,text=True,timeout=45)
                if proc.returncode:raise StudioError('REHEARSAL_FAILED','Isolated control did not complete',500)
                r=json.loads(path.read_text());r.update(id=uuid4().hex,created_at=now(),ai=None);store.create(r)
        finally:lock.release()
        return jsonify(r),201

def jsonify_record(raw):
    import json
    r=json.loads(raw);return {k:r.get(k) for k in ('id','created_at','kind','analysis','passed','ai')}
