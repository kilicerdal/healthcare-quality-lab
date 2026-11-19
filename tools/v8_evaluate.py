"""Explicit bounded local evaluation on the new family-separated cohort."""
import argparse,json,threading
from pathlib import Path
from healthcare_quality.evaluation_v8 import cohort,matrix
from healthcare_quality.experiment_lab import ExperimentLab
from healthcare_quality.ollama_provider import OllamaProvider
from healthcare_quality.ai_schema import MODELS
from healthcare_quality.test_design import PROMPTS

def main():
 p=argparse.ArgumentParser();p.add_argument('--models',nargs='+',choices=MODELS,required=True);p.add_argument('--prompts',nargs='+',choices=PROMPTS,default=['focused-v68']);p.add_argument('--tasks',nargs='+',required=True);p.add_argument('--repeats',type=int,default=2);p.add_argument('--mode',choices=['ai_expectations','calculator_control'],default='calculator_control');p.add_argument('--state',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--dry-run',action='store_true');a=p.parse_args()
 try:protocol=matrix(a.tasks,a.models,a.prompts,a.repeats)
 except ValueError as e:p.error(str(e))
 if a.dry_run:print(json.dumps(protocol,indent=2));return 0
 if a.output.exists():p.error('Choose a new output file; retained evidence is never overwritten')
 provider=OllamaProvider('advanced')
 if a.mode=='ai_expectations' and not set(a.models)<={x['name'] for x in provider.status()['models']}:p.error('Select installed local models; no downloads or cloud fallback')
 lab=ExperimentLab(a.state,provider,threading.BoundedSemaphore(1),cohort());r=lab.start(dict(models=a.models,prompts=a.prompts,tasks=a.tasks,repeats=a.repeats,modes=[a.mode]));a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(dict(id=r['id'],state=r['state'],summary=r['summary']),indent=2));return 0 if r['state']=='completed' else 1
if __name__=='__main__':raise SystemExit(main())
