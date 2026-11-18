"""Integrated reliability, grounded assistant, traceability and advanced synthetic claims."""
from pathlib import Path
from uuid import uuid4
import json
from flask import request,jsonify,g
from healthcare_quality.reliability import ReliabilityLab,dataset
from healthcare_quality.investigator import analyze,change_impact
from healthcare_quality.benefits import FACTS
from healthcare_quality.benefit_claims import BenefitClaims,FAMILIES
from healthcare_quality.ai_studio import ExperimentStore,StudioError,now
from healthcare_quality.ai_schema import MODELS
from healthcare_quality.maintenance import recommend,instability

def register(app,body,actor_id):
    root=Path(app.config['DATABASE']).parent;studio=app.extensions['studio'];coverage=app.extensions['coverage_lab'];reliability=ReliabilityLab(root/'reliability-v58.sqlite',studio.provider,generation_lock=studio.generation_lock);research=ExperimentStore(root/'research-v59.sqlite');benefits=BenefitClaims(root/'benefits-v60.sqlite');app.extensions.update(reliability=reliability,research=research,benefits=benefits)
    from healthcare_quality.advanced_lab import AdvancedLab
    advanced=AdvancedLab(root/'advanced-v63.sqlite',studio.provider,studio.generation_lock)
    app.extensions['advanced']=advanced
    @app.get('/api/advanced')
    def advanced_list():
        return jsonify(records=[{k:r.get(k) for k in ('id','created_at','state','revision','assessment','provenance')} for r in advanced.records()])
    @app.get('/api/advanced/<id>')
    def advanced_get(id):return jsonify(advanced.get(id))
    @app.post('/api/advanced/generate')
    def advanced_generate():return jsonify(advanced.generate(body())),202
    @app.get('/api/advanced/controls')
    def advanced_controls():
        return jsonify(json.loads((Path(__file__).with_name('data')/'advanced_cases_v63.json').read_text()))
    @app.post('/api/advanced/import')
    def advanced_import():
        b=body()
        if not isinstance(b,dict) or set(b)!={'cases'}:raise StudioError('INVALID_REQUEST','Provide cases')
        return jsonify(advanced.propose(b['cases'])),201
    @app.post('/api/advanced/<id>/review')
    def advanced_review(id):
        b=body()
        if not isinstance(b,dict) or set(b)!={'reviewer','note','revision'} or type(b['revision']) is not int:raise StudioError('INVALID_REQUEST','Provide reviewer, note and revision')
        reviewer=g.identity['username'] if getattr(g,'identity',None) else b['reviewer']
        return jsonify(advanced.review(id,reviewer,b['note'],b['revision']))
    @app.post('/api/advanced/<id>/execute')
    def advanced_execute(id):
        b=body()
        if not isinstance(b,dict) or set(b)!={'transport'} or b['transport'] not in ('service','http'):raise StudioError('INVALID_REQUEST','Choose service or http')
        return jsonify(advanced.execute(id,b['transport']))
    @app.post('/api/advanced/<id>/correct')
    def advanced_correct(id):
        b=body()
        if not isinstance(b,dict) or set(b)!={'model'}:raise StudioError('INVALID_REQUEST','Provide a local model')
        return jsonify(advanced.correct(id,b['model'])),201
    @app.post('/api/advanced/<id>/score')
    def advanced_score(id):
        if body()!={}:raise StudioError('INVALID_REQUEST','Provide an empty object')
        return jsonify(advanced.score(id))
    evaluations=ExperimentStore(root/'advanced-evaluations-v64.sqlite')
    integrations=ExperimentStore(root/'integrations-v67.sqlite')
    app.extensions.update(advanced_evaluations=evaluations,integrations=integrations)
    from healthcare_quality.integration_scenarios import SCENARIOS,rehearse
    from healthcare_quality.advanced_evaluation import recover as recover_evaluations
    import threading
    integration_lock=threading.BoundedSemaphore(1)
    def records(store):
        with store.transaction() as db:return [json.loads(r[0]) for r in db.execute('SELECT record_json FROM ai_experiments ORDER BY created_at DESC LIMIT 50')]
    @app.get('/api/advanced/evaluations')
    def advanced_evaluations():
        recover_evaluations(evaluations)
        return jsonify(records=[{k:r.get(k) for k in ('id','created_at','state','protocol','summary','previously_exposed_tasks')} for r in records(evaluations)])
    @app.get('/api/advanced/evaluations/<id>')
    def advanced_evaluation(id):return jsonify(evaluations.get(id))
    @app.get('/api/integrations')
    def integration_records():return jsonify(scenarios=SCENARIOS,records=records(integrations))
    @app.post('/api/integrations/rehearse')
    def integration_rehearsal():
        b=body()
        if not isinstance(b,dict) or set(b)!={'scenario'} or b['scenario'] not in SCENARIOS:raise StudioError('INVALID_REQUEST','Select a known synthetic integration scenario')
        if not integration_lock.acquire(False):raise StudioError('INTEGRATION_BUSY','Another isolated rehearsal is active',409)
        try:r=rehearse(b['scenario'])
        finally:integration_lock.release()
        r.update(created_at=now(),kind='integration',state='completed' if r['passed'] else 'failed');integrations.create(r)
        return jsonify(r),201
    @app.get('/api/research/overview')
    def overview():
        data=dataset();records=reliability.records()
        with research.transaction() as db:
            investigations=[{k:value.get(k) for k in ("id","created_at","state","kind")} for value in (json.loads(row[0]) for row in db.execute("SELECT record_json FROM ai_experiments ORDER BY created_at DESC LIMIT 50"))]
        return jsonify(dataset=dict(version=data['version'],task_ids=[t['id'] for t in data['tasks']],scope=data['scope']),models=list(MODELS),benchmarks=[{k:r.get(k) for k in ('id','created_at','state','first_exposure','models','task_ids','repeats','summary','error')} for r in records],investigations=investigations,milestones=['V5.8 Reliability','V5.9 Grounded assistant','V6.0 Benefit lifecycle','V6.1 Resilience','V6.2 Reproducible showcase'])
    @app.post('/api/research/benchmarks')
    def benchmark():return jsonify(reliability.start(body())),202
    @app.get('/api/research/benchmarks/<id>')
    def benchmark_record(id):return jsonify(reliability.store.get(id))

    @app.post('/api/research/benchmarks/<id>/cancel')
    def benchmark_cancel(id):return jsonify(reliability.cancel(id))
    @app.post('/api/research/investigations')
    def investigate():
        b=body()
        if not isinstance(b,dict) or set(b)!={'experiment_id','run_id','model'} or b['model'] not in (*MODELS,None):raise StudioError('INVALID_REQUEST','Provide stored experiment_id, run_id and optional local model')
        e=studio.store.get(b['experiment_id']);analysis=analyze(e,b['run_id']);hypotheses=app.extensions['quality_lab'].investigate(b) if b['model'] else None;r=dict(id=uuid4().hex,created_at=now(),kind='grounded_investigation',state='completed',analysis=analysis,ai=hypotheses,reviewer=getattr(g,'identity',None));research.create(r);return jsonify(r),201
    @app.get('/api/research/investigations/<id>')
    def investigation_record(id):return jsonify(research.get(id))
    @app.post('/api/research/changes')
    def changes():
        b=body()
        if not isinstance(b,dict) or set(b)!={'rule_ids'}:raise StudioError('INVALID_REQUEST','Provide rule_ids')
        return jsonify(change_impact(b['rule_ids'],coverage.inventory()))
    @app.post('/api/research/changes/propose')
    def propose():
        b=body()
        if not isinstance(b,dict) or set(b)!={'rule_ids','model'}:raise StudioError('INVALID_REQUEST','Provide rule_ids and model')
        impact=change_impact(b['rule_ids'],coverage.inventory());return jsonify(studio.generate(dict(requirement=impact['suggested_requirement'],source_ids=b['rule_ids'],model=b['model'],strategy='boundaries-v1',count=1))),201
    @app.get('/api/research/maintenance/<id>')
    def maintenance(id):return jsonify(instability=instability(studio.store.get(id)),scope='Mixed outcomes compare identical source/contract/revision/transport; investigate nondeterminism before calling a test flaky.')
    @app.get('/api/research/suite/<id>')
    def suite(id):
        score=coverage.record(id)
        if not score.get('matches_current_implementation') or not score.get('approval_snapshots_current'):raise StudioError('STALE_SCORE','Rescore current approved cases before recommendations',409)
        try:return jsonify(recommend(score))
        except ValueError as e:raise StudioError('INVALID_SCORE',str(e))
    @app.get('/api/benefits/catalog')
    def benefit_catalog():return jsonify(**FACTS,members=FAMILIES,synthetic=True)
    @app.post('/api/benefits/claims')
    def benefit_submit():return jsonify(benefits.operate(actor_id(),body(),'submit')),201
    @app.get('/api/benefits/claims/<id>')
    def benefit_get(id):return jsonify(benefits.get(actor_id(),id))
    @app.post('/api/benefits/claims/<id>/<action>')
    def benefit_action(id,action):return jsonify(benefits.operate(actor_id(),body(),action,id))
