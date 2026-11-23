"""Explicit experimental model-only generation and separate unapproved export."""
from pathlib import Path
from flask import jsonify
from healthcare_quality.expectation_lab import ExpectationLab
from healthcare_quality import compact_expectations_v83 as compact_expectations
from healthcare_quality.compact_expectations_v83 import cohort,VERSION
from healthcare_quality.compact_evaluator import evaluate
from healthcare_quality.ollama_provider import CompactExpectationProvider
from healthcare_quality.ai_schema import MODELS
from healthcare_quality.experiment_budget import request as budget_request,estimate
from healthcare_quality.ai_studio import StudioError
from healthcare_quality.advanced_lab import contract_hash
from tools.fingerprints import source_hash

def register(app,body):
 lab=ExpectationLab(Path(app.config['DATABASE']).with_name('expectations-v83.sqlite'),CompactExpectationProvider(),app.extensions['studio'].generation_lock,protocol=compact_expectations,evaluator=evaluate);app.extensions['expectations_v82']=lab;app.extensions['expectations_v83']=lab
 @app.get('/api/advanced/expectations-v82')
 @app.get('/api/advanced/expectations-v83')
 def compact_config():return jsonify(version=VERSION,models=list(MODELS),default_max_seconds=180,max_seconds_limit=300,tasks=[{k:t[k] for k in ('id','split')} for t in cohort()['tasks']],target=cohort()['target'],records=[{k:r[k] for k in ('id','created_at','state','summary','previously_exposed_tasks')} for r in lab.records()],scope='Experimental compact quotes; pricing worksheets scored once per pricing action plus stored-ledger checks; no revision/event worksheet claim. Models author all numbers; the calculator only scores frozen answers. First attempt and blind self-review are separate. Page loads make zero generation calls.')
 @app.post('/api/advanced/expectations-v82')
 @app.post('/api/advanced/expectations-v83')
 def compact_start():
  data,seconds=budget_request(body());return jsonify(lab.start(data,True,max_seconds=seconds)),202
 @app.get('/api/advanced/expectations-v82/<id>')
 @app.get('/api/advanced/expectations-v83/<id>')
 def compact_get(id):
  from copy import deepcopy
  from healthcare_quality.expectation_lab import summary
  r=deepcopy(lab.get(id));r['summary']=summary(r['rows']);r['run_complete']=r['state']=='completed';r['qualification_complete']=bool(r['run_complete'] and any(g['stage']=='first' and g['unique_heldout_tasks']>=10 for g in r['summary']));r['matches_current_source']=r['protocol']['source_hash']==source_hash() and r['protocol']['contract_hash']==contract_hash();return jsonify(r)
 @app.post('/api/advanced/expectations-v82/<id>/cancel')
 @app.post('/api/advanced/expectations-v83/<id>/cancel')
 def compact_cancel(id):
  if body()!={}:raise StudioError('INVALID_REQUEST','Provide empty object')
  return jsonify(lab.cancel(id))
 @app.post('/api/advanced/expectations-v82/<id>/propose')
 @app.post('/api/advanced/expectations-v83/<id>/propose')
 def compact_export(id):
  data=body()
  if set(data)!={'row','stage'} or type(data['row']) is not int or data['stage'] not in ('first','self_review'):raise StudioError('INVALID_REQUEST','Select integer row and first/self_review stage')
  r=lab.get(id)
  if r['state']!='completed' or r['protocol']['source_hash']!=source_hash() or r['protocol']['contract_hash']!=contract_hash():raise StudioError('STALE_EXPERIMENT','Use a completed current-source experiment',409)
  if not 0<=data['row']<len(r['rows']):raise StudioError('INVALID_REQUEST','Unknown trial row')
  row=r['rows'][data['row']];answer=row.get(data['stage'],{}).get('answer')
  from healthcare_quality.compact_evaluator import evaluate
  task=next(t for t in cohort()['tasks'] if t['id']==row['task_id']);assessment=evaluate(task['plan'],answer)
  if not assessment['eligible']:raise StudioError('EXPECTATIONS_BLOCKED','All model-authored observations and pricing/ledger worksheets must independently match',409)
  return jsonify(app.extensions['advanced'].propose(assessment['cases'],dict(origin='v83_model_expectations_'+data['stage'],experiment_id=id,row=data['row'],model=row['model'],stage=data['stage'],expectation_author='local model; no calculator assistance',blind_self_review=data['stage']=='self_review',reference_assisted=False,experimental=True))),201

 @app.get('/api/advanced/expectations-v82/faults')
 @app.get('/api/advanced/expectations-v83/faults')
 def compact_faults():
  import json
  from tools.fault_audit_v82 import ROOT,SURVIVORS
  from healthcare_quality.effectiveness import variants
  path=ROOT/'artifacts/v8.2/fault-audit.json';record=json.loads(path.read_text()) if path.is_file() else None
  return jsonify(faults=[{k:v[k] for k in ('id','before','after')} for v in variants() if v['id'] in SURVIVORS],evidence=record,evidence_matches_current_source=bool(record and record['source_hash']==source_hash()),scope='V8.1 AI suite detected21/27. Multi-claim witnesses are authored engineering tests, not AI credit. Loading this catalog does not run mutations or inference.')

 @app.post('/api/advanced/expectations-v83/estimate')
 @app.post('/api/advanced/expectations-v82/estimate')
 def compact_estimate():return jsonify(estimate(body(),lab.records(),cohort()))
