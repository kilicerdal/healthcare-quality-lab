"""Run the V7 reviewer argument in disposable state, without any model inference."""
import argparse,json
from pathlib import Path
from tempfile import TemporaryDirectory
from healthcare_quality.app import create_app
from healthcare_quality.traceability import graph,impact
from tools.fingerprints import source_hash

def rehearse():
 with TemporaryDirectory(prefix='hql-v7-portfolio-') as tmp:
  app=create_app({'TESTING':True,'DATABASE':str(Path(tmp)/'claims.sqlite')});c=app.test_client();created=c.post('/api/advanced/portfolio/control',json={}).json;assert created['approval'] is None and not created['runs'];id=created['id'];assert c.post('/api/advanced/'+id+'/execute',json={'transport':'http'}).status_code==409
  result=c.post('/api/advanced/'+id+'/review',json={'reviewer':'Scripted V7 engineering rehearsal','note':'Authored control independently inspected at 71200-cent initial payout, 31200-cent adjustment and zero net reversal; scripted attestation, not human or AI generation.','revision':1});assert result.status_code==200
  execution=c.post('/api/advanced/'+id+'/execute',json={'transport':'http'}).json;assert execution['runs'][-1]['passed']==1 and execution['runs'][-1]['failed']==0
  trace=graph([execution]);assert next(x for x in trace['coverage'] if x['rule_id']=='BN-004')['current_passing_scenarios']==1;change=impact(trace,[{'id':'BN-004','contract':'A proposed cost sharing contract change for a what-if review'}]);assert len(change['affected_scenarios'])==1 and not change['applied']
  failure=c.post('/api/advanced/investigations/rehearse',json={});assert failure.status_code==201 and failure.json['passed'] and failure.json['restored']['failed']==0
  reports={v:c.get('/reports/v'+v).status_code for v in ('6.8','6.9','6.10','6.11','6.12','7.0')};assert all(x==200 for x in reports.values());assert c.get('/api/ready').status_code==200
  return dict(status='passed',source_hash=source_hash(),authored_control=dict(case_id=created['cases'][0]['id'],review_required=True,scripted_engineering_review=True,http_passed=execution['runs'][-1]['passed'],http_failed=execution['runs'][-1]['failed']),traceability=dict(current_passing_cost_sharing_scenarios=1,what_if_affected=1,contract_applied=False),known_defect=dict(healthy_failures=0,fault_failures=1,restored_failures=0,evidence_hash=failure.json['bundle']['content_hash']),reports=reports,live_model_calls=0,scope='Actual connected UI/API services in disposable synthetic state. Authored control with explicit scripted review; no AI generation, human-approval claim, real payment or interactive data write.')
def main():
 p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 if a.output.exists():p.error('Choose a fresh output file')
 r=rehearse();a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2))
if __name__=='__main__':main()
