"""Reproducible live local-model measurement, separate from offline CI tests.
Use fresh state/output directories. All failures and corrections are retained.
"""
from pathlib import Path
import json,sys,time
ROOT=Path(__file__).resolve().parents[1]
from healthcare_quality.ai_studio import StudioService,ExperimentStore
from healthcare_quality.coverage_lab import CoverageLab
import argparse
from healthcare_quality.ai_schema import MODELS
parser=argparse.ArgumentParser(description="Measure the frozen focused-evaluator development cohort with real local Ollama. No reference replacement. Not a blind holdout.")
parser.add_argument('--model',choices=MODELS,default='qwen3.5:27b');parser.add_argument('--state-dir',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
args=parser.parse_args()
if args.output.exists():parser.error('Choose a fresh output directory; previous evidence is never overwritten.')
def review_request(record):return dict(expected_revision=record['revision'],approved_ids=[p['case']['id'] for p in record['proposals']],reviewer_label='Scripted development evaluation',review_note='Literal frozen expectation, independent reference and calculation checks passed. This is scripted evaluation, not a human review.',expectations_checked=True)

from healthcare_quality.ollama_provider import OllamaProvider
out=args.output.resolve();out.mkdir(parents=True);state=args.state_dir.resolve();state.mkdir(parents=True,exist_ok=True)
studio=StudioService(ExperimentStore(state/'studio.sqlite'),OllamaProvider());lab=CoverageLab(state/'coverage.sqlite',studio)
cohort=json.loads((ROOT/'tests/data/v57_evaluation.json').read_text());results=[]
existing={json.dumps(studio.store.get(x['id']).get('focused_source',{}).get('data'),sort_keys=True):studio.store.get(x['id']) for x in studio.store.list() if not studio.store.get(x['id']).get('correction_of')}
for item in cohort['cases']:
 r=existing.get(json.dumps(item['data'],sort_keys=True)) or studio.generate_focused({'data':item['data'],'model':args.model});root=r['id'];raw=studio.view(root);correct=all(p['review_ready'] for p in raw['proposals']) and bool(raw['proposals']);literal=bool(raw['proposals']) and raw['proposals'][0]['case']['steps'][0]['expect']==item['expect']
 for attempt in range(2):
  if all(p['review_ready'] for p in studio.view(r['id'])['proposals']) and r['proposals']:break
  try:r=studio.correct(r['id'],{'expected_revision':r['revision'],'reviewer_label':'V5.7 measured development review','review_note':'Retain raw failure and request explicit AI expectation correction; no reference replacement.'})
  except Exception as e:print('Correction unavailable',type(e).__name__,str(e),flush=True);break
 v=studio.view(r['id']);ready=bool(v['proposals']) and all(p['review_ready'] for p in v['proposals']);run=None
 if ready:
  r=studio.review(r['id'],review_request(r));run=studio.execute(r['id'],{'expected_revision':r['revision']});r=studio.store.get(r['id'])
 row={'scenario':item['id'],'root_id':root,'final_id':r['id'],'raw_correct':correct,'raw_literal_match':literal,'final_ready':ready,'origin':r.get('expectation_origin','original_ai'),'run_status':run['status'] if run else None};results.append(row)
 for rec in studio.store.list():
  full=studio.store.get(rec['id']);(out/(rec['id']+'.json')).write_text(json.dumps(full,indent=2)+'\n')
 (out/'focused-measurement.json').write_text(json.dumps({'scope':cohort['scope'],'results':results,'metrics':lab.focused_metrics()},indent=2)+'\n')
 print(json.dumps(row),flush=True)
print('FINISHED',json.dumps(lab.focused_metrics()),flush=True)
