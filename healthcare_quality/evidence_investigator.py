"""Sealed advanced execution evidence. Explanations are hypotheses, not verdicts."""
from copy import deepcopy
from pathlib import Path
from datetime import datetime,timezone
import json
from jsonschema import Draft202012Validator
from healthcare_quality.ai_schema import digest
from healthcare_quality.advanced_lab import check,contract_hash
from healthcare_quality.advanced_runner import run
from healthcare_quality.fault_controls import seeded_payout
from tools.fingerprints import source_hash

CATEGORIES=('potential_application_fault','expected_value_error','stale_evidence','infrastructure_unknown','harness_injection','passed')
EXPLANATION_SCHEMA={'type':'object','additionalProperties':False,'required':['hypotheses','uncertainty'],'properties':{'hypotheses':{'type':'array','minItems':1,'maxItems':4,'items':{'type':'object','additionalProperties':False,'required':['category','statement','evidence_ids'],'properties':{'category':{'enum':list(CATEGORIES)},'statement':{'type':'string','minLength':10,'maxLength':1200},'evidence_ids':{'type':'array','minItems':1,'maxItems':12,'uniqueItems':True,'items':{'type':'string','pattern':'^F[0-9]+$'}}}}},'uncertainty':{'type':'string','minLength':10,'maxLength':1500}}}

def seal(cases,execution):
    record=dict(kind='advanced_failure_bundle',created_at=datetime.now(timezone.utc).isoformat(),source_hash=source_hash(),contract_hash=contract_hash(),cases=deepcopy(cases),execution=deepcopy(execution));return dict(**record,content_hash=digest(record))

def inspect(bundle):
    payload={k:v for k,v in bundle.items() if k!='content_hash'}
    if digest(payload)!=bundle.get('content_hash'):raise ValueError('Evidence integrity mismatch')
    cases={c['id']:c for c in bundle['cases']};results=bundle['execution'].get('results',[])
    if len(results)!=len(cases) or len({x['case_id'] for x in results})!=len(results) or any(x['case_id'] not in cases for x in results):raise ValueError('Execution/case cardinality mismatch')
    findings=[];facts=[];reference=check(bundle['cases']);stale=bundle['source_hash']!=source_hash() or bundle['contract_hash']!=contract_hash()
    for result in results:
        case=cases[result['case_id']]
        for step in result['steps']:
            n=step['step']
            if type(n) is not int or not 1<=n<=len(case['steps']):raise ValueError('Invalid frozen step reference')
            if step['action']!=case['steps'][n-1]['action']:raise ValueError('Action snapshot mismatch')
            for a in step['assertions']:
                if a['field'] not in case['steps'][n-1]['expect'] or a['expected']!=case['steps'][n-1]['expect'][a['field']]:raise ValueError('Assertion expectation snapshot mismatch')
                if not a['passed']:facts.append(dict(id='F'+str(len(facts)+1),case_id=case['id'],step=n,action=step['action'],field=a['field'],expected=a['expected'],observed=a['observed'],request=step.get('request'),response=step.get('response'),request_id=step.get('request_id')))
        if stale:category='stale_evidence'
        elif not reference['review_ready']:category='expected_value_error'
        elif result.get('execution_error'):category='infrastructure_unknown'
        elif bundle['execution'].get('observation_fault'):category='harness_injection'
        elif not result['passed']:category='potential_application_fault'
        else:category='passed'
        findings.append(dict(case_id=case['id'],category=category))
    if not facts:facts.append(dict(id='F1',field='execution_summary',observed=dict(passed=bundle['execution']['passed'],failed=bundle['execution']['failed'])))
    return dict(bundle_hash=bundle['content_hash'],findings=findings,facts=facts,reference_matches=reference['review_ready'],source_current=not stale,scope='Observed differences and independent gate support triage, not proof of root cause. A deliberate control is not an unseeded product defect.')

def explain(provider,model,analysis):
    prompt='Explain these observed synthetic test failures. Return hypotheses with category, statement and evidence_ids plus uncertainty. Cite only supplied F identifiers. Distinguish expected-value errors, possible application defects, stale evidence, infrastructure and harness injection. Do not assert a proven root cause or invent file/line citations. Do not propose executable code. Evidence: '+json.dumps(analysis,sort_keys=True)
    raw=provider.generate(model,prompt,EXPLANATION_SCHEMA)
    from healthcare_quality.advanced_schema import parse_model_json
    try:
        answer=parse_model_json(raw['text']);Draft202012Validator(EXPLANATION_SCHEMA).validate(answer)
    except Exception as error:return dict(raw=raw,answer=None,rubric=dict(citations_exist=False,category_agreement=False),accepted=False,error=type(error).__name__,label='Invalid AI hypothesis retained; no automatic fix or execution')
    ids={f['id'] for f in analysis['facts']};unknown=sorted({i for h in answer['hypotheses'] for i in h['evidence_ids'] if i not in ids});expected={f['category'] for f in analysis['findings']}
    rubric=dict(citations_exist=not unknown,unknown_citations=unknown,category_agreement=all(h['category'] in expected for h in answer['hypotheses']),uncertainty_supplied=True,scope='Citation existence and category agreement are scored; this does not verify the truth of every natural-language statement.')
    return dict(raw=raw,answer=answer,rubric=rubric,accepted=bool(rubric['citations_exist'] and rubric['category_agreement']),label='AI hypothesis; no automatic fix, approval or execution')

def rehearsal(transport='http'):
    cases=json.loads((Path(__file__).with_name('data')/'advanced_cases_v63.json').read_text())['cases'][:1]
    healthy=run(cases,transport)
    with seeded_payout():fault=run(cases,transport)
    restored=run(cases,transport)
    assert healthy['failed']==0 and fault['failed']==1 and restored['failed']==0
    bundle=seal(cases,fault);analysis=inspect(bundle)
    return dict(kind='known_defect_investigation',source_hash=source_hash(),healthy=healthy,bundle=bundle,analysis=analysis,restored=restored,known_control='Trusted one-cent payout perturbation in production pricing dependency; original function restored',passed=True,live_model_calls=0)
