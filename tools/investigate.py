"""Bounded known-defect rehearsal in an isolated process; optional explicit local AI."""
import argparse,json
from pathlib import Path
from healthcare_quality.evidence_investigator import rehearsal,explain
from healthcare_quality.ai_schema import MODELS
from healthcare_quality.ollama_provider import OllamaProvider

def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--model',choices=MODELS);a=p.parse_args()
    if a.output.exists():p.error('Evidence exists; choose a fresh file')
    r=rehearsal()
    if a.model:r['ai']=explain(OllamaProvider('advanced'),a.model,r['analysis']);r['live_model_calls']=1
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(dict(passed=r['passed'],output=str(a.output),ai_accepted=r.get('ai',{}).get('accepted'))))
if __name__=='__main__':main()
