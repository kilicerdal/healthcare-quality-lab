"""Same declarative observations through actual isolated loopback HTTP."""
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Thread
import json,time,urllib.request,urllib.error
from urllib.parse import quote
from werkzeug.serving import make_server
from healthcare_quality.ai_schema import MAX_CASES,MAX_STEPS
from healthcare_quality.ai_runner import project_evidence

def run_http_cases(cases):
    from healthcare_quality.app import create_app
    if not isinstance(cases,list) or not 1<=len(cases)<=MAX_CASES:raise ValueError('Case budget exceeded')
    results=[];actions=0;at=time.monotonic()
    with TemporaryDirectory(prefix='hql-http-') as temp:
        for i,case in enumerate(cases):
            if not 1<=len(case['steps'])<=MAX_STEPS:raise ValueError('Step budget exceeded')
            app=create_app({'TESTING':True,'DATABASE':str(Path(temp)/str(i)/'claims.sqlite')});server=make_server('127.0.0.1',0,app,threaded=True);thread=Thread(target=server.serve_forever,daemon=True);thread.start();steps=[];error=None
            try:
                for number,step in enumerate(case['steps'],1):
                    if time.monotonic()-at>30:raise TimeoutError('HTTP execution time budget exceeded')
                    action=step['action'];data=step['data'];id=quote(str(data.get('claim_id','')),safe='');path={'evaluate':'/api/evaluate','submit':'/api/claims','transition':'/api/claims/'+id+'/transitions','read':'/api/claims/'+id}[action];payload=None if action=='read' else ({'target':data['target']} if action=='transition' else data)
                    req=urllib.request.Request('http://127.0.0.1:'+str(server.server_port)+path,data=json.dumps(payload).encode() if payload is not None else None,headers={'Content-Type':'application/json','X-Demo-Actor':step['actor']})
                    try:response=urllib.request.urlopen(req,timeout=5)
                    except urllib.error.HTTPError as e:response=e
                    with response:status=response.status;raw=json.loads(response.read(262145))
                    if action=='evaluate':observed={'status':status,**({k:raw[k] for k in ('decision','reason','payout_cents')} if status==200 else {'error':'INVALID_REQUEST'})}
                    elif status in (200,201):observed=project_evidence(raw,status)
                    else:
                        observed=dict(status=status,error=raw.get('error'))
                        if raw.get('details',{}).get('evaluation'):observed['reason']=raw['details']['evaluation']['reason']
                    assertions=[dict(field=k,expected=v,observed=observed.get(k),passed=k in observed and type(observed[k]) is type(v) and observed[k]==v) for k,v in step['expect'].items()];passed=all(x['passed'] for x in assertions);actions+=1;steps.append(dict(number=number,action=action,actor=step['actor'],data=data,expected=step['expect'],observed=observed,assertions=assertions,evidence=raw,passed=passed))
                    if not passed:break
            except Exception as e:error=f'{type(e).__name__}: {e}'[:500]
            finally:server.shutdown();thread.join(5);server.server_close()
            results.append(dict(case_id=case['id'],title=case['title'],rule_ids=case['rule_ids'],steps=steps,execution_error=error,passed=error is None and len(steps)==len(case['steps']) and all(s['passed'] for s in steps)))
    return dict(results=results,passed=sum(x['passed'] for x in results),failed=sum(not x['passed'] for x in results),actions_executed=actions,action_budget=MAX_CASES*MAX_STEPS,duration_ms=round((time.monotonic()-at)*1000,2),transport='http',isolation='Fresh application/databases and ephemeral loopback HTTP listener per case; no interactive state.',scope='Actual HTTP boundary; generic validation errors are normalized while raw responses are retained. Known fault scoring remains on the service adapter.')
