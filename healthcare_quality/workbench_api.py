"""V8 product workbench, using existing authentication, explicit actions and review gates."""
from pathlib import Path
from flask import jsonify,g
from healthcare_quality.ai_studio import StudioError
from healthcare_quality.coverage_packs import packs,journeys
from healthcare_quality.test_design import compile_plan
from healthcare_quality.scenario_quality import inspect
from healthcare_quality.evaluation_v8 import cohort
from healthcare_quality.experiment_lab import ExperimentLab
from healthcare_quality.ollama_provider import OllamaProvider
from healthcare_quality.team_workflow import TeamWorkflow
from healthcare_quality.assistant_v8 import explain,gap_analysis

def register(app,body):
 team=TeamWorkflow(Path(app.config['DATABASE']).with_name('team-v8.sqlite'));app.extensions['team_v8']=team
 experiments=ExperimentLab(Path(app.config['DATABASE']).with_name('experiments-v8.sqlite'),OllamaProvider('advanced'),app.extensions['studio'].generation_lock,cohort());app.extensions['experiments_v8']=experiments
 @app.get('/api/advanced/workbench')
 def workbench_summary():
  return jsonify(packs=[{k:v for k,v in p.items() if k!='plans'}|dict(scenarios=len(p['plans'])) for p in packs()],journeys=[dict(id=p['case']['id'],title=p['case']['title']) for p in journeys()],cohort={k:v for k,v in cohort().items() if k!='tasks'}|dict(tasks=[dict(id=t['id'],split=t['split'],family=t['family']) for t in cohort()['tasks']]),queue=team.queue(app.extensions['advanced'].records()),reports=['v7.'+str(n) for n in range(1,10)]+['v8.0'],scope='Synthetic teaching packs. No provider calls on page load. Routing and assistant findings never approve a test.')
 @app.post('/api/advanced/workbench/inspect')
 def workbench_inspect_plan():
  data=body()
  if set(data)!={'plan'}:raise StudioError('INVALID_REQUEST','Provide plan')
  return jsonify(inspect(data['plan']))
 @app.post('/api/advanced/workbench/propose')
 def workbench_propose():
  data=body()
  if set(data)!={'pack','scenario'} or type(data['pack']) is not str or type(data['scenario']) is not int:raise StudioError('INVALID_REQUEST','Select pack and integer scenario index')
  pack=next((p for p in packs() if p['id']==data['pack']),None)
  if pack is None or not 0<=data['scenario']<len(pack['plans']):raise StudioError('INVALID_REQUEST','Unknown pack/scenario')
  return jsonify(app.extensions['advanced'].propose([compile_plan(pack['plans'][data['scenario']])],dict(origin='authored_v8_coverage_pack',pack=pack['id'],expectation_author='independent calculator',live_inference=False))),201
 @app.get('/api/advanced/workbench/assistant/<id>')
 def workbench_assistant(id):return jsonify(explain(app.extensions['advanced'].get(id)))
 @app.post('/api/advanced/workbench/assistant/plan')
 def workbench_ai_plan():
  data=body()
  if set(data)!={'requirement','model'}:raise StudioError('INVALID_REQUEST','Provide requirement and model')
  if type(data['requirement']) is not str or not 10<=len(data['requirement'])<=1500:raise StudioError('INVALID_REQUEST','Provide bounded scenario requirement')
  requirement=data['requirement']+' Include a successful pay followed immediately by an authorized read of that same claim; include payment, ledger, history and balance verification. Return action inputs only, no expected values.'
  return jsonify(app.extensions['designs'].generate(requirement,'calculator_expectations',data['model'],True)),202
 @app.post('/api/advanced/workbench/assistant/designs/<id>/propose')
 def workbench_ai_export(id):
  if body()!={}:raise StudioError('INVALID_REQUEST','Provide empty object')
  r=app.extensions['designs'].get(id)
  from healthcare_quality.advanced_schema import semantic_key
  seen={semantic_key(c) for existing in app.extensions['advanced'].records() if existing.get('assessment',{}).get('valid') for c in existing.get('cases',[])}
  if r['state']!='proposed' or not r.get('assessment',{}).get('eligible') or not inspect(r['plan'],seen)['ready']:raise StudioError('DESIGN_QUALITY_BLOCKED','Valid distinct lifecycle plan and financial readbacks required',409)
  from tools.fingerprints import source_hash
  from healthcare_quality.advanced_lab import contract_hash
  if r['source_hash']!=source_hash() or r['contract_hash']!=contract_hash():raise StudioError('STALE_DESIGN','Create a current design',409)
  return jsonify(app.extensions['advanced'].propose(r['cases'],dict(origin='v8_ai_plan_calculator_expectations',design_id=id,model=r['model'],expectation_author='independent calculator',reference_assisted_correction=False))),201
 @app.get('/api/advanced/workbench/gaps')
 def workbench_gaps():return jsonify(gap_analysis(app.extensions['advanced'].records()))
 @app.post('/api/advanced/workbench/team/<id>')
 def workbench_route(id):
  data=body()
  if set(data)!={'owner','decision','note'}:raise StudioError('INVALID_REQUEST','Provide owner, decision and note')
  identity=getattr(g,'identity',None);actor=identity['username'] if identity else 'local_attestation'
  return jsonify(team.decide(app.extensions['advanced'].get(id),actor=actor,**data))
 @app.get('/api/advanced/workbench/team/<id>')
 def workbench_history(id):return jsonify(team.history(app.extensions['advanced'].get(id)))
 @app.get('/api/advanced/workbench/experiments')
 def workbench_experiment_list():return jsonify(records=[{k:r[k] for k in ('id','state','summary','previously_exposed_tasks')} for r in experiments.records()])
 @app.post('/api/advanced/workbench/experiments')
 def workbench_experiment_start():return jsonify(experiments.start(body(),True)),202
 @app.get('/api/advanced/workbench/experiments/<id>')
 def workbench_experiment_get(id):return jsonify(experiments.get(id))
 @app.post('/api/advanced/workbench/experiments/<id>/cancel')
 def workbench_experiment_cancel(id):
  if body()!={}:raise StudioError('INVALID_REQUEST','Provide empty object')
  return jsonify(experiments.cancel(id))
