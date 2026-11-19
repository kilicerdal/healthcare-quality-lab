"""Explicit local model-only experiment. No answer synthesis or automatic review."""
import argparse,json,threading
from pathlib import Path
from healthcare_quality.expectation_lab import ExpectationLab,selection
from healthcare_quality.ollama_provider import ExpectationOllamaProvider
from healthcare_quality.ai_schema import MODELS

def main():
 p=argparse.ArgumentParser();p.add_argument('--models',nargs='+',choices=MODELS,required=True);p.add_argument('--tasks',nargs='+',required=True);p.add_argument('--strategy',choices=['whole_case','stepwise'],default='whole_case');p.add_argument('--repeats',type=int,default=1);p.add_argument('--self-review',action='store_true');p.add_argument('--state',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--native-reasoning',action='store_true');p.add_argument('--dry-run',action='store_true');a=p.parse_args();body=dict(models=a.models,tasks=a.tasks,strategy=a.strategy,repeats=a.repeats,self_review=a.self_review)
 try:s=selection(body)
 except ValueError as e:p.error(str(e))
 if a.dry_run:print(json.dumps(s,indent=2));return 0
 if a.output.exists():p.error('Choose a new evidence path; previous answers are never overwritten')
 lab=ExpectationLab(a.state,ExpectationOllamaProvider(a.native_reasoning),threading.BoundedSemaphore(1));r=lab.start(body);a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(dict(id=r['id'],state=r['state'],summary=r['summary']),indent=2));return 0 if r['state']=='completed' else 1
if __name__=='__main__':raise SystemExit(main())
