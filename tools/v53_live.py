"""Opt-in local Ollama generation/correction measurement; no automatic approval."""
import sys,json
from pathlib import Path
from healthcare_quality.ai_studio import StudioService,ExperimentStore,now,build_prompt
from healthcare_quality import reference
from healthcare_quality.ai_schema import digest
from healthcare_quality.ollama_provider import SETTINGS
root=Path(__file__).resolve().parents[1];out=root/'artifacts/v5.3';out.mkdir(exist_ok=True);dest=out/'live-comparison.json'
if dest.exists():raise RuntimeError('Preserve existing evidence')
studio=StudioService(ExperimentStore(root/'.local/v53-live/ai.sqlite'))
status=studio.provider.status()
if not status['available']:raise RuntimeError('Ollama unavailable; no fixture fallback')
tasks=[]
for i,(amount,payout) in enumerate([(8300,0),(10000,0),(10001,1),(143750,133750),(209999,199999),(210000,200000),(286450,200000)],1):
 data={'plan_id':'commercial_ppo','service':'medical','amount_cents':amount}
 tasks.append({'id':f'F{i:02}','data':data,'literal_expected':{'status':200,'decision':'approved','reason':'COVERED','payout_cents':payout},'requirement':f'Create exactly one evaluate-only case. actor none. Use these exact inputs: {json.dumps(data)}. Assert status, decision, reason and exact payout_cents. Do not include workflow steps.'})
# Final task exercises payment and history as well as payout.
tasks.append({'id':'F08','amount':117340,'literal_payout':107340,'requirement':'Create one case with exactly four steps: customer-m100 submits claim FRESH-853 for member M100, service medical, amount_cents 117340; adjuster-demo transitions it to approved; finance-demo transitions it to paid; customer-m100 reads it. Assert all six successful workflow observations on every step: status,claim_status,revision,payout_cents,event_count,payment_cents. No other steps.'})
for t in tasks:
 t['request']={'requirement':t['requirement'],'source_ids':['HC-007'] if t['id']!='F08' else ['HC-007','WF-001','WF-003','WF-004','WF-005'],'model':'qwen2.5-coder:3b','strategy':'assertions-v2','count':1}
 t['prompt_hash']=digest(build_prompt(t['requirement'],t['request']['source_ids'],'assertions-v2',1))
record={'created_at':now(),'state':'running','provider':status,'settings':SETTINGS,'reference_fingerprint':reference.fingerprint(),'tasks':tasks,'results':[],'scope':'Eight newly authored tasks frozen before local inference. Each raw generation receives at most one explicit correction; no approval or execution. Small demonstration, not a held-out accuracy benchmark. Literal answers authored before calls, separate from calculator.'}
def save():dest.write_text(json.dumps(record,indent=2)+'\n')
def metrics(t,r):
 ps=r['proposals'];m={'state':r['state'],'experiment_id':r['id'],'structure':bool(ps and ps[0]['valid']),'complete':bool(ps and ps[0].get('assertions_complete')),'reference_match':bool(ps and ps[0].get('reference',{}).get('status')=='matched'),'literal_pass':False}
 if not m['structure']:return m
 steps=ps[0]['case']['steps']
 if t['id']!='F08':
  m['literal_pass']=len(steps)==1 and steps[0]['action']=='evaluate' and steps[0]['actor']=='none' and all(steps[0]['data'].get(k)==v for k,v in t['data'].items()) and steps[0]['expect']==t['literal_expected']
 else:
  expected=[{'status':201 if i==0 else 200,'claim_status':['submitted','approved','paid','paid'][i],'revision':[1,2,3,3][i],'event_count':[1,2,3,3][i],'payout_cents':107340,'payment_cents':None if i<2 else 107340} for i in range(4)]
  m['literal_pass']=len(steps)==4 and [s['action'] for s in steps]==['submit','transition','transition','read'] and steps[0]['data'].get('amount_cents')==117340 and [s['expect'] for s in steps]==expected
 return m
save()
for t in tasks:
 raw=studio.generate(t['request']);(out/f"proposal-{raw['id']}.json").write_text(json.dumps(raw,indent=2)+'\n')
 row={'task_id':t['id'],'original':metrics(t,raw),'correction':None};record['results'].append(row);save()
 print(t['id'],'original',row['original'],flush=True)
 if raw['proposals'] and all(p['valid'] for p in raw['proposals']):
  child=studio.correct(raw['id'],{'expected_revision':raw['revision'],'reviewer_label':'Live demonstration operator','review_note':'One explicit correction against frozen inputs and independent synthetic reference; no approval.'})
  assert child['approval'] is None and not child['runs']
  (out/f"proposal-{child['id']}.json").write_text(json.dumps(child,indent=2)+'\n');row['correction']=metrics(t,child);save();print(t['id'],'correction',row['correction'],flush=True)
record['state']='completed';record['finished_at']=now();record['summary']={mode:{key:sum(bool(r[mode] and r[mode].get(key)) for r in record['results']) for key in ['structure','complete','reference_match','literal_pass']} for mode in ['original','correction']};save();print(json.dumps(record['summary']),flush=True)
