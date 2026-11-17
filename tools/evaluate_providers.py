"""Explicit paid evaluation; normal tests and the web app never import credentials."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import time
from healthcare_quality.api_budget import Budget, BudgetError, MODEL
from healthcare_quality.openai_provider import OpenAIProvider
from healthcare_quality.ollama_provider import OllamaProvider
from healthcare_quality.provider_evaluation import cohort, request_for, assess, summarize, PROTOCOL

def key_from(path):
    if path is None:return os.environ.get('OPENAI_API_KEY','')
    for line in path.read_text().splitlines():
        match=re.match(r'\s*(?:export\s+)?OPENAI_API_KEY\s*=\s*(.*?)\s*$',line)
        if match:return match.group(1).strip().strip(chr(34)+chr(39))
    return ''

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--provider',choices=['openai','ollama'],required=True)
    parser.add_argument('--allow-paid',action='store_true')
    parser.add_argument('--env-file',type=Path)
    parser.add_argument('--budget-ledger',type=Path,default=Path('.local/api-budget.sqlite'))
    parser.add_argument('--max-usd',default='15')
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--repeats',type=int,default=3,choices=range(1,6))
    parser.add_argument('--limit',type=int,default=16,choices=range(1,17))
    args=parser.parse_args()
    if args.output.exists():parser.error('Use a fresh output directory; prior evidence is never overwritten')
    if args.provider=='openai' and not args.allow_paid:parser.error('Paid inference requires --allow-paid')
    dataset=cohort(); cases=dataset['cases'][:args.limit]
    budget=Budget(args.budget_ledger,args.max_usd) if args.provider=='openai' else None
    provider=OpenAIProvider(key_from(args.env_file),budget) if budget else OllamaProvider()
    args.output.mkdir(parents=True)
    rows=[]
    frozen={'protocol':PROTOCOL,'cohort_sha256':hashlib.sha256(json.dumps(dataset,sort_keys=True).encode()).hexdigest(),
            'prompts':{s['id']:hashlib.sha256(request_for(s['data'])[1].encode()).hexdigest() for s in cases},
            'repeats':args.repeats,'provider':args.provider,'model':MODEL if budget else 'qwen3.5:27b',
            'scope':dataset['scope'],'started_at':datetime.now(timezone.utc).isoformat()}
    (args.output/'frozen-protocol.json').write_text(json.dumps(frozen,indent=2)+'\n')
    for trial in range(args.repeats):
        for item in cases:
            context,prompt,schema=request_for(item['data'])
            row={'provider':args.provider,'scenario':item['id'],'trial':trial+1,'input':item['data'],'prompt_sha256':frozen['prompts'][item['id']]}
            started=time.monotonic()
            try:
                response=provider.generate(prompt,schema) if budget else provider.generate('qwen3.5:27b',prompt,schema)
                row.update(response=response,assessment=assess(item['data'],response))
                if response.get('completed') is False:row['assessment']['accepted_for_review']=False
            except Exception as error:
                row.update(error_type=type(error).__name__,latency_ms=round((time.monotonic()-started)*1000,2))
            rows.append(row)
            (args.output/f"{args.provider}-{trial+1}-{item['id']}.json").write_text(json.dumps(row,indent=2)+'\n')
            summary={'protocol':frozen,'results':summarize(rows),'budget':budget.summary() if budget else None,'rows':rows}
            (args.output/'measurement.json').write_text(json.dumps(summary,indent=2)+'\n')
            print(json.dumps({'provider':args.provider,'scenario':item['id'],'trial':trial+1,'accepted':row.get('assessment',{}).get('accepted_for_review',False),'error_type':row.get('error_type')}),flush=True)
            if budget and budget.summary()['unresolved']:return 2
    return 0

if __name__=='__main__':raise SystemExit(main())
