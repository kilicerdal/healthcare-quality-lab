"""Evidence-derived failure classification; AI hypotheses cannot change this verdict."""
from copy import deepcopy
from healthcare_quality import reference
from healthcare_quality.ai_schema import ALL_RULES,contract_fingerprint,digest
from healthcare_quality.assertion_quality import assess
from healthcare_quality.ai_studio import StudioError

def analyze(experiment,run_id):
    run=next((x for x in experiment.get('runs',[]) if x['id']==run_id),None)
    if run is None:raise StudioError('NOT_FOUND','Stored run not found',404)
    cases={c['id']:c for c in run.get('approved_cases',[])};findings=[];links=[]
    stale=run.get('contract_fingerprint')!=contract_fingerprint()
    for result in run.get('results',[]):
        case=cases.get(result['case_id']);rules=[x for x in result.get('rule_ids',[]) if x in ALL_RULES]
        if not case:
            findings.append(dict(category='insufficient_evidence',case_id=result['case_id'],reason='Frozen approved input snapshot is unavailable'));continue
        calculation=reference.check(case);quality=assess(case)
        if stale:category='stale_evidence';reason='Contract changed since this execution'
        elif result.get('execution_error'):category='infrastructure_error';reason=result['execution_error']
        elif calculation['status']=='mismatch':category='test_oracle_error';reason='Declared expectations disagree with independent written-rule calculation'
        elif not quality['complete']:category='incomplete_assertions';reason='Required business observations are missing'
        elif not result['passed'] and calculation['status']=='matched':category='potential_application_fault';reason='Complete reference-matching expectations failed; investigate implementation and environment'
        elif not result['passed']:category='insufficient_evidence';reason='Independent reference does not support this case'
        else:category='passed';reason='No failed assertions observed'
        facts=[]
        for step in result.get('steps',[]):
            for assertion in step.get('assertions',[]):
                if not assertion['passed']:facts.append(dict(id=f'F{len(findings)+1}-{len(facts)+1}',step=step['number'],action=step['action'],assertion=deepcopy(assertion)))
        findings.append(dict(category=category,case_id=case['id'],reason=reason,facts=facts,reference=calculation,quality=quality,rule_ids=rules,next_checks=['Inspect frozen inputs and independent derivation','Reproduce through the HTTP adapter','Propose a separate reviewed correction or follow-up test; never edit the recorded run']))
        for rule in rules:links.append(dict(requirement_id=rule,rule=deepcopy(ALL_RULES[rule]),rule_version=digest(ALL_RULES[rule]),case_id=case['id'],case_hash=digest(case),run_id=run_id,experiment_id=experiment['id'],observed_pass=result['passed']))
    if run.get('status')=='interrupted':findings.insert(0,dict(category='infrastructure_error',reason='Interrupted execution has an unknown outcome'))
    return dict(experiment_id=experiment['id'],run_id=run_id,findings=findings,traceability=links,contract_current=not stale,scope='Deterministic triage, not automatic defect confirmation. AI explanations remain hypotheses; no correction, approval or execution occurs here.')

def change_impact(rule_ids,items):
    if not isinstance(rule_ids,list) or not rule_ids or len(rule_ids)>6 or any(type(i) is not str or i not in ALL_RULES for i in rule_ids) or len(set(rule_ids))!=len(rule_ids):raise StudioError('INVALID_REQUEST','Select 1–6 unique written rule IDs')
    affected=[dict(key=c['key'],eligible=c['eligible'],rules=[i for i in c['case']['rule_ids'] if i in rule_ids],quality=c.get('quality'),origin=c.get('origin')) for c in items if c.get('valid') and set(c['case']['rule_ids'])&set(rule_ids)]
    return dict(rules=[dict(id=i,version=digest(ALL_RULES[i])) for i in rule_ids],affected=affected,scope='Citation-based impact candidates, not proof that every semantic dependency was discovered.',suggested_requirement='Propose a new boundary and negative test for changed synthetic rules '+', '.join(rule_ids)+'. Include exact business observations, preserve review gates and do not claim execution.')
