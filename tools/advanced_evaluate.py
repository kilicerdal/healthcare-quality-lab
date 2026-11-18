"""Explicit bounded local AI evaluation; never auto-approves or executes proposals."""
import argparse,json
from pathlib import Path
from healthcare_quality.ai_schema import MODELS
from healthcare_quality.ollama_provider import OllamaProvider
from healthcare_quality.advanced_evaluation import measure

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--model',choices=MODELS,default='qwen3.5:27b');p.add_argument('--tasks',nargs='+',default=['ADV-03','ADV-05']);p.add_argument('--repeats',type=int,choices=[1,2,3],default=1);p.add_argument('--correct',action='store_true');p.add_argument('--state',type=Path,default=Path('.local/advanced-evaluations-v64.sqlite'));p.add_argument('--output',type=Path,required=True);a=p.parse_args();provider=OllamaProvider('advanced');status=provider.status()
    if a.model not in {m['name'] for m in status['models']}:p.error('Requested allowlisted model is not installed/running')
    r=measure(provider,a.model,a.tasks,a.repeats,a.state,a.output,a.correct);print(json.dumps(dict(id=r['id'],state=r['state'],summary=r['summary'],output=str(a.output)),indent=2));return 0 if r['state']=='completed' else 1
if __name__=='__main__':raise SystemExit(main())
