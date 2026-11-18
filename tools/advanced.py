"""Explicit local advanced-case generation. Never approves or executes a draft."""
import argparse,json,threading
from pathlib import Path
from healthcare_quality.advanced_lab import AdvancedLab
from healthcare_quality.ollama_provider import OllamaProvider
from healthcare_quality.ai_schema import MODELS

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--requirement',required=True);p.add_argument('--model',choices=MODELS,default='qwen3.5:27b');p.add_argument('--state',type=Path,default=Path('.local/advanced-v63.sqlite'));p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    if a.output.exists():p.error('Output exists; use a new evidence file')
    provider=OllamaProvider('advanced');installed=provider.status()
    if a.model not in {m['name'] for m in installed['models']}:p.error('Requested model is not installed/running locally')
    lab=AdvancedLab(a.state,provider,threading.BoundedSemaphore(1));r=lab.generate(dict(requirement=a.requirement,model=a.model),background=False);r['installed_models']=installed['models'];a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(dict(id=r['id'],state=r['state'],review_ready=r['assessment']['review_ready'],output=str(a.output),approval=r['approval'])));return 0 if r['state']=='proposed' else 1
if __name__=='__main__':raise SystemExit(main())
