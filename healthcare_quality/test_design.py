"""V6.8 plan-first generation. Calculated expectations are never called AI reasoning."""
from copy import deepcopy
from datetime import date
import json,threading
from pathlib import Path
from uuid import uuid4
from jsonschema import Draft202012Validator
from healthcare_quality.advanced_schema import CASE,SCHEMA,RULES,PLAN_FACTS,parse_model_json,validate,semantic_key
from healthcare_quality.advanced_reference import Oracle,FACTS
from healthcare_quality.advanced_lab import check,contract_hash
from healthcare_quality.ai_schema import digest,MODELS
from healthcare_quality.ai_studio import ExperimentStore,StudioError,now
from healthcare_quality import operations
from tools.fingerprints import source_hash

PLAN_CASE=deepcopy(CASE)
for variant in PLAN_CASE['properties']['steps']['items']['oneOf']:
    variant['properties'].pop('expect');variant['required'].remove('expect')
PLAN_SCHEMA={'type':'object','additionalProperties':False,'required':['objective','risk','case'],'properties':{'objective':{'type':'string','minLength':10,'maxLength':1000},'risk':{'enum':['financial','lifecycle','authorization','idempotency','effective_date','family_limits']},'case':PLAN_CASE}}
PLAN_SCHEMA['$defs']={'lines':deepcopy(SCHEMA['$defs']['lines'])}
PROMPTS=('baseline-v67','focused-v68')
MODES=('ai_expectations','calculator_expectations')

def compile_plan(plan):
    Draft202012Validator(PLAN_SCHEMA).validate(plan)
    c=deepcopy(plan['case']);oracle=Oracle()
    for s in c['steps']:s['expect']=oracle.step(s)
    validate([c]);return c

def plan_from_case(case,objective=None,risk='financial'):
    c=deepcopy(case)
    for step in c['steps']:step.pop('expect',None)
    p=dict(objective=objective or c['title'],risk=risk,case=c);compile_plan(p);return p

def dependencies(case):
    ids={'BN-001','BN-002','BN-003','BN-004','BN-005'}
    actions={s['action'] for s in case['steps']}
    if actions & {'pay','reverse','adjust'}:ids.add('BN-006')
    if actions & {'appeal','resolve'}:ids.add('BN-007')
    return sorted(ids)

def retrieve(plan):
    c=compile_plan(plan);plans={s['data']['plan_id'] for s in c['steps'] if s['action']=='submit'};dates={s['data']['service_date'] for s in c['steps'] if s['action']=='submit'}
    policies=[p for p in FACTS['policies'] if any(p['start']<=d<p['end'] for d in dates)]
    return dict(rules=[deepcopy(RULES[i]) for i in dependencies(c)],plans=[deepcopy(p) for p in PLAN_FACTS if p['id'] in plans],policies=deepcopy(policies),scope=FACTS['scope'],families={'M100':'F100','M200':'F100','M300':'F100','M400':'F400'},retrieval='Deterministic rule dependencies; no expected observations or application responses.')

def expectation_prompt(plan,version='focused-v68'):
    if version not in PROMPTS:raise ValueError('Unknown frozen prompt version')
    if version=='baseline-v67':
        from healthcare_quality.advanced_lab import prompt_for
        return prompt_for(plan['objective'])+'\nPreserve exactly these inputs/actions and fill every expect: '+json.dumps(plan['case'],sort_keys=True)
    return ('Return exactly one JSON object with cases containing the supplied case, preserving EVERY input, actor, action and step. Fill all required expect fields. No tools or code. '
      'First account for other-payer money, remaining deductible, policy copay, integer floor coinsurance, OOP and benefit caps. Noncovered money does not consume OOP. '
      'Track revision and event count separately: submit starts both at 1; each successful non-replayed mutation increments both. Pay appends one debit; adjustment appends credit+debit; reversal credits the payout without zeroing the original quote. Replays return the original response and add no events. '
      'Reserve accounts on adjudication. Credit only original allocations on adjustment/reversal. Read returns current accounts. Preserve rejected-action readbacks. '
      'This is a first-attempt answer: no reference feedback or expected values are provided.\nRETRIEVED FACTS: '+json.dumps(retrieve(plan),sort_keys=True)+'\nPLAN: '+json.dumps(plan,sort_keys=True))

def evaluate_answer(plan,response):
    try:
        cases=parse_model_json(response['text'])['cases'];a=check(cases);preserved=a['valid'] and len(cases)==1 and semantic_key(cases[0])==semantic_key(plan['case'])
        return dict(**a,scenario_preserved=preserved,eligible=bool(preserved and a['review_ready']),cases=cases)
    except (KeyError,TypeError,ValueError,RecursionError) as e:return dict(valid=False,matched=False,scenario_preserved=False,eligible=False,cases=[],error=type(e).__name__)

class DesignLab:
    def __init__(self,path,provider,lock):
        self.store=ExperimentStore(path);self.provider=provider;self.lock=lock;self.recover()
    def recover(self):
        import time
        with self.store.transaction() as db:
            for row in db.execute('SELECT record_json FROM ai_experiments'):
                r=json.loads(row[0])
                if r['state']=='generating':
                    lease=db.execute('SELECT expires_at FROM studio_operations WHERE experiment_id=?',(r['id'],)).fetchone()
                    if not lease or lease[0]<=time.time():r.update(state='interrupted',error='Expired generation lease; retained responses are not retried or approved');db.execute('DELETE FROM studio_operations WHERE experiment_id=?',(r['id'],));self.store.save(db,r)
    def get(self,id):self.recover();return self.store.get(id)
    def records(self):
        self.recover()
        with self.store.transaction() as db:return [json.loads(x[0]) for x in db.execute('SELECT record_json FROM ai_experiments ORDER BY created_at DESC LIMIT 50')]
    def generate(self,requirement,mode,model,background=False):
        if type(requirement) is not str or not 10<=len(requirement)<=2000 or mode not in MODES or model not in MODELS:raise StudioError('INVALID_REQUEST','Provide bounded requirement, known generation mode and allowlisted local model')
        r=dict(id=uuid4().hex,created_at=now(),kind='plan_first_design',state='generating',phase='planning',requirement=requirement,mode=mode,model=model,source_hash=source_hash(),contract_hash=contract_hash(),planning_raw=None,expectation_raw=None,plan=None,cases=[],assessment=None,approval=None,reference_assisted_correction=False,prompt_version='focused-v68')
        with self.store.transaction() as db:token=operations.start(db,r,'plan-first',30);db.execute('INSERT INTO ai_experiments VALUES(?,?,?)',(r['id'],r['created_at'],json.dumps(r)))
        if background:threading.Thread(target=self._work,args=(r,token),daemon=True).start()
        else:self._work(r,token)
        return self.store.get(r['id'])
    def _save(self,r,token,final=False):
        import time
        with self.store.transaction() as db:
            lease=db.execute('SELECT expires_at FROM studio_operations WHERE token=?',(token,)).fetchone()
            if not lease or lease[0]<=time.time():raise operations.LeaseLost('Late design completion fenced')
            if final:operations.finish(db,r,token)
            self.store.save(db,r)
    def _work(self,r,token):
        acquired=False
        try:
            with operations.keepalive(self.store.path,token,30,5):
                if not self.lock.acquire(False):raise StudioError('MODEL_BUSY','Another local request is active',429)
                acquired=True
                prompt='Design one bounded synthetic insurance test plan. Return objective, risk and case with action/actor/data only; NEVER include expect. Use valid members, plans and roles. Include meaningful ledger/history readbacks. No code or URLs. FACTS: '+json.dumps(dict(rules=list(RULES.values()),plans=PLAN_FACTS,policies=FACTS['policies'],scope=FACTS['scope']))+' REQUIREMENT: '+r['requirement']
                r['planning_raw']=self.provider.generate(r['model'],prompt,PLAN_SCHEMA);self._save(r,token)
                r['plan']=parse_model_json(r['planning_raw']['text']);compiled=compile_plan(r['plan']);r['retrieved']=retrieve(r['plan']);r['phase']='expectations';self._save(r,token)
                if r['mode']=='calculator_expectations':r['cases']=[compiled];r['expectation_author']='independent deterministic lifecycle calculator';r['assessment']=dict(**check(r['cases']),scenario_preserved=True,eligible=True)
                else:
                    r['expectation_raw']=self.provider.generate(r['model'],expectation_prompt(r['plan']),SCHEMA);self._save(r,token);r['assessment']=evaluate_answer(r['plan'],r['expectation_raw']);r['cases']=r['assessment']['cases'];r['expectation_author']='local AI first attempt, independently checked without correction'
                if r['source_hash']!=source_hash() or r['contract_hash']!=contract_hash():raise ValueError('Source or contract changed during generation')
                r.update(state='proposed',phase='completed')
        except Exception as e:r.update(state='failed',error=(type(e).__name__+': '+str(e))[:1500])
        finally:
            if acquired:self.lock.release()
            try:self._save(r,token,True)
            except operations.LeaseLost:pass
