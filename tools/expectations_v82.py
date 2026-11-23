"""Explicit local model-only experiment. No answer synthesis or automatic review."""
import argparse,json,threading
from pathlib import Path
from healthcare_quality.expectation_lab import ExpectationLab,selection
from healthcare_quality.ollama_provider import CompactExpectationProvider
from healthcare_quality import compact_expectations
from healthcare_quality.compact_evaluator import evaluate
from healthcare_quality.ai_schema import MODELS
from healthcare_quality.experiment_budget import request as budget_request,estimate

def main():
 p=argparse.ArgumentParser();p.add_argument('--models',nargs='+',choices=MODELS,required=True);p.add_argument('--tasks',nargs='+',required=True);p.add_argument('--strategy',choices=['whole_case','stepwise'],default='whole_case');p.add_argument('--repeats',type=int,default=1);p.add_argument('--self-review',action='store_true');p.add_argument('--state',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--dry-run',action='store_true');p.add_argument('--max-seconds',type=int,default=180);a=p.parse_args();body=dict(models=a.models,tasks=a.tasks,strategy=a.strategy,repeats=a.repeats,self_review=a.self_review)
 try:
  body,seconds=budget_request(dict(**body,max_seconds=a.max_seconds));s=selection(body,compact_expectations.cohort())
 except ValueError as e:p.error(str(e))
 if a.dry_run:print(json.dumps({**s,**estimate(dict(**body,max_seconds=seconds),[],compact_expectations.cohort())},indent=2));return 0
 if a.output.exists():p.error('Choose a new evidence path; previous answers are never overwritten')
 lab=ExpectationLab(a.state,CompactExpectationProvider(),threading.BoundedSemaphore(1),protocol=compact_expectations,evaluator=evaluate);r=lab.start(body,max_seconds=a.max_seconds);a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(dict(id=r['id'],state=r['state'],summary=r['summary']),indent=2));return 0 if r['state']=='completed' else 1
if __name__=='__main__':raise SystemExit(main())
