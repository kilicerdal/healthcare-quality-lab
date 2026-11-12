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
from healthcare_quality.quality_lab import QualityLab
from healthcare_quality.evaluation import dataset,retrieve
from healthcare_quality.showcase import summary,readiness,EVIDENCE
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

    @app.before_request
    def request_trace():
        g.request_id=uuid4().hex;g.started=time.monotonic()

    @app.get("/api/ready")
    def ready():
        result=readiness([("claims",service.store.path,"claims"),("ai",studio.store.path,"ai_experiments"),("quality",lab.store.path,"ai_experiments")])
        return jsonify(result),200 if result["status"]=="ready" else 503

    @app.get("/api/showcase")
    def showcase():return jsonify(summary())

    @app.get("/api/showcase/evidence/<key>")
    def showcase_evidence(key):
        path=ROOT/EVIDENCE[key] if key in EVIDENCE else None
        if path is None or not path.is_file():return jsonify(error="Evidence not available"),404
        return send_file(path,mimetype="application/json",as_attachment=True,download_name=key+".json")

    def body():
        if not request.is_json:raise WorkflowError("INVALID_CONTENT_TYPE","Content-Type must be application/json",415,"HC-001")
        return request.get_json(silent=True)

    @app.get("/")
    def index():return render_template("index.html",version=__version__)

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
    def claims():return jsonify(service.list(request.headers.get("X-Demo-Actor")))

    @app.post("/api/claims")
    def submit():return jsonify(service.submit(request.headers.get("X-Demo-Actor"),body())),201

    @app.get("/api/claims/<claim_id>")
    @app.get("/api/claims/<claim_id>/evidence")
    def detail(claim_id):return jsonify(service.get(request.headers.get("X-Demo-Actor"),claim_id))

    @app.post("/api/claims/<claim_id>/transitions")
    def transition(claim_id):return jsonify(service.transition(request.headers.get("X-Demo-Actor"),claim_id,body()))

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
    def ai_config():return jsonify(version=__version__,dsl_version=DSL_VERSION,rules=list(ALL_RULES.values()),models=list(MODELS),strategies=PROMPTS,schema=SUITE_SCHEMA,contract_fingerprint=contract_fingerprint(),execution_mode="Approved declarative cases; fresh temporary databases")

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
    def ai_detail(id):return jsonify(studio.store.get(id))

    @app.put("/api/ai/experiments/<id>/cases/<case_id>")
    def ai_edit(id,case_id):return jsonify(studio.edit(id,case_id,body()))

    @app.post("/api/ai/experiments/<id>/review")
    def ai_review(id):return jsonify(studio.review(id,body()))

    @app.post("/api/ai/experiments/<id>/execute")
    def ai_execute(id):return jsonify(studio.execute(id,body()))

    @app.errorhandler(StudioError)
    def studio_error(error):return jsonify(error=error.code,message=str(error)),error.status

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
        try:return jsonify(method="Lexical overlap plus exact rule-ID boost; not vector search",results=retrieve(request.args.get("q","")))
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
    def report(version="v5"):
        if version not in ("v1","v2","v3","v4","v5"):return jsonify(error="Report not found"),404
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
    return app
