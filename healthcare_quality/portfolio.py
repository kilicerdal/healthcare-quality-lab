"""V7 reviewer overview. Historical model results never become current verification."""
from pathlib import Path
import json
from healthcare_quality import __version__
from healthcare_quality.ai_schema import digest
from tools.fingerprints import source_hash
ROOT=Path(__file__).resolve().parents[1]
VERSIONS=('6.8','6.9','6.10','6.11','6.12','7.0')

def overview():
    fingerprint=source_hash();p=ROOT/'artifacts/verification.json';verification=json.loads(p.read_text()) if p.exists() else {'status':'not_run'}
    verification={k:verification.get(k) for k in ('status','version','source_hash','tests_passed','tests_total','tests_failed','tests_skipped','recorded_at','categories')}
    if verification.get('source_hash')!=fingerprint and verification['status']!='not_run':verification['status']='stale'
    models=[];p=ROOT/'artifacts/v6.12/live-model-prompt-comparison.json'
    if p.exists():
        saved=json.loads(p.read_text());models=[dict(model=s['model'],prompt_version=s['prompt_version'],mode=s['mode'],eligible=s['eligible'],attempted=s['attempted'],provider_errors=s['provider_errors'],historical=True) for s in saved['summary']]
    return dict(version=__version__,source_hash=fingerprint,verification=verification,reports=[dict(version=v,url='/reports/v'+v) for v in VERSIONS],historical_model_comparison=models,milestones=[dict(version=v,title=t) for v,t in zip(VERSIONS,['Plan-first AI test design','Sealed evidence and grounded hypotheses','Requirement/assertion/execution traceability','Production mutation and property effectiveness','Frozen model/prompt comparisons','Reproducible guided showcase'])],scope='Synthetic engineering lab. The guided control is authored, optional models run only on explicit requests, and historical measurements remain labeled. No paid calls, real eligibility or real money.')
