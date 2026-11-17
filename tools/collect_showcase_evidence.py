"""Collect observed authored checks and combine retained provider measurements. No inference."""
from datetime import datetime,timezone
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from healthcare_quality.showcase_lab import run,SCENARIOS
from healthcare_quality.provider_evaluation import summarize
from healthcare_quality.api_budget import Budget

def main():
    p=argparse.ArgumentParser();p.add_argument('--openai',type=Path,required=True);p.add_argument('--ollama',type=Path,required=True);p.add_argument('--budget-ledger',type=Path,required=True);p.add_argument('--output',type=Path,default=Path('artifacts/showcase'));args=p.parse_args()
    measurements=[json.loads(path.read_text()) for path in [args.openai,args.ollama]]
    a,b=[m['protocol'] for m in measurements]
    if any(a[k]!=b[k] for k in ['protocol','cohort_sha256','prompts','repeats']):raise ValueError('Provider protocol mismatch; cannot combine')
    rows=deepcopy([r for m in measurements for r in m['rows']])
    for row in rows:
        envelope=row.get('response',{}).get('raw_envelope',{})
        if 'context' in envelope:
            envelope.pop('context');row['context_token_ids_omitted_from_public_summary']=True
    if any(len(m['rows'])!=len(m['protocol']['prompts'])*m['protocol']['repeats'] for m in measurements):raise ValueError('Trials are incomplete; retain partial evidence separately')
    args.output.mkdir(parents=True,exist_ok=True)
    budget=Budget(args.budget_ledger).summary()
    combined={'recorded_at':datetime.now(timezone.utc).isoformat(),'scope':'Sixteen newly authored inputs, three trials per provider; known scenario families, inspectable references, no blind holdout. Models generate expectations/calculations inside an authored wrapper. Eligibility is not human approval.',
              'protocols':[m['protocol'] for m in measurements], 'results':summarize(rows),'budget':budget,
              'settings':{'openai':'gpt-6.1-terra; low reasoning; strict JSON schema; store=false; no tools or automatic retries',
                          'ollama':'qwen3.5:27b; temperature=0; seed=7; num_predict=2600; num_ctx=12288; think=false; prompt JSON validated; schema appended by adapter'},
              'limits':['Different transport, decoding, model size and hardware; no causal ranking claim.',
                        'Latency includes local model loading when applicable; local hardware/electricity costs not measured.',
                        'Cost is token-usage-derived, not a billing invoice; the ledger also includes the separate one-request pilot.',
                        'Identical base prompt/schema hashes; provider-specific output format wrappers differ.',
                        'No generated output was automatically approved or executed.',
                        'Ollama context token-ID arrays are omitted from this public summary; original provider files are preserved in the release evidence archive.'], 'rows':rows}
    (args.output/'provider-comparison.json').write_text(json.dumps(combined,indent=2)+'\n')
    authored={'recorded_at':datetime.now(timezone.utc).isoformat(),'scenarios':[run(name) for name in SCENARIOS],
              'scope':'Authored deterministic demonstrations executed against disposable synthetic state. Zero inference or paid calls.'}
    (args.output/'deterministic-evidence.json').write_text(json.dumps(authored,indent=2)+'\n')
    print(json.dumps({'results':combined['results'],'budget':{k:v for k,v in budget.items() if k!='pricing'},'authored_passed':all(r['status']=='passed' for r in authored['scenarios'])},indent=2))

if __name__=='__main__':main()
