"""Run isolated external-service rehearsals; no provider or interactive-state writes."""
import argparse,json
from pathlib import Path
from healthcare_quality.integration_scenarios import SCENARIOS,rehearse
from tools.fingerprints import source_hash

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--scenarios',nargs='+',choices=SCENARIOS,default=list(SCENARIOS));p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    if a.output.exists():p.error('Use a fresh evidence path')
    rows=[rehearse(s) for s in a.scenarios];r=dict(source_hash=source_hash(),passed=all(x['passed'] for x in rows),results=rows,live_model_calls=0)
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(dict(passed=r['passed'],scenarios=len(rows),assertions=sum(len(x['assertions']) for x in rows))));return 0 if r['passed'] else 1
if __name__=='__main__':raise SystemExit(main())
