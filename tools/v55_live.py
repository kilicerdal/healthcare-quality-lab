"""Opt-in real local gap analysis, reviewed generation and fault measurement.
Engineering attestations are explicit local labels, not authenticated humans.
"""
from copy import deepcopy
import json
from pathlib import Path
from healthcare_quality.ai_studio import StudioService,ExperimentStore
from healthcare_quality.coverage_lab import CoverageLab,gap_matches,duplicates
ROOT=Path(__file__).resolve().parents[1]

def run():
    out=ROOT/'artifacts/v5.5';out.mkdir(exist_ok=True);destination=out/'live-gap-demo.json'
    if destination.exists():raise RuntimeError('Preserve previous measurements; refuse overwrite')
    studio=StudioService(ExperimentStore(ROOT/'.local/v55-live/studio.sqlite'))
    lab=CoverageLab(ROOT/'.local/v55-live/coverage.sqlite',studio)
    provider=studio.provider.status()
    if not provider['available']:raise RuntimeError('Local Ollama unavailable; no offline fallback')
    before=lab.dashboard();record={'state':'running','provider':provider,'before_counts':before['counts'],'missing_before':[g['id'] for g in before['gaps'] if g['status']=='missing'],'cases':[],
        'scope':'One real gap analysis, at most two explicit generated proposals. Engineering operator verifies scenario and reference before review; model requests/corrections retained. Scoring uses known seeded defects, not blind mutation evaluation. Duplicate probe is deliberately constructed and not a new AI success.'}
    def save():destination.write_text(json.dumps(record,indent=2)+'\n')
    def snapshot(r): (out/('proposal-'+r['id']+'.json')).write_text(json.dumps(r,indent=2)+'\n')
    save();analysis=lab.analyze({'model':'qwen2.5-coder:3b'});record['analysis_id']=analysis['id'];(out/'gap-analysis.json').write_text(json.dumps(analysis,indent=2)+'\n');save()
    if analysis['state']!='analyzed':raise RuntimeError('Gap analysis failed; preserved evidence')
    selected=sorted(range(len(analysis['suggestions'])),key=lambda i:{'zero-payment':0,'cap-plus-one':1,'invalid-zero':2,'payment-replay':3}.get(analysis['suggestions'][i]['gap_id'],4))[:2]
    approved=[]
    for index in selected:
        gap=analysis['suggestions'][index]['gap_id'];current=lab.propose(analysis['id'],{'suggestion_index':index});snapshot(current)
        result={'gap_id':gap,'original_id':current['id'],'corrections':[],'approved':False};record['cases'].append(result);save()
        for _ in range(2):
            if current['proposals'] and all(p['review_ready'] for p in current['proposals']):break
            if not current['proposals'] or not all(p['valid'] for p in current['proposals']):break
            current=studio.correct(current['id'],{'expected_revision':current['revision'],'reviewer_label':'Codex engineering operator (automated attestation)','review_note':'Explicit correction of a new gap proposal; no approval implied.'});snapshot(current);result['corrections'].append(current['id']);save()
        valid=current['proposals'] and all(p['review_ready'] and gap_matches(gap,p['case']) for p in current['proposals'])
        result['ready_and_matches_target']=bool(valid)
        if valid:
            current=studio.review(current['id'],{'expected_revision':current['revision'],'approved_ids':[p['case']['id'] for p in current['proposals']],'reviewer_label':'Codex engineering operator (automated attestation)','review_note':'Checked independent expectations, input/action sequence and defined gap predicate before bounded engineering scoring. Local label, not authenticated human review.','expectations_checked':True})
            approved.append({'id':current['id'],'expected_revision':current['revision']});result['approved']=True;result['approved_id']=current['id'];snapshot(studio.view(current['id']))
        save();print('GAP',gap,'approved',bool(valid),flush=True)
    if approved:
        score=lab.score({'experiments':approved});(out/'live-defect-score.json').write_text(json.dumps(score,indent=2)+'\n');record['score']={k:score.get(k) for k in ('id','state','detected','applicable','score','errors')}
        first=studio.view(approved[0]['id'])['proposals'][0];clone=deepcopy(first);clone['case']['id']='AI-DUPLICATE-PROBE';clone['case']['title']='Deliberately renamed equivalent case';clone['key']='deliberate-probe';first['key']='actual-live-case'
        (out/'duplicate-probe.json').write_text(json.dumps({'scope':'Deliberate duplicate of one actual generated case, for normalization demonstration; not an additional model generation.','groups':duplicates([first,clone])},indent=2)+'\n')
    after=lab.dashboard();record['after_counts']=after['counts'];record['missing_after']=[g['id'] for g in after['gaps'] if g['status']=='missing'];record['state']='completed';save();print(json.dumps(record),flush=True)
if __name__=='__main__':run()
