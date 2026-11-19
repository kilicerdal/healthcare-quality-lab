"""Input-design quality is separate from expected-value correctness and approval."""
from copy import deepcopy
from jsonschema import Draft202012Validator,ValidationError
from healthcare_quality.test_design import PLAN_SCHEMA,compile_plan
from healthcare_quality.advanced_schema import semantic_key

def inspect(plan,seen=()):
 try:
  Draft202012Validator(PLAN_SCHEMA).validate(plan)
  compiled=compile_plan(plan)
 except (ValidationError,ValueError,KeyError,TypeError) as e:
  return dict(valid=False,ready=False,issues=[dict(code='INVALID_PLAN',detail=str(e)[:400])],features=[])
 issues=[];steps=plan['case']['steps'];features=set();key=semantic_key(plan['case'])
 if key in seen:issues.append(dict(code='DUPLICATE_SCENARIO',detail='Business inputs/actions duplicate a previously supplied scenario'))
 for i,(s,c) in enumerate(zip(steps,compiled['steps'])):
  action=s['action'];features.add(action)
  if action=='submit':
   for line in s['data']['lines']:
    features.add('service:'+line['service'])
    if line.get('other_payer_cents',0):features.add('coordination')
   if len(s['data']['lines'])>1:features.add('multi_line')
  if c['expect']['status']>=400:features.add('negative')
  if action in ('pay','adjust','reverse','resolve') and c['expect']['status']<400:
   following=steps[i+1:i+2]
   if not following or following[0]['action']!='read' or following[0]['data']['claim_id']!=s['data']['claim_id']:
    issues.append(dict(code='MISSING_READBACK',step=i+1,detail='Follow successful financial mutation with a read of the same claim'))
  if action=='submit' and c['expect']['status']==201:
   later=[x for x in steps[i+1:] if x['data']['claim_id']==s['data']['claim_id']]
   if not later:issues.append(dict(code='ISOLATED_SUBMISSION',step=i+1,detail='Add a later lifecycle action or state readback'))
 return dict(valid=True,ready=not issues,issues=issues,features=sorted(features),semantic_key=key,expectation_author='independent calculator',required_success_assertions=list(compiled['steps'][0]['expect']),approval=None)

def add_readbacks(plan):
 """Explicit authored transformation; never claims the model supplied added steps."""
 out=deepcopy(plan);steps=[]
 for i,s in enumerate(plan['case']['steps']):
  steps.append(deepcopy(s));following=plan['case']['steps'][i+1:i+2]
  if s['action'] in ('pay','adjust','reverse','resolve') and (not following or following[0]['action']!='read' or following[0]['data']['claim_id']!=s['data']['claim_id']):
   steps.append(dict(action='read',actor='finance-demo',data=dict(claim_id=s['data']['claim_id'])))
 out['case']['steps']=steps
 compile_plan(out)
 return dict(plan=out,transformation='authored_financial_readbacks',model_authored=False,approval=None)
