"""Fresh, explicitly labeled demo replay. No model inference; existing state is never reused."""
from pathlib import Path
from uuid import uuid4
from copy import deepcopy
import argparse,json,time
from healthcare_quality.app import create_app
from healthcare_quality.ai_studio import now
from healthcare_quality.ai_schema import digest,contract_fingerprint
from healthcare_quality.ai_runner import run_cases
from healthcare_quality.investigator import analyze
from tools.fingerprints import source_hash
ROOT=Path(__file__).resolve().parents[1]

def seed(state,output):
    state=Path(state);output=Path(output)
    if output.exists() or state.exists() and any(state.iterdir()):raise ValueError('Choose fresh empty demo state and output; interactive data is never overwritten')
    state.mkdir(parents=True,exist_ok=True);app=create_app(dict(DATABASE=str(state/'claims-v2.sqlite')));s=app.extensions['studio'];coverage=app.extensions['coverage_lab'];ids={}
    paths={'assembly':'artifacts/v5.7/core-assembly.json','workflow':'artifacts/v5.7/9bacd245fceb4eec866a075e8da6cc7e.json','zero':'artifacts/v5.7/9622713a4a004b51a79df1a79b4ce9bd.json','replay':'artifacts/v5.7/9c5fb236a6f24b2daf9af48eba040f25.json','baseline-eval':'artifacts/v5.5/proposal-ed66bafce6264ad8ae0bc4e917511a4b.json','baseline-flow':'artifacts/v5.5/proposal-d60cf809910c486cbf44fbe6f670d35a.json'}
    for key,path in paths.items():
        original=json.loads((ROOT/path).read_text());r=deepcopy(original);r.update(id=uuid4().hex,created_at=now(),state='proposed',revision=1,approved_ids=[],approval=None,runs=[],history=[],demo_source=dict(path=path,original_id=original['id'],artifact_hash=digest(original),live_inference=False,label='Replay of saved synthetic AI evidence; no new model request'))
        for x in ('operation','pending_run','correction_of','correction_root_id','reference_assisted_of','retry_of'):r.pop(x,None)
        s.store.create(r);r=s.review(r['id'],dict(expected_revision=1,approved_ids=[p['case']['id'] for p in r['proposals']],reviewer_label='Scripted demo replay',review_note='Replayed saved synthetic input/expectation snapshots passed current independent checks. This is not a new AI inference or authenticated human review.',expectations_checked=True));run=s.execute(r['id'],dict(expected_revision=r['revision']));assert run['status']=='passed';ids[key]=r['id']
    def score(keys):return coverage.score(dict(experiments=[dict(id=ids[k],expected_revision=s.store.get(ids[k])['revision']) for k in keys]))
    before=score(['baseline-eval','baseline-flow']);after=score(['assembly','workflow','zero','replay']);comparison=coverage.compare(dict(before_id=before['id'],after_id=after['id']));assert after['detected']==12 and coverage.dashboard()['counts']['missing_gaps']==0
    # Known synthetic fault demonstration in a separate labeled frozen run.
    r=s.store.get(ids['assembly']);cases=s._approved_cases(r);fault=run_cases(cases,evaluation_defect='deductible');fault.update(id=uuid4().hex,experiment_id=r['id'],at=now(),status='failed',approval=deepcopy(r['approval']),approved_cases=cases,contract_fingerprint=contract_fingerprint(),source_hash=source_hash(),revision=r['revision'],known_controlled_fault='deductible',scope='Deliberately seeded demonstration, not an observed unseeded application defect')
    with s.store.transaction() as db:r['runs'].append(fault);s.store.save(db,r)
    triage=analyze(r,fault['id']);investigation=dict(id=uuid4().hex,created_at=now(),kind='grounded_investigation',state='completed',analysis=triage,ai=None,demo=True);app.extensions['research'].create(investigation)
    for path in ('artifacts/v5.8/reserved-live.json','artifacts/v5.8/reserved-live-online.json'):
        p=ROOT/path
        if p.exists():
            recorded=json.loads(p.read_text());recorded['demo_source']=dict(path=path,live_inference=False);app.extensions['reliability'].store.create(recorded)
    benefits=app.extensions['benefits'];b=benefits.operate('customer-m100',dict(operation_key='demo-benefit-submit',id='DEMO-BENEFIT',member_id='M100',plan_id='commercial_ppo',service_date='2026-03-01',lines=[dict(id='L1',service='medical',allowed_cents=100000),dict(id='L2',service='dental',allowed_cents=5000)]),'submit');b=benefits.operate('finance-demo',dict(operation_key='demo-benefit-pay',expected_revision=b['revision']),'pay',b['id'])
    result=dict(status='passed',demo=True,live_model_requests=0,source_hash=source_hash(),state_dir=str(state),experiments=ids,before_score=before['id'],after_score=after['id'],comparison=comparison['id'],before_detected=before['detected'],after_detected=after['detected'],missing_gaps=coverage.dashboard()['counts']['missing_gaps'],investigation=investigation['id'],fault_run=fault['id'],benefit_claim=b['id'],scope='Fresh replay state with copied saved evidence, current checks and explicit scripted approvals. Original source artifacts and interactive databases remain unchanged.')
    output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(result,indent=2)+'\n');return result
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--state-dir',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();print(json.dumps(seed(a.state_dir,a.output),indent=2))
