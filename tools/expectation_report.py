"""Read frozen experiment files; never call a provider or repair an answer."""
from collections import Counter
from pathlib import Path
import argparse,json
from healthcare_quality.expectation_lab import aggregate

def analyze(records):
 result=aggregate(records);pairs={};fields={}
 for record in records:
  for row in record['rows']:
   if row['split']!='reserved_until_exposed':continue
   model=row['model'];p=pairs.setdefault(model,Counter());first=row.get('first',{}).get('assessment',{}).get('eligible',False);review=row.get('self_review',{}).get('assessment',{}).get('eligible',False)
   if row.get('self_review_requested'):
    if row.get('first',{}).get('assessment') is None or row.get('self_review',{}).get('assessment') is None:p['review_unassessed']+=1
    else:p['both_correct' if first and review else 'self_review_recovered' if review else 'self_review_regressed' if first else 'neither_correct']+=1
   else:p['review_not_requested']+=1
   for stage in ('first','self_review'):
    a=row.get(stage,{}).get('assessment',{});m={d['field'] for c in a.get('assessment',{}).get('reference',[]) for s in c.get('steps',[]) for d in s.get('mismatches',[])};fields.setdefault(model+':'+stage,Counter()).update(m)
 result['paired_outcomes']={m:dict(v) for m,v in pairs.items()};result['trials_with_field_mismatch']={m:dict(sorted(v.items())) for m,v in fields.items()};return result

def main():
 p=argparse.ArgumentParser();p.add_argument('records',nargs='+',type=Path);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 if a.output.exists():p.error('Choose a fresh analysis output; original evidence is immutable')
 result=analyze([json.loads(p.read_text()) for p in a.records]);a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
if __name__=='__main__':main()
