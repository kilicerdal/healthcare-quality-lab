from pathlib import Path
from flask import jsonify
from healthcare_quality.experiment_lab import ExperimentLab,cohort
from healthcare_quality.ollama_provider import OllamaProvider
from healthcare_quality.ai_studio import StudioError
from healthcare_quality.ai_schema import MODELS
from healthcare_quality.test_design import PROMPTS

def register(app,body):
 lab=ExperimentLab(Path(app.config['DATABASE']).with_name('experiments-v612.sqlite'),OllamaProvider('advanced'),app.extensions['studio'].generation_lock);app.extensions['experiments']=lab
 @app.get('/api/advanced/experiments')
 def experiments_list():return jsonify(records=[{k:r.get(k) for k in ('id','created_at','state','protocol','summary','previously_exposed_tasks','error')} for r in lab.records()],models=list(MODELS),prompts=list(PROMPTS),tasks=[{'id':t['id'],'split':t['split']} for t in cohort()['tasks']],scope='Explicit bounded calls only. Calculator rows are not model accuracy; no inference on page load.')
 @app.get('/api/advanced/experiments/<id>')
 def experiment_get(id):
  from tools.fingerprints import source_hash
  r=lab.get(id);r['matches_current_source']=r['protocol']['source_hash']==source_hash();return jsonify(r)
 @app.post('/api/advanced/experiments')
 def experiment_start():return jsonify(lab.start(body(),True)),202
 @app.post('/api/advanced/experiments/<id>/cancel')
 def experiment_cancel(id):
  if body()!={}:raise StudioError('INVALID_REQUEST','Provide an empty object')
  return jsonify(lab.cancel(id))
