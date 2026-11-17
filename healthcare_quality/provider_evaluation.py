"""Frozen expectation-generation protocol shared by both providers; no model oracle."""
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from healthcare_quality import focused, reference
from healthcare_quality.ai_schema import digest, json_loads
from healthcare_quality.ai_studio import checked_cases

PROTOCOL = 'provider-expectations-v1'
ROOT = Path(__file__).resolve().parents[1]

def cohort():
    return json.loads((ROOT/'tests/data/showcase_evaluation.json').read_text())

def request_for(data):
    context = focused.context_for(data)
    nullable = lambda values: {'enum': [*values, None]}
    expect = {'type':'object','additionalProperties':False,
        'properties': {'status':{'type':'integer','enum':[200,400]},
                       'decision':nullable(['approved','denied']),
                       'reason':nullable(['COVERED','INACTIVE_POLICY','SERVICE_NOT_COVERED','OUT_OF_NETWORK','AUTH_REQUIRED','NON_FORMULARY']),
                       'error':nullable(['INVALID_REQUEST']),
                       'payout_cents':{'type':['integer','null'],'minimum':0,'maximum':100000000}},
        'required':['status','decision','reason','error','payout_cents']}
    schema = {'type':'object','additionalProperties':False,'required':['assessment','expect'],
              'properties': {'assessment':focused.assessment_schema(context), 'expect':expect}}
    prompt = ('Propose expected results for ONE synthetic software evaluator test. Return JSON matching the schema. '
              'These are invented teaching rules, not medical advice or real insurance decisions. '
              'Use only the provided plan, input and rules. Integer cents only. '
              'Invalid amount (outside 1..100000000) gives HTTP 400 and INVALID_REQUEST; '
              'expect decision/reason/payout are null for invalid. Approved or denied gives HTTP 200; error null. '
              'Apply first denial in order: inactive, unsupported service, required network missing, required authorization missing, non-formulary prescription. '
              'Denial payout is zero; assessment after_deductible is null, deductible/cap are plan facts. '
              'Approval payout is min(max(amount-deductible,0),cap). Assessment rule is HC-007 for approval, HC-001 for invalid; otherwise blocking rule. '
              'For invalid assessment all money fields are null. Do not invent percentages. '
              'The assessment is a compact calculation record. Expectations remain untrusted; no review or execution is authorized.\n'
              +json.dumps({k:context[k] for k in ['data','plan','source_ids','rules','defaults']},sort_keys=True)
              +'\nJSON schema: '+json.dumps(schema,sort_keys=True))
    return context, prompt, schema

def assess(data, response):
    from jsonschema import Draft202012Validator
    context, _prompt, schema = request_for(data)
    try:
        raw = json_loads(response['text'])
        Draft202012Validator(schema).validate(raw)
        expectation = {k:v for k,v in raw['expect'].items() if v is not None}
        case = {'id':'AI-COMPARISON','title':'Frozen evaluator expectation comparison',
                'rule_ids':context['source_ids'],'rationale':'Model-proposed expectations for an authored frozen input.',
                'assumptions':['Synthetic teaching rules; authored wrapper, model expectations; not human-approved.'],
                'steps':[{'action':'evaluate','actor':'none','data':deepcopy(data),'expect':expectation}]}
        checked = checked_cases([case],context['source_ids'])[0]
        calculation = focused.check(context,raw['assessment'],[case])
        literal, _ = reference.evaluate(data)
        return {'schema_valid':True,'reference_matched':checked['reference']['status']=='matched',
                'assertions_complete':checked['assertions_complete'],
                'calculation_matched':calculation['status']=='matched',
                'literal_match':expectation==literal,
                'accepted_for_review':bool(checked['review_ready'] and calculation['status']=='matched' and expectation==literal),
                'approval':'unapproved', 'case':case, 'reference':checked['reference'],
                'calculation':calculation, 'independent_expected':literal}
    except (ValueError,TypeError,KeyError) as error:
        return {'schema_valid':False,'accepted_for_review':False,'approval':'unapproved',
                'error_type':type(error).__name__}
    except Exception as error:
        # JSON Schema validation errors contain model output; preserve raw output separately.
        return {'schema_valid':False,'accepted_for_review':False,'approval':'unapproved',
                'error_type':type(error).__name__}

def summarize(rows):
    groups={}
    for provider in sorted({r['provider'] for r in rows}):
        items=[r for r in rows if r['provider']==provider]
        scenarios=sorted({r['scenario'] for r in items})
        accepted=sum(r.get('assessment',{}).get('accepted_for_review',False) for r in items)
        stability=[]
        for scenario in scenarios:
            trials=[r for r in items if r['scenario']==scenario]
            values=[r.get('assessment',{}).get('case',{}).get('steps',[{}])[0].get('expect') for r in trials]
            stability.append({'scenario':scenario,'trials':len(trials),
                'identical_expectations':len(trials)>1 and all(v is not None for v in values) and len({digest(v) for v in values})==1,
                'all_accepted':all(r.get('assessment',{}).get('accepted_for_review',False) for r in trials)})
        times=sorted(r['response']['latency_ms'] for r in items if r.get('response'))
        from decimal import Decimal
        cost=sum((Decimal(r.get('response',{}).get('usage_estimate_usd','0')) for r in items),Decimal(0))
        groups[provider]={'attempts':len(items),'accepted_for_review':accepted,'rejected_or_error':len(items)-accepted,
                          'schema_valid':sum(r.get('assessment',{}).get('schema_valid',False) for r in items),
                          'literal_matches':sum(r.get('assessment',{}).get('literal_match',False) for r in items),
                          'reference_matches':sum(r.get('assessment',{}).get('reference_matched',False) for r in items),
                          'calculation_matches':sum(r.get('assessment',{}).get('calculation_matched',False) for r in items),
                          'provider_errors':sum(bool(r.get('error_type')) for r in items),
                          'assertions_complete':sum(r.get('assessment',{}).get('assertions_complete',False) for r in items),
                          'median_latency_ms':__import__('statistics').median(times) if times else None,
                          'usage_estimate_usd':str(cost) if provider=='openai' else None,
                          'cost_per_accepted_case_usd':str(cost/accepted) if provider=='openai' and accepted else None,
                          'local_cost_note':'Local electricity/hardware cost not measured' if provider=='ollama' else None,
                          'repeatability':stability}
    return groups
