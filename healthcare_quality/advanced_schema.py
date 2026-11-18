"""V6.3 bounded benefit DSL. Model output is data, never executable code."""
from copy import deepcopy
import json
from pathlib import Path
from jsonschema import Draft202012Validator
from healthcare_quality.ai_schema import digest
from healthcare_quality.benefits import FACTS
from healthcare_quality.workflow import ACTORS

DSL = 'benefit-cases-1'
RULES = {r['id']: r for r in FACTS['rules']}
PLAN_FACTS=json.loads((Path(__file__).with_name('data')/'plans.json').read_text())
SERVICES=sorted({s for p in PLAN_FACTS for s in p['services']})
SUCCESS_FIELDS = ('status', 'state', 'revision', 'event_count', 'payout_cents',
                  'member_cents', 'other_payer_cents', 'noncovered_cents',
                  'ledger_cents', 'ledger_count', 'individual_deductible',
                  'individual_oop', 'individual_benefit', 'family_deductible',
                  'family_oop', 'family_benefit', 'policy_id', 'partial')
ACTIONS = ('submit', 'pay', 'adjust', 'reverse', 'appeal', 'resolve', 'read')

def obj(properties, required=None):
    return dict(type='object', additionalProperties=False,
                properties=properties, required=list(properties if required is None else required))

TEXT = dict(type='string', minLength=3, maxLength=150)
IDENTIFIER = dict(type='string', pattern=r'^[A-Za-z0-9][A-Za-z0-9_-]{2,47}$')
KEY = dict(type='string', pattern=r'^[A-Za-z0-9_-]{8,80}$')
MONEY = dict(type='integer', minimum=0, maximum=100000000)
LINE = obj(dict(id=IDENTIFIER, service=dict(type='string', enum=SERVICES),
                allowed_cents=dict(type='integer',minimum=1,maximum=100000000),
                other_payer_cents=MONEY, in_network=dict(type='boolean'),
                authorized=dict(type='boolean'), formulary=dict(type='boolean')),
           ['id','service','allowed_cents'])
LINES = dict(type='array', minItems=1, maxItems=5, items=LINE)
COMMON = dict(claim_id=IDENTIFIER, operation_key=KEY)
DATA = {
    'submit': obj({**COMMON, 'member_id':dict(type='string',enum=['M100','M200','M300','M400']),
                   'plan_id':dict(type='string',enum=[p['id'] for p in PLAN_FACTS]),
                   'service_date':dict(type='string',pattern=r'^202[67]-[01][0-9]-[0-3][0-9]$'),'lines':LINES}),
    'read': obj(dict(claim_id=IDENTIFIER)),
}
for action in ACTIONS:
    if action in DATA: continue
    fields = {**COMMON,'expected_revision':dict(type='integer',minimum=1,maximum=32)}
    if action in ('adjust','resolve'):fields['lines']=LINES
    if action in ('adjust','reverse','appeal','resolve'):fields['note']=dict(type='string',minLength=3,maxLength=500)
    DATA[action]=obj(fields)
success = {k:dict(type='integer',minimum=0,maximum=500000000) for k in SUCCESS_FIELDS}
success.update(status=dict(type='integer',enum=[200,201]),state=dict(type='string',enum=['adjudicated','paid','appealed','reversed']),policy_id=dict(type='string',enum=[p['id'] for p in FACTS['policies']]),partial=dict(type='boolean'))
EXPECT = {'oneOf':[obj(success), obj(dict(status=dict(type='integer',enum=[400,403,404,409]), error=dict(type='string',enum=['INVALID_BENEFITS_REQUEST','FORBIDDEN','NOT_FOUND','DUPLICATE_CLAIM','IDEMPOTENCY_CONFLICT','REVISION_CONFLICT','INVALID_TRANSITION'])))]}
STEP = {'oneOf':[obj(dict(action=dict(const=a),actor=dict(type='string',enum=[x['id'] for x in ACTORS]),data=DATA[a],expect=EXPECT)) for a in ACTIONS]}
CASE = obj(dict(id=dict(type='string',pattern=r'^AB-[A-Za-z0-9_-]{1,40}$'),title=TEXT,
                rule_ids=dict(type='array',minItems=1,maxItems=7,uniqueItems=True,items=dict(enum=list(RULES))),
                rationale=dict(type='string',minLength=5,maxLength=1000),
                assumptions=dict(type='array',maxItems=0),
                steps=dict(type='array',minItems=1,maxItems=16,items=STEP)))
SCHEMA = obj(dict(cases=dict(type='array',minItems=1,maxItems=3,items=CASE)))
SCHEMA['$defs'] = {'expect':deepcopy(EXPECT), 'lines':deepcopy(LINES)}
for variant in SCHEMA['properties']['cases']['items']['properties']['steps']['items']['oneOf']:
    variant['properties']['expect'] = {'$ref':'#/$defs/expect'}
    fields=variant['properties']['data']['properties']
    if 'lines' in fields:fields['lines']={'$ref':'#/$defs/lines'}
Draft202012Validator.check_schema(SCHEMA)

def parse_model_json(text):
    def unique(pairs):
        value={}
        for key,item in pairs:
            if key in value:raise ValueError('Duplicate JSON key: '+key)
            value[key]=item
        return value
    def invalid(value):raise ValueError('Non-finite JSON number')
    return json.loads(text,object_pairs_hook=unique,parse_constant=invalid)

def validate(cases):
    def integers_only(value):
        if isinstance(value,float):raise ValueError('Use built-in integer amounts and observations, not floating point')
        if isinstance(value,dict):
            for item in value.values():integers_only(item)
        elif isinstance(value,list):
            for item in value:integers_only(item)
    integers_only(cases)
    Draft202012Validator(SCHEMA).validate({'cases':cases})
    ids=[c['id'] for c in cases]
    if len(set(ids)) != len(ids): raise ValueError('Duplicate case IDs')
    for case in cases:
        if any(s['data'].get('other_payer_cents',0) for s in case['steps']):
            raise ValueError('Other-payer amounts belong to claim lines')
        for index,step in enumerate(case['steps']):
            if step['action'] != 'read' and step['expect']['status'] >= 400:
                following = case['steps'][index+1:index+2]
                # Known-claim rejection must be followed by an authorized readback.
                exists=any(p['action']=='submit' and p['expect']['status']==201 and p['data']['claim_id']==step['data']['claim_id'] for p in case['steps'][:index])
                if exists and (not following or following[0]['action']!='read' or following[0]['data']['claim_id']!=step['data']['claim_id'] or following[0]['expect']['status']!=200):
                    raise ValueError('Rejected writes require an authorized unchanged-state readback')
    return cases

def semantic_key(case):
    """Ignore generated identifiers/operation keys and expected values, not business inputs."""
    names={}; keys={}; steps=[]
    for step in case['steps']:
        data=deepcopy(step['data']);name=data['claim_id'];names.setdefault(name,'claim-'+str(len(names)));data['claim_id']=names[name]
        if 'operation_key' in data:
            key=data['operation_key'];keys.setdefault(key,'operation-'+str(len(keys)));data['operation_key']=keys[key]
        steps.append(dict(action=step['action'],actor=step['actor'],data=data))
    return digest(steps)

def duplicate_groups(cases):
    groups={}
    for c in cases:groups.setdefault(semantic_key(c),[]).append(c['id'])
    return [v for v in groups.values() if len(v)>1]
