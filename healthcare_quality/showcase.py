"""Read-only showcase provenance; observed runtime readiness is separate from test evidence."""
from contextlib import closing
import json
from pathlib import Path
import sqlite3
import time
from urllib.parse import quote
from healthcare_quality import __version__
from tools.fingerprints import source_hash
ROOT=Path(__file__).resolve().parents[1]
EVIDENCE={"verification":"artifacts/verification.json","development":"artifacts/v4/development-comparison.json","reserved":"artifacts/v4/held_out-comparison.json","investigation":"artifacts/v4/live-investigation.json","sensitivity":"artifacts/v4/assertion-sensitivity.json","rehearsal":"artifacts/v5/deployment-rehearsal.json","reliability":"artifacts/v5.8/reserved-live-online.json","assistant":"artifacts/v5.9/live-ai-investigation.json","mutations":"artifacts/v6.1/mutation-sweep.json","resilience":"artifacts/v6.1/resilience-rehearsal.json","reproducibility":"artifacts/v6.2/demo-rehearsal.json","focused":"artifacts/v5.7/focused-measurement.json","showcase":"artifacts/showcase/deterministic-evidence.json","providers":"artifacts/showcase/provider-comparison.json"}

def verification():
    try:
        result=json.loads((ROOT/EVIDENCE["verification"]).read_text())
        if result.get("source_hash")!=source_hash():result["status"]="stale"
        return result
    except (OSError,ValueError):return {"status":"not_available"}

def readiness(stores):
    checks={}
    # One shared budget tolerates brief writer contention without multiplying
    # the maximum probe wait by the number of databases.
    deadline=time.monotonic()+1.0
    for label,path,table in stores:
        try:
            with closing(sqlite3.connect("file:"+quote(str(Path(path).resolve()))+"?mode=rw",uri=True,timeout=max(0.0,deadline-time.monotonic()))) as db:
                db.execute("SELECT 1 FROM "+table+" LIMIT 1").fetchall()
            checks[label]="ready"
        except sqlite3.Error:checks[label]="unavailable"
    return {"status":"ready" if all(v=="ready" for v in checks.values()) else "unavailable","version":__version__,"storage":checks,"ai":"Optional; not probed by readiness","scope":"Databases can open and expected tables can be queried. Does not prove write availability, model quality or production readiness."}

def summary():
    return {"version":__version__,"verification":verification(),"milestones":[
        {"version":"V1","title":"Written contracts","outcome":"8 synthetic plan configurations; deterministic claim evaluation and rule traces","page":"workspace"},
        {"version":"V2","title":"Transactional workflows","outcome":"Ownership, duplicates, ordered approvals, simulated ledger and atomic history","page":"workflow"},
        {"version":"V3","title":"Local AI test creation","outcome":"Ollama proposals, explicit review, isolated execution and trusted pytest export","page":"ai"},
        {"version":"V4","title":"Measure AI quality","outcome":"16 saved live proposals; scoring exposes missing assertions and wrong oracles","page":"evaluation"},
        {"version":"V5","title":"Repeatable showcase release","outcome":"Validated packages, local activation/rollback, readiness and request tracing","page":"showcase"}],
        "extensions":[{"version":"V5.8","title":"Reserved AI evaluations","outcome":"Repeated raw model measurements; no repairs or approvals"},{"version":"V5.9","title":"Grounded investigation","outcome":"Facts, rule citations, triage and separate AI hypotheses"},{"version":"V6.0","title":"Versioned benefit lifecycle","outcome":"Lines, family accumulators, adjustments, appeals and reversals"},{"version":"V6.1","title":"Prove resilience","outcome":"HTTP parity, concurrency, rollback and broader mutation checks"},{"version":"V6.2","title":"Reproducible showcase","outcome":"Fresh demo, authenticated review option and multi-browser CI"}],
        "evidence":[{"id":key,"available":(ROOT/path).is_file(),"url":"/api/showcase/evidence/"+key} for key,path in EVIDENCE.items()],
        "repository":"https://github.com/kilicerdal/healthcare-quality-lab","repository_visibility":"public","deployment_scope":"Loopback local demonstration. GitHub CI status is recorded separately; no public healthcare service is deployed."}
