"""Opt-in survivor-targeting demonstration using actual loopback Ollama.
Input/action plans are authored. Expectations are generated, independently checked,
and explicitly reviewed by a labeled engineering operator before fault scoring.
"""
from copy import deepcopy
import json
from pathlib import Path
from healthcare_quality.ai_studio import StudioService,ExperimentStore
from healthcare_quality.coverage_lab import CoverageLab
from healthcare_quality.survivors import group_match
from healthcare_quality.evaluation import signature
ROOT=Path(__file__).resolve().parents[1]

def repair_candidate(studio,record,reviewer,on_snapshot):
    """Opt-in engineering operation, not a product auto-review loop.
    Reload persisted assessment after every model call; respect the shared budget.
    Reference replacements stay unapproved and retain their distinct origin.
    """
    record=studio.view(record['id']);actions={'correction_ids':[],'reference_assisted':False}
    for _ in range(2):
        if record['proposals'] and all(p['review_ready'] for p in record['proposals']):break
        if not record['proposals'] or not all(p['valid'] for p in record['proposals']) or not record.get('survivor_sequence_matches') or not record['correction_budget']['remaining']:break
        result=studio.correct(record['id'],{'expected_revision':record['revision'],**reviewer})
        record=studio.view(result['id']);actions['correction_ids'].append(record['id']);on_snapshot(record)
    if not (record['proposals'] and all(p['review_ready'] for p in record['proposals'])):
        try:preview=studio.reference_preview(record['id'])
        except Exception:return record,actions
        group=record.get('survivor_source',{}).get('group')
        if group and len(preview['cases'])==1 and group_match(group,preview['cases'][0]):
            result=studio.apply_reference(record['id'],{k:preview[k] for k in ('expected_revision','reference_fingerprint','preview_hash')}|{**reviewer,'reference_confirmed':True})
            record=studio.view(result['id']);actions['reference_assisted']=True;on_snapshot(record)
    return record,actions

def run(output=None,state_dir=None):
    out=Path(output) if output else ROOT/'artifacts/v5.6';out.mkdir(parents=True,exist_ok=True);destination=out/'live-survivor-demo.json'
    if destination.exists():raise RuntimeError('Preserve prior evidence; refuse overwrite')
    state=Path(state_dir) if state_dir else ROOT/'.local/v56-live'
    studio=StudioService(ExperimentStore(state/'studio.sqlite'))
    lab=CoverageLab(state/'coverage.sqlite',studio)
    provider=studio.provider.status()
    if not provider['available']:raise RuntimeError('Actual local Ollama unavailable; no fixture fallback')
    original=json.loads((ROOT/'artifacts/v5.5/live-gap-demo.json').read_text())
    baseline_selection=[]
    for row in original['cases']:
        r=json.loads((ROOT/f"artifacts/v5.5/proposal-{row['approved_id']}.json").read_text())
        studio.store.create(r);baseline_selection.append({'id':r['id'],'expected_revision':r['revision']})
    before=lab.score({'experiments':baseline_selection});assert before['detected']==2 and before['applicable']==12
    (out/'baseline-score.json').write_text(json.dumps(before,indent=2)+'\n')
    plans={name:lab.survivor_plan(before['id'],name=='alternate') for name in ('core','alternate')}
    literals=json.loads((ROOT/'tests/data/v56_scenarios.json').read_text())['cases']
    record={'state':'running','provider':provider,'baseline_score_id':before['id'],'baseline_detected':2,'applicable':12,'frozen_plans':plans,'proposals':[],
            'scope':'Known-seed targeting with authored input/action plans and provider input constraints. The model supplies expectations. Alternate plans and literal expected answers frozen before inference; these are development variations, not blind holdouts. Operator attestations are explicitly automated engineering reviews. Corrections/reference assistance/manual edits, if used, are reported separately.'}
    def save():destination.write_text(json.dumps(record,indent=2)+'\n')
    def snapshot(r): (out/('proposal-'+r['id']+'.json')).write_text(json.dumps(r,indent=2)+'\n')
    reviewer={'reviewer_label':'Codex engineering operator (automated attestation)','review_note':'Checked planned actions, literal development answers and independent reference before healthy-baseline and seeded-defect scoring. Local label, not authenticated human identity.'}
    scores={};selections={}
    save()
    for name in ('core','alternate'):
        plan=plans[name];selected=[]
        for group in plan['groups']:
            r=lab.generate_survivors(before['id'],{'group_id':group['id'],'plan_hash':plan['plan_hash'],'model':'qwen2.5-coder:3b','variant':name=='alternate'});snapshot(r)
            row={'set':name,'group':group['id'],'original_id':r['id'],'corrections':[],'reference_assisted':False,'manual_edit':False};record['proposals'].append(row);save()
            r,actions=repair_candidate(studio,r,reviewer,snapshot)
            row['corrections']=actions['correction_ids'];row['reference_assisted']=actions['reference_assisted'];save()
            expected=literals[('variant-' if name=='alternate' else 'core-')+group['id']]
            valid=len(r['proposals'])==1 and r['proposals'][0]['review_ready'] and group_match(group,r['proposals'][0]['case'])
            literal_match=valid and [s['expect'] for s in r['proposals'][0]['case']['steps']]==[s['expect'] for s in expected['steps']]
            row.update(final_id=r['id'],ready_and_plan_matched=bool(valid),literal_match=bool(literal_match),origin=r.get('expectation_origin','original_ai'));save()
            if not literal_match:
                print('UNRESOLVED',name,group['id'],r['id'],flush=True);continue
            r=studio.review(r['id'],{'expected_revision':r['revision'],'approved_ids':[r['proposals'][0]['case']['id']],**reviewer,'expectations_checked':True});snapshot(studio.view(r['id']));selected.append({'id':r['id'],'expected_revision':r['revision']})
            print('GENERATED',name,group['id'],'reviewed',r['id'],'corrections',len(row['corrections']),flush=True)
        selections[name]=selected
        if selected:
            score=lab.score({'experiments':selected});scores[name]=score
            (out/(name+'-score.json')).write_text(json.dumps(score,indent=2)+'\n')
            record[name+'_score']={k:score.get(k) for k in ('id','state','detected','applicable','score','errors')}
            if score['applicable']==before['applicable']:
                comparison=lab.compare({'before_id':before['id'],'after_id':score['id']});(out/(name+'-comparison.json')).write_text(json.dumps(comparison,indent=2)+'\n');record[name+'_comparison_id']=comparison['id']
        save()
    record['state']='completed';record['selected']=selections;record['summary']={'core_detected':scores.get('core',{}).get('detected'),'alternate_detected':scores.get('alternate',{}).get('detected'),'initial_generation_calls':len(record['proposals']),'correction_calls':sum(len(r['corrections']) for r in record['proposals']),'reference_assisted_cases':sum(r['reference_assisted'] for r in record['proposals']),'manual_edits':sum(r['manual_edit'] for r in record['proposals'])};save();print(json.dumps(record['summary']),flush=True)

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--output');parser.add_argument('--state-dir');args=parser.parse_args();run(args.output,args.state_dir)
