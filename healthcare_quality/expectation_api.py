"""Explicit experimental model-only generation and separate unapproved export."""
from pathlib import Path
from flask import jsonify
from healthcare_quality.expectation_lab import ExpectationLab
from healthcare_quality.expectation_protocol import cohort,VERSION
from healthcare_quality.ollama_provider import ExpectationOllamaProvider
from healthcare_quality.ai_schema import MODELS
from healthcare_quality.ai_studio import StudioError
from healthcare_quality.advanced_lab import contract_hash
from tools.fingerprints import source_hash

def register(app,body):
 lab=ExpectationLab(Path(app.config['DATABASE']).with_name('expectations-v81.sqlite'),ExpectationOllamaProvider(),app.extensions['studio'].generation_lock);app.extensions['expectations_v81']=lab
 @app.get('/api/advanced/expectations')
 def expectation_config():return jsonify(version=VERSION,models=list(MODELS),tasks=[{k:t[k] for k in ('id','split')} for t in cohort()['tasks']],target=cohort()['target'],records=[{k:r[k] for k in ('id','created_at','state','summary','previously_exposed_tasks')} for r in lab.records()],scope='Experimental. Models author all numbers; the calculator only scores frozen answers. First attempt and blind self-review are separate. Page loads make zero generation calls.')
 @app.post('/api/advanced/expectations')
 def expectation_start():return jsonify(lab.start(body(),True)),202
 @app.get('/api/advanced/expectations/<id>')
 def expectation_get(id):
  r=lab.get(id);r['matches_current_source']=r['protocol']['source_hash']==source_hash() and r['protocol']['contract_hash']==contract_hash();return jsonify(r)
 @app.post('/api/advanced/expectations/<id>/cancel')
 def expectation_cancel(id):
  if body()!={}:raise StudioError('INVALID_REQUEST','Provide empty object')
  return jsonify(lab.cancel(id))
 @app.post('/api/advanced/expectations/<id>/propose')
 def expectation_export(id):
  data=body()
  if set(data)!={'row','stage'} or type(data['row']) is not int or data['stage'] not in ('first','self_review'):raise StudioError('INVALID_REQUEST','Select integer row and first/self_review stage')
  r=lab.get(id)
  if r['state']!='completed' or r['protocol']['source_hash']!=source_hash() or r['protocol']['contract_hash']!=contract_hash():raise StudioError('STALE_EXPERIMENT','Use a completed current-source experiment',409)
  if not 0<=data['row']<len(r['rows']):raise StudioError('INVALID_REQUEST','Unknown trial row')
  row=r['rows'][data['row']];answer=row.get(data['stage'],{}).get('answer')
  from healthcare_quality.expectation_evaluator import evaluate
  task=next(t for t in cohort()['tasks'] if t['id']==row['task_id']);assessment=evaluate(task['plan'],answer)
  if not assessment['eligible']:raise StudioError('EXPECTATIONS_BLOCKED','All model-authored observations and worksheets must independently match',409)
  return jsonify(app.extensions['advanced'].propose(assessment['cases'],dict(origin='v81_model_expectations_'+data['stage'],experiment_id=id,row=data['row'],model=row['model'],stage=data['stage'],expectation_author='local model; no calculator assistance',blind_self_review=data['stage']=='self_review',reference_assisted=False,experimental=True))),201
