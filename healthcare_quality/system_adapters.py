"""Versioned observation adapter contract and two disposable HTTP implementations.
The reference peer uses the independent oracle: it is a sample integration target,
not additional independent evidence of oracle correctness or a real payer.
"""
from copy import deepcopy
from contextlib import contextmanager
from threading import Thread,Lock
import json,time,urllib.request,urllib.error
from flask import Flask,request,jsonify
from werkzeug.serving import make_server
from healthcare_quality.advanced_schema import validate,CASE
from healthcare_quality.advanced_reference import Oracle
from healthcare_quality.advanced_runner import run
from healthcare_quality.test_design import PLAN_SCHEMA
from jsonschema import Draft202012Validator

@contextmanager
def reference_peer():
 app=Flask('hql-reference-peer');app.config['MAX_CONTENT_LENGTH']=16384;oracle=Oracle();lock=Lock()
 @app.post('/contract/v1/step')
 def step():
  data=request.get_json(silent=True)
  schema=deepcopy(PLAN_SCHEMA['properties']['case']['properties']['steps']['items']);schema['$defs']=deepcopy(PLAN_SCHEMA['$defs'])
  try:Draft202012Validator(schema).validate(data)
  except Exception:return jsonify(error='INVALID_ADAPTER_STEP'),400
  with lock:value=oracle.step(data)
  return jsonify(value)
 server=make_server('127.0.0.1',0,app,threaded=True);thread=Thread(target=server.serve_forever,daemon=True);thread.start()
 try:yield 'http://127.0.0.1:'+str(server.server_port)
 finally:server.shutdown();thread.join(5);server.server_close()

def execute(cases,target='application'):
 validate(cases)
 if target=='application':return dict(adapter='application-http-v1',**run(cases,'http'))
 if target!='reference_peer':raise ValueError('Choose a trusted installed adapter, never a model-supplied URL')
 results=[];started=time.monotonic()
 for case in cases:
  steps=[]
  with reference_peer() as url:
   for s in case['steps']:
    data={k:deepcopy(v) for k,v in s.items() if k!='expect'}
    req=urllib.request.Request(url+'/contract/v1/step',data=json.dumps(data).encode(),headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(req,timeout=5) as response:observed=json.loads(response.read(262144))
    assertions=[dict(field=k,expected=v,observed=observed.get(k),passed=k in observed and type(v) is type(observed[k]) and v==observed[k]) for k,v in s['expect'].items()]
    steps.append(dict(action=s['action'],passed=all(x['passed'] for x in assertions),assertions=assertions))
  results.append(dict(case_id=case['id'],passed=all(s['passed'] for s in steps),steps=steps))
 return dict(adapter='reference-peer-http-v1',passed=sum(r['passed'] for r in results),failed=sum(not r['passed'] for r in results),results=results,duration_ms=round((time.monotonic()-started)*1000,2),scope='Independent in-memory sample HTTP implementation backed by the same oracle used to author expectations; integration proof, not independent correctness proof.')
