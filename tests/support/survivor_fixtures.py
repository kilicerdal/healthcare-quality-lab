from copy import deepcopy
import json
from pathlib import Path
DATA=json.loads((Path(__file__).resolve().parents[1]/'data/v56_scenarios.json').read_text())['cases']
def case(group='evaluator',variant=False):return deepcopy(DATA[('variant-' if variant else 'core-')+group])
def baseline_cases():
    evaluator=case();evaluator['steps']=evaluator['steps'][-1:];evaluator['rule_ids']=['HC-007'];evaluator['id']='AI-BASE-CAP'
    workflow=case('workflow');workflow['id']='AI-BASE-ZERO';workflow['steps']=[workflow['steps'][i] for i in (0,6,7)];last=deepcopy(workflow['steps'][-1]);last['action']='read';last['actor']='customer-m100';last['data']={'claim_id':last['data']['claim_id']};workflow['steps'].append(last)
    workflow['steps'][0]['data']['amount_cents']=9999
    for s in workflow['steps']:
        s['expect']['payout_cents']=0
        if s['expect']['payment_cents'] is not None:s['expect']['payment_cents']=0
    return evaluator,workflow
