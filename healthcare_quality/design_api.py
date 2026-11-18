"""Explicit plan-first API; no inference on reads and no automatic approvals."""
from pathlib import Path
from flask import jsonify
from healthcare_quality.test_design import DesignLab,MODES
from healthcare_quality.ai_studio import StudioError
from healthcare_quality.ollama_provider import OllamaProvider

def register(app,body):
    lab=DesignLab(Path(app.config['DATABASE']).with_name('designs-v68.sqlite'),OllamaProvider('advanced'),app.extensions['studio'].generation_lock);app.extensions['designs']=lab
    @app.get('/api/advanced/designs')
    def designs():return jsonify(modes=MODES,records=lab.records(),scope='Plans and cases remain unapproved. Calculator expectations are not AI-authored expected values.')
    @app.get('/api/advanced/designs/<id>')
    def design_get(id):return jsonify(lab.get(id))
    @app.post('/api/advanced/designs/generate')
    def design_generate():
        b=body()
        if not isinstance(b,dict) or set(b)!={'requirement','mode','model'}:raise StudioError('INVALID_REQUEST','Provide requirement, mode and model')
        return jsonify(lab.generate(b['requirement'],b['mode'],b['model'],True)),202
    @app.post('/api/advanced/designs/<id>/export')
    def design_export(id):
        if body()!={}:raise StudioError('INVALID_REQUEST','Provide an empty object')
        r=lab.get(id)
        if r['state']!='proposed' or not r['assessment']['eligible']:raise StudioError('DESIGN_BLOCKED','Only checked, scenario-preserving proposals can be exported',409)
        from tools.fingerprints import source_hash
        from healthcare_quality.advanced_lab import contract_hash
        if r['source_hash']!=source_hash() or r['contract_hash']!=contract_hash():raise StudioError('STALE_DESIGN','Regenerate against current source',409)
        return jsonify(app.extensions['advanced'].propose(r['cases'],dict(origin='plan_first_'+r['mode'],design_id=id,expectation_author=r['expectation_author'],reference_assisted=False,explicit_export=True))),201
