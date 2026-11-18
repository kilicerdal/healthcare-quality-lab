from pathlib import Path
from uuid import uuid4
from flask import jsonify
from healthcare_quality.ai_studio import ExperimentStore,StudioError,now
from healthcare_quality.traceability import graph,impact

def register(app,body):
    store=ExperimentStore(Path(app.config['DATABASE']).with_name('traceability-v610.sqlite'));app.extensions['traceability']=store
    def current():return graph(app.extensions['advanced'].records())
    @app.get('/api/advanced/traceability')
    def trace_current():return jsonify(current())
    @app.post('/api/advanced/traceability/snapshots')
    def trace_snapshot():
        if body()!={}:raise StudioError('INVALID_REQUEST','Provide an empty object')
        r=dict(id=uuid4().hex,created_at=now(),kind='trace_snapshot',graph=current());store.create(r);return jsonify(r),201
    @app.post('/api/advanced/traceability/impact')
    def trace_impact():
        b=body()
        if not isinstance(b,dict) or set(b)!={'snapshot_id','changes'} or type(b['snapshot_id']) is not str:raise StudioError('INVALID_REQUEST','Provide snapshot ID and proposed written-rule changes')
        try:return jsonify(impact(store.get(b['snapshot_id'])['graph'],b['changes']))
        except ValueError as e:raise StudioError('INVALID_REQUEST',str(e)) from e
