"""Opt-in reserved repeated local inference. Never approves, repairs or executes drafts."""
import argparse,json
from pathlib import Path
from healthcare_quality.reliability import ReliabilityLab
p=argparse.ArgumentParser();p.add_argument('--models',nargs='+',default=['qwen3.5:27b']);p.add_argument('--tasks',nargs='+',default=['R01','R02','R03','R04']);p.add_argument('--repeats',type=int,default=2);p.add_argument('--state',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
if a.output.exists():p.error('Refusing to overwrite evidence')
lab=ReliabilityLab(a.state);r=lab.start(dict(models=a.models,task_ids=a.tasks,repeats=a.repeats),background=False);a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r['summary'],indent=2));raise SystemExit(0 if r['state']=='completed' else 1)
