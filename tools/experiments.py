"""Explicit local frozen comparison or export of retained partial/completed evidence."""
import argparse,json,threading
from pathlib import Path
from healthcare_quality.experiment_lab import ExperimentLab
from healthcare_quality.ollama_provider import OllamaProvider
from healthcare_quality.ai_schema import MODELS
from healthcare_quality.test_design import PROMPTS

def main():
 p=argparse.ArgumentParser();p.add_argument('--models',nargs='+',choices=MODELS);p.add_argument('--prompts',nargs='+',choices=PROMPTS,default=['focused-v68']);p.add_argument('--tasks',nargs='+',default=['XP-03']);p.add_argument('--repeats',type=int,default=1);p.add_argument('--modes',nargs='+',default=['ai_expectations','calculator_control']);p.add_argument('--state',type=Path,default=Path('.local/experiments-v612.sqlite'));p.add_argument('--output',type=Path,required=True);p.add_argument('--export-id');a=p.parse_args()
 if a.output.exists():p.error('Evidence exists; choose a fresh output')
 provider=OllamaProvider('advanced');lab=ExperimentLab(a.state,provider,threading.BoundedSemaphore(1))
 if a.export_id:r=lab.get(a.export_id)
 else:
  if not a.models:p.error('Select explicit installed models')
  installed={m['name'] for m in provider.status()['models']}
  if not set(a.models)<=installed:p.error('Selected model is not installed/running locally; no download or cloud fallback')
  r=lab.start(dict(models=a.models,prompts=a.prompts,tasks=a.tasks,repeats=a.repeats,modes=a.modes))
 a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(dict(id=r['id'],state=r['state'],summary=r['summary']),indent=2));return 0 if r['state']=='completed' else 1
if __name__=='__main__':raise SystemExit(main())
