"""Explain V8.1 survivors with authored healthy multi-claim witnesses, not AI credit."""
from pathlib import Path
import argparse,json
from healthcare_quality.effectiveness import compare,suite_run,variants,reduce_prefix
from healthcare_quality.test_design import compile_plan
from tools.fingerprints import source_hash
ROOT=Path(__file__).resolve().parents[1]
SURVIVORS=('AST-294','AST-321','AST-324','AST-345','AST-348','AST-355')
def audit():
 data=json.loads((ROOT/'healthcare_quality/data/fault_witnesses_v82.json').read_text());cases=[compile_plan(p) for p in data['plans']];score=compare({'authored_v82_multi_claim':cases});rows=[]
 for v in variants():
  if v['id'] not in SURVIVORS:continue
  witnesses=[c for c in cases if not suite_run([c],v)['passed']]
  rows.append(dict(id=v['id'],before=v['before'],after=v['after'],detected=bool(witnesses),witness_cases=[c['id'] for c in witnesses],minimal_prefix=reduce_prefix(witnesses[0],v['id']) if witnesses else None))
 return dict(kind='v82_surviving_fault_investigation',source_hash=source_hash(),origin=data['origin'],previous_ai_detection=dict(detected=21,total=27),investigated=len(rows),closed=sum(r['detected'] for r in rows),faults=rows,authored_effectiveness=score,scope='Actual trusted production AST mutations; authored witnesses use independent reference expectations. Never count these as AI-generated tests. Prior live AI cases lacked accumulated balances needed by these faults.')
def main():
 p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 if a.output.exists():p.error('Choose a fresh evidence path')
 r=audit();a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(r,indent=2)+'\n');print(json.dumps({k:r[k] for k in ('investigated','closed','source_hash')},indent=2));return 0 if r['closed']==6 else 1
if __name__=='__main__':raise SystemExit(main())
