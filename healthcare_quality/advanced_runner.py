"""Execute bounded advanced cases in fresh stores, through service or real HTTP."""
from pathlib import Path
from tempfile import TemporaryDirectory
from copy import deepcopy
import json,time,threading,urllib.request,urllib.error
from werkzeug.serving import make_server
from healthcare_quality.advanced_schema import validate
from healthcare_quality.benefit_claims import BenefitClaims
from healthcare_quality.workflow import WorkflowError

FAULTS=('payout_cents','ledger_cents','ledger_count','event_count','revision',
        'individual_deductible','individual_oop','individual_benefit',
        'family_deductible','family_oop','family_benefit','member_cents')

def project(r,status=200):
    return dict(status=status,state=r['state'],revision=r['revision'],event_count=len(r['events']),
                **{k:r['calculation']['totals'][k] for k in ('payout_cents','member_cents','other_payer_cents','noncovered_cents')},
                ledger_cents=sum(x['amount'] for x in r['ledger']),ledger_count=len(r['ledger']),
                **{'individual_'+k:v for k,v in r['current_member_accumulators'].items()},
                **{'family_'+k:v for k,v in r['current_family_accumulators'].items()},
                policy_id=r['calculation']['policy_id'],partial=r['calculation']['partial'])

def run(cases,transport='service',fault=None):
    validate(cases)
    if transport not in ('service','http') or fault not in (*FAULTS,None) or (fault and transport!='service'):raise ValueError('Unknown trusted transport/fault')
    results=[];started=time.monotonic();actions=0
    with TemporaryDirectory(prefix='hql-benefit-cases-') as tmp:
        for index,case in enumerate(cases):
            root=Path(tmp)/str(index);root.mkdir();service=BenefitClaims(root/'claims.sqlite');server=None;thread=None;steps=[]
            if transport=='http':
                from healthcare_quality.app import create_app
                app=create_app({'TESTING':True,'DATABASE':str(root/'workflow.sqlite')})
                server=make_server('127.0.0.1',0,app,threaded=True);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
            try:
                for n,s in enumerate(case['steps'],1):
                    if time.monotonic()-started>60:raise TimeoutError('Advanced execution time budget exceeded')
                    d=deepcopy(s['data']);id=d.pop('claim_id');a=s['action'];status=201 if a=='submit' else 200;request_id=None
                    if a=='submit':d['id']=id
                    if transport=='service':
                        try:raw=service.get(s['actor'],id) if a=='read' else service.operate(s['actor'],d,a,None if a=='submit' else id);observed=project(raw,status)
                        except WorkflowError as error:raw=dict(error=error.code,message=str(error));observed=dict(status=error.status,error=error.code)
                    else:
                        path='/api/benefits/claims'+('' if a=='submit' else '/'+id+('' if a=='read' else '/'+a))
                        req=urllib.request.Request('http://127.0.0.1:'+str(server.server_port)+path,data=None if a=='read' else json.dumps(d).encode(),headers={'Content-Type':'application/json','X-Demo-Actor':s['actor']})
                        try:response=urllib.request.urlopen(req,timeout=5)
                        except urllib.error.HTTPError as e:response=e
                        with response:
                            data=response.read(262145)
                            if len(data)>262144:raise ValueError('Response budget exceeded')
                            raw=json.loads(data);status=response.status;request_id=response.headers.get('X-Request-ID')
                        observed=project(raw,status) if status in (200,201) else dict(status=status,error=raw['error'])
                    if fault and fault in observed:observed[fault]+=1
                    expected=s['expect'];assertions=[dict(field=k,expected=v,observed=observed.get(k),passed=k in observed and type(v) is type(observed[k]) and v==observed[k]) for k,v in expected.items()]
                    passed=all(x['passed'] for x in assertions);actions+=1
                    steps.append(dict(step=n,action=a,expected=expected,observed=observed,passed=passed,assertions=assertions,request=dict(action=a,actor=s['actor'],data=deepcopy(s['data'])),response=deepcopy(raw),request_id=request_id))
                    if not passed:break
                results.append(dict(case_id=case['id'],passed=len(steps)==len(case['steps']) and all(s['passed'] for s in steps),steps=steps))
            finally:
                if server:server.shutdown();thread.join(5);server.server_close()
    return dict(results=results,passed=sum(x['passed'] for x in results),failed=sum(not x['passed'] for x in results),
                actions=actions,transport=transport,observation_fault=fault,duration_ms=round((time.monotonic()-started)*1000,2),
                isolation='Fresh synthetic state per case. Fixed actions only; no generated code or interactive-store writes.')
