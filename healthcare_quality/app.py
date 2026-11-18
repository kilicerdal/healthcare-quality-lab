from healthcare_quality import reference, focused
"""V5 local healthcare quality showcase, AI review controls and transactional API."""
import json
import logging
import os
import time
from uuid import uuid4
from pathlib import Path
import sqlite3
from flask import Flask, jsonify, render_template, request, send_file, g
from werkzeug.exceptions import RequestEntityTooLarge
from tools.fingerprints import source_hash
from healthcare_quality import __version__
from healthcare_quality.ai_studio import StudioService,ExperimentStore,StudioError,PROMPTS
from healthcare_quality.ai_schema import ALL_RULES,MODELS,SUITE_SCHEMA,DSL_VERSION,contract_fingerprint
from healthcare_quality.coverage_lab import CoverageLab
from healthcare_quality.quality_lab import QualityLab
from healthcare_quality.evaluation import dataset,retrieve
from healthcare_quality.showcase import summary,readiness,EVIDENCE
from healthcare_quality.assertion_quality import POLICY,policy_fingerprint
from healthcare_quality.catalog import get_catalog
from healthcare_quality.claims import ContractError, evaluate_claim
from healthcare_quality.workflow import ACTORS, MEMBERS, WORKFLOW_RULES, WORKFLOW_HASH, ClaimStore, WorkflowService, WorkflowError

ROOT=Path(__file__).resolve().parent.parent


def create_app(config=None):
    app=Flask(__name__)
    app.logger.setLevel(logging.INFO)
    app.config.update(MAX_CONTENT_LENGTH=16384,DATABASE=str(ROOT/".local/claims-v2.sqlite"))
    if config:app.config.update(config)
    service=WorkflowService(ClaimStore(app.config["DATABASE"]))
    app.extensions["workflow"]=service
    ai_path=app.config.get("AI_DATABASE") or str(Path(app.config["DATABASE"]).with_name("ai-v3.sqlite"))
    studio=StudioService(ExperimentStore(ai_path),app.config.get("AI_PROVIDER"))
    app.extensions["studio"]=studio
    lab=QualityLab(str(Path(ai_path).with_name("evaluation-v4.sqlite")),studio)
    app.extensions["quality_lab"]=lab
    coverage=CoverageLab(str(Path(ai_path).with_name("coverage-v55.sqlite")),studio)
    app.extensions["coverage_lab"]=coverage

    @app.before_request
    def request_trace():
        g.request_id=uuid4().hex;g.started=time.monotonic()

    @app.get("/api/ready")
    def ready():
        result=readiness([("claims",service.store.path,"claims"),("ai",studio.store.path,"ai_experiments"),("quality",lab.store.path,"ai_experiments"),("coverage",coverage.store.path,"ai_experiments"),("reliability",app.extensions["reliability"].store.path,"ai_experiments"),("research",app.extensions["research"].path,"ai_experiments"),("benefits",app.extensions["benefits"].path,"benefit_claims"),("audit",app.extensions["audit"].path,"review_audit"),("advanced",app.extensions["advanced"].store.path,"ai_experiments"),("advanced_evaluations",app.extensions["advanced_evaluations"].path,"ai_experiments"),("integrations",app.extensions["integrations"].path,"ai_experiments")])
        return jsonify(result),200 if result["status"]=="ready" else 503

    @app.get("/api/showcase")
    def showcase():return jsonify(summary())

    @app.get("/api/showcase/evidence/<key>")
    def showcase_evidence(key):
        path=ROOT/EVIDENCE[key] if key in EVIDENCE else None
        if path is None or not path.is_file():return jsonify(error="Evidence not available"),404
        return send_file(path,mimetype="application/json",as_attachment=True,download_name=key+".json")

    def actor_id():return g.identity["actor_id"] if getattr(g,"identity",None) else request.headers.get("X-Demo-Actor")

    def body():
        if not request.is_json:raise WorkflowError("INVALID_CONTENT_TYPE","Content-Type must be application/json",415,"HC-001")
        value=request.get_json(silent=True)
        if isinstance(value,dict) and "reviewer_label" in value and getattr(g,"identity",None):value["reviewer_label"]=g.identity["username"]
        return value

    @app.get("/")
    def index():return render_template("index.html",version=__version__)

    from healthcare_quality.showcase_lab import SCENARIOS, run as run_proof
    import threading
    proof_lock = threading.BoundedSemaphore(1)

    @app.get("/api/showcase-lab")
    def proof_catalog():
        return jsonify(scenarios=[{"id":key,"title":value} for key,value in SCENARIOS.items()],
                       provenance="Authored demonstrations; no inference or writes to your saved claims.",
                       comparison_available=(ROOT/"artifacts/showcase/provider-comparison.json").is_file())

    @app.get("/api/showcase-lab/comparison")
    def proof_comparison():
        path=ROOT/"artifacts/showcase/provider-comparison.json"
        if not path.is_file():return jsonify(status="not_recorded"),404
        return send_file(path,mimetype="application/json")

    @app.post("/api/showcase-lab/run")
    def proof_run():
        from urllib.parse import urlsplit
        origin=request.headers.get("Origin")
        if origin and urlsplit(origin).netloc != request.host:
            return jsonify(error="CROSS_ORIGIN_REJECTED"),403
        data=request.get_json(silent=True)
        if not request.is_json or not isinstance(data,dict) or set(data)!={"scenario"} or not isinstance(data["scenario"],str) or data["scenario"] not in SCENARIOS:
            return jsonify(error="INVALID_SCENARIO"),400
        if not proof_lock.acquire(blocking=False):return jsonify(error="DEMO_BUSY"),429
        try:return jsonify(run_proof(data["scenario"]))
        finally:proof_lock.release()

    @app.get("/api/health")
    def health():return jsonify(status="ok",version=__version__)

    @app.get("/api/catalog")
    def catalog():return jsonify({**get_catalog(),"workflow_rules":WORKFLOW_RULES,"workflow_contract_hash":WORKFLOW_HASH})

    @app.post("/api/evaluate")
    def evaluate():
        try:return jsonify(evaluate_claim(body()))
        except ContractError as error:return jsonify(error=str(error),rule_id="HC-001"),400

    @app.get("/api/workflow/fixtures")
    def fixtures():
        return jsonify(actors=ACTORS,members=MEMBERS,synthetic=True,identity_mode="demo selector; not authentication",workflow_contract_hash=WORKFLOW_HASH)

    @app.get("/api/claims")
    def claims():return jsonify(service.list(actor_id()))

    @app.post("/api/claims")
    def submit():return jsonify(service.submit(actor_id(),body())),201

    @app.get("/api/claims/<claim_id>")
    @app.get("/api/claims/<claim_id>/evidence")
    def detail(claim_id):return jsonify(service.get(actor_id(),claim_id))

    @app.post("/api/claims/<claim_id>/transitions")
    def transition(claim_id):return jsonify(service.transition(actor_id(),claim_id,body()))

    @app.errorhandler(WorkflowError)
    def workflow_error(error):
        result={"error":error.code,"message":str(error),"rule_id":error.rule}
        if error.details:result["details"]=error.details
        return jsonify(result),error.status

    @app.errorhandler(sqlite3.Error)
    def storage_error(error):return jsonify(error="STORAGE_ERROR",message="Storage operation failed; transaction was rolled back",rule_id="WF-006"),503

    @app.errorhandler(RequestEntityTooLarge)
    def oversized(error):return jsonify(error="Request exceeds 16 KiB",rule_id="HC-001"),413

    @app.get("/api/ai/config")
    def ai_config():return jsonify(version=__version__,dsl_version=DSL_VERSION,rules=list(ALL_RULES.values()),models=list(MODELS),strategies=PROMPTS,schema=SUITE_SCHEMA,reference_fingerprint=reference.fingerprint(),reference_version=reference.VERSION,assertion_policy=POLICY,assertion_policy_fingerprint=policy_fingerprint(),contract_fingerprint=contract_fingerprint(),execution_mode="Approved declarative cases; fresh temporary databases")

    @app.get("/api/ai/provider")
    def ai_provider():return jsonify(studio.provider.status())

    @app.get("/api/ai/experiments")
    def ai_list():return jsonify(experiments=studio.store.list())

    @app.post("/api/ai/experiments")
    def ai_generate():return jsonify(studio.generate(body())),201

    @app.get("/api/ai/experiments/<id>/pytest")
    def ai_pytest(id):
        response=app.response_class(studio.export_pytest(id),mimetype="text/x-python")
        response.headers["Content-Disposition"]="attachment; filename=test_ai_generated_"+id[:8]+".py"
        return response

    @app.get("/api/ai/experiments/<id>")
    @app.get("/api/ai/experiments/<id>/evidence")
    def ai_detail(id):return jsonify(studio.view(id))

    @app.put("/api/ai/experiments/<id>/cases/<case_id>")
    def ai_edit(id,case_id):return jsonify(studio.edit(id,case_id,body()))

    @app.post("/api/ai/experiments/<id>/review")
    def ai_review(id):return jsonify(studio.review(id,body(),_identity=getattr(g,"identity",None)))

    @app.get("/api/ai/experiments/<id>/reference-preview")
    def ai_reference_preview(id):return jsonify(studio.reference_preview(id))

    @app.post("/api/ai/experiments/<id>/apply-reference")
    def ai_apply_reference(id):return jsonify(studio.apply_reference(id,body())),201

    @app.post("/api/ai/experiments/<id>/correct")
    def ai_correct(id):return jsonify(studio.correct(id,body())),201

    @app.post("/api/ai/experiments/<id>/retry")
    def ai_retry(id):return jsonify(studio.retry(id,body())),201

    @app.post("/api/ai/experiments/<id>/execute")
    def ai_execute(id):return jsonify(studio.execute(id,body()))

    @app.errorhandler(StudioError)
    def studio_error(error):return jsonify(error=error.code,message=str(error)),error.status

    @app.get("/api/ai/focused-evaluator/config")
    def focused_config():return jsonify(version=focused.VERSION,plans=sorted(reference.PLANS),services=sorted(reference.SERVICES),models=list(MODELS))

    @app.post("/api/ai/focused-evaluator")
    def focused_generate():return jsonify(studio.generate_focused(body())),201

    @app.post("/api/coverage/gaps/<id>/generate")
    def coverage_gap_generate(id):return jsonify(coverage.close_gap(id,body())),201

    @app.post("/api/coverage/assemble-evaluators")
    def coverage_assemble():return jsonify(coverage.assemble_evaluators(body())),201

    @app.get("/api/coverage/scores/<id>/survivor-plan")
    def coverage_survivor_plan(id):
        value=request.args.get('variant','false')
        if value not in ('true','false'):raise StudioError('INVALID_REQUEST','variant must be true or false')
        return jsonify(coverage.survivor_plan(id,value=='true'))

    @app.post("/api/coverage/scores/<id>/generate-survivors")
    def coverage_generate_survivors(id):return jsonify(coverage.generate_survivors(id,body())),201

    @app.post("/api/coverage/compare")
    def coverage_compare():return jsonify(coverage.compare(body())),201

    @app.get("/api/coverage/dashboard")
    def coverage_dashboard():return jsonify(coverage.dashboard())

    @app.get("/api/coverage/records")
    def coverage_records():return jsonify(records=coverage.records())

    @app.get("/api/coverage/records/<id>")
    def coverage_record(id):return jsonify(coverage.record(id))

    @app.post("/api/coverage/analyze")
    def coverage_analyze():return jsonify(coverage.analyze(body())),201

    @app.post("/api/coverage/analyses/<id>/propose")
    def coverage_propose(id):return jsonify(coverage.propose(id,body())),201

    @app.post("/api/coverage/score")
    def coverage_score():return jsonify(coverage.score(body())),201

    @app.get("/api/quality/dataset")
    def quality_dataset():return jsonify(dataset())

    @app.get("/api/quality/records")
    def quality_records():return jsonify(records=lab.records())

    @app.get("/api/quality/records/<id>")
    def quality_record(id):return jsonify(lab.store.get(id))

    @app.post("/api/quality/comparisons")
    def quality_compare():return jsonify(lab.start(body())),202

    @app.post("/api/quality/investigations")
    def quality_investigate():return jsonify(lab.investigate(body())),201

    @app.get("/api/quality/retrieval")
    def quality_retrieve():
        try:return jsonify(method="Explicit rule-ID resolution; lexical overlap excludes IDs and namespace fragments",results=retrieve(request.args.get("q","")))
        except ValueError as error:raise StudioError("INVALID_REQUEST",str(error))

    @app.get("/api/verification")
    def verification():
        path=ROOT/"artifacts/verification.json"
        if not path.exists():return jsonify(status="not_run")
        data=json.loads(path.read_text())
        if data.get("source_hash")!=source_hash():data["status"]="stale"
        return jsonify(data)

    @app.get("/report")
    @app.get("/reports/<version>")
    def report(version=None):
        version=version or "v"+__version__.rsplit(".",1)[0]
        if version not in ("v1","v2","v3","v4","v5","v5.1","v5.2","v5.3","v5.4","v5.5","v5.6","v5.7","v5.8","v5.8_reliability","v5.9","v6.0","v6.1","v6.2","v6.3","v6.4","v6.5","v6.6","v6.7","v6.8","v6.9","v6.10","v6.11","v6.12","v7.0"):return jsonify(error="Report not found"),404
        path=ROOT/f"docs/{version.upper()}_REPORT.html"
        if not path.exists():return jsonify(error="Report is not available yet"),404
        return send_file(path)

    @app.after_request
    def response_headers(response):
        request_id=getattr(g,"request_id",uuid4().hex)
        duration=round((time.monotonic()-getattr(g,"started",time.monotonic()))*1000,2)
        response.headers["X-Request-ID"]=request_id
        response.headers["Server-Timing"]=f"app;dur={duration}"
        response.headers["Referrer-Policy"]="no-referrer"
        response.headers["X-Frame-Options"]="DENY"
        app.logger.info(json.dumps({"event":"http_request","request_id":request_id,"method":request.method,"route":request.url_rule.rule if request.url_rule else "unmatched","status":response.status_code,"duration_ms":duration},sort_keys=True))
        response.headers["X-Content-Type-Options"]="nosniff"
        response.headers["Cache-Control"]="no-store"
        return response
    from healthcare_quality.research_api import register
    register(app,body,actor_id)
    from healthcare_quality.design_api import register as register_design
    register_design(app,body)
    from healthcare_quality.investigation_api import register as register_investigations
    register_investigations(app,body)
    from healthcare_quality.traceability_api import register as register_traceability
    register_traceability(app,body)
    from healthcare_quality.effectiveness_api import register as register_effectiveness
    register_effectiveness(app)
    from healthcare_quality.auth import configure
    configure(app)
    return app
