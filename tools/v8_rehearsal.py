"""Disposable cross-system coverage and lifecycle rehearsal, not interactive state."""
import argparse,json,time,statistics
from pathlib import Path
from tempfile import TemporaryDirectory
from concurrent.futures import ThreadPoolExecutor
from healthcare_quality.coverage_packs import packs,journeys
from healthcare_quality.test_design import compile_plan
from healthcare_quality.system_adapters import execute
from healthcare_quality.app import create_app
from healthcare_quality.advanced_lab import AdvancedLab
from healthcare_quality.team_workflow import TeamWorkflow
from healthcare_quality.assistant_v8 import explain
from tools.fingerprints import source_hash

def rehearsal():
 start=time.monotonic();fingerprint=source_hash();rows=[]
 for group in packs()+[dict(id='lifecycle',plans=journeys())]:
  for plan in group['plans']:
   c=compile_plan(plan)
   for target in ('application','reference_peer'):
    result=execute([c],target);rows.append(dict(group=group['id'],scenario=c['id'],target=target,passed=result['passed']==1,actions=len(c['steps']),result=result))
 with TemporaryDirectory(prefix='hql-v8-load-') as tmp:
  app=create_app({'TESTING':True,'DATABASE':str(Path(tmp)/'claims.sqlite')})
  def probe(i):
   at=time.monotonic()
   with app.test_client() as client:r=client.get('/api/advanced/workbench')
   return dict(status=r.status_code,ms=round((time.monotonic()-at)*1000,2))
  with ThreadPoolExecutor(max_workers=4) as pool:probes=list(pool.map(probe,range(24)))
  c=app.test_client();p=c.post('/api/advanced/workbench/propose',json={'pack':'medicare_advantage','scenario':0}).json
  route=c.post('/api/advanced/workbench/team/'+p['id'],json=dict(owner='Engineering rehearsal',decision='ready_for_review',note='Inspected synthetic rule and all independent observations'))
  denied=c.post('/api/advanced/'+p['id']+'/execute',json={'transport':'http'}).status_code
  approved=c.post('/api/advanced/'+p['id']+'/review',json=dict(reviewer='Codex engineering rehearsal',note='Automated engineering inspection, not a human review; full reference and observations inspected',revision=p['revision']))
  result=c.post('/api/advanced/'+p['id']+'/execute',json={'transport':'http'})
  workflow=dict(routed=route.status_code==200,unapproved_execution_blocked=denied==409,explicit_review=approved.status_code==200,http_execution=result.status_code==200 and result.json['runs'][-1]['passed']==1,assistant_cannot_approve=not explain(p)['can_approve'])
 good=all(r['passed'] for r in rows) and all(p['status']==200 for p in probes) and all(workflow.values()) and fingerprint==source_hash()
 return dict(passed=good,source_hash=fingerprint,cross_system=rows,scenarios=len(rows)//2,adapter_executions=len(rows),workflow=workflow,load=dict(requests=len(probes),workers=4,failures=sum(p['status']!=200 for p in probes),median_ms=statistics.median(p['ms'] for p in probes),max_ms=max(p['ms'] for p in probes),scope='Bounded in-process concurrent read probes, not a production capacity claim'),duration_seconds=round(time.monotonic()-start,2),scope='Authored calculator-backed scenarios. The second HTTP target is the independent reference implementation; agreement is an integration control, not an independent test of that reference.')
def main():
 p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 if a.output.exists():p.error('Use a fresh evidence path')
 r=rehearsal();a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(r,indent=2)+'\n');print(json.dumps({k:v for k,v in r.items() if k!='cross_system'},indent=2));return 0 if r['passed'] else 1
if __name__=='__main__':raise SystemExit(main())
