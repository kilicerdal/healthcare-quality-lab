"""Offline, bounded implementation-mutation comparison; no model inference."""
import argparse,json
from pathlib import Path
from healthcare_quality.effectiveness import compare,reduce_prefix
ROOT=Path(__file__).resolve().parents[1]
def main():
 p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--examples',type=int,default=80);a=p.parse_args()
 if a.output.exists():p.error('Choose fresh evidence output')
 suites={'authored_controls':json.loads((ROOT/'healthcare_quality/data/advanced_cases_v63.json').read_text())['cases'],'authored_gap_controls':json.loads((ROOT/'healthcare_quality/data/advanced_cases_v611.json').read_text())['cases']}
 for mode,label in [('ai_expectations','historical_ai_raw'),('calculator_expectations','historical_ai_scenario_calculator_values')]:
  f=ROOT/('artifacts/v6.8/live-'+mode+'.json')
  if f.exists():
   r=json.loads(f.read_text())
   if r.get('cases'):suites[label]=r['cases']
 result=compare(suites,examples=a.examples)
 row=next((x for x in result['suites'] if x['scored'] and x['detected']),None)
 if row:
  trial=next(t for t in row['trials'] if t['detected']);case=next(c for c in suites[row['name']] if c['id']==trial['witness']['case_id']);result['reduction']=reduce_prefix(case,trial['mutant'])
 a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps([{'suite':s['name'],'scored':s['scored'],'detected':s.get('detected'),'total':s.get('total')} for s in result['suites']]))
if __name__=='__main__':main()
