"""Versioned rule -> scenario -> assertion -> execution links, with conservative impact."""
from copy import deepcopy
from healthcare_quality.ai_schema import digest
from healthcare_quality.advanced_schema import RULES,validate
from healthcare_quality.advanced_reference import FACTS,PLANS
from healthcare_quality.advanced_lab import contract_hash,check
from healthcare_quality.test_design import dependencies
from tools.fingerprints import source_hash

RULE_FIELDS={
 'BN-001':{'status','policy_id'},'BN-002':{'status','partial','noncovered_cents'},
 'BN-003':{'other_payer_cents','payout_cents'},
 'BN-004':{'payout_cents','member_cents','noncovered_cents'},
 'BN-005':{'individual_deductible','individual_oop','individual_benefit','family_deductible','family_oop','family_benefit'},
 'BN-006':{'state','revision','event_count','ledger_cents','ledger_count'},
 'BN-007':{'state','revision','event_count'}}

def requirements(overrides=None):
    overrides=overrides or {};rows=[]
    for id,rule in RULES.items():
        content={**deepcopy(rule),'contract':overrides.get(id,rule['contract'])};rows.append(dict(id=id,contract=content['contract'],version=digest(dict(rule=content,policies=FACTS['policies'],plans=PLANS)),facts_scope='Conservatively includes shared policy/plan facts; candidate impact is not exhaustive semantic proof'))
    return rows

def graph(proposals):
    if not isinstance(proposals,list) or len(proposals)>50:raise ValueError('Use at most 50 saved proposals')
    reqs=requirements();rows=[];edges=[];runs=[];invalid=[];assertions=[]
    for p in proposals:
        try:validate(p['cases'])
        except Exception:invalid.append(p.get('id','unknown'));continue
        gate=check(p['cases']);a=p.get('approval') or {};current=bool(a and a.get('cases_hash')==digest(p['cases']) and a.get('source_hash')==source_hash() and a.get('contract_hash')==contract_hash() and p.get('source_hash')==source_hash() and p.get('contract_hash')==contract_hash())
        for c in p['cases']:
            key=p['id']+'/'+c['id'];deps=dependencies(c);rows.append(dict(id=key,proposal_id=p['id'],case_id=c['id'],title=c['title'],case_hash=digest(c),derived_dependencies=deps,declared_citations=c['rule_ids'],independently_matched=gate['review_ready'],approval_current=current))
            for rule in deps:edges.append(dict(source=key,target=rule,kind='depends_on'))
            for n,s in enumerate(c['steps'],1):
                for field,value in s['expect'].items():
                    id=key+'/'+str(n)+'/'+field;assertions.append(dict(id=id,case_id=key,step=n,action=s['action'],field=field,expected=value));edges.append(dict(source=key,target=id,kind='asserts'))
                    for rule in deps:
                        if field in RULE_FIELDS[rule]:edges.append(dict(source=id,target=rule,kind='observes_rule'))
            for run in p.get('runs',[]):
                match=next((x for x in run.get('results',[]) if x['case_id']==c['id']),None)
                if not match:continue
                rid=p['id']+'/'+run['id'];runs.append(dict(id=rid,case_id=key,passed=match['passed'],snapshot_current=current,transport=run.get('transport')))
                for step in match.get('steps',[]):
                    for assertion in step['assertions']:
                        aid=key+'/'+str(step['step'])+'/'+assertion['field'];edges.append(dict(source=aid,target=rid,kind='observed_in',passed=assertion['passed'],current=current))
    coverage=[]
    for req in reqs:
        case_ids={c['id'] for c in rows if req['id'] in c['derived_dependencies']};covered={e['source'] for e in edges if e['kind']=='observes_rule' and e['target']==req['id']};executed={x['case_id'] for x in runs if x['case_id'] in case_ids and x['passed'] and x['snapshot_current']}
        coverage.append(dict(rule_id=req['id'],version=req['version'],scenario_count=len(case_ids),assertion_count=len(covered),current_passing_scenarios=len(executed)))
    return dict(kind='requirement_trace_graph',source_hash=source_hash(),contract_hash=contract_hash(),requirements=reqs,scenarios=rows,assertions=assertions,executions=runs,edges=edges,coverage=coverage,invalid_proposals=invalid,scope='Derived dependency and assertion links, not merely declared citations. Coverage counts are bounded observability evidence, not proof of complete business requirements. Unexecuted/stale approvals are never current passing coverage.')

def impact(snapshot,changes):
    if not isinstance(changes,list) or not 1<=len(changes)<=7 or any(not isinstance(c,dict) or set(c)!={'id','contract'} or type(c['id']) is not str or c['id'] not in RULES or type(c['contract']) is not str or not 5<=len(c['contract'])<=1000 for c in changes) or len({c['id'] for c in changes})!=len(changes):raise ValueError('Provide 1–7 unique known rule IDs and bounded proposed contract text')
    before={x['id']:x for x in snapshot['requirements']};after={x['id']:x for x in requirements({c['id']:c['contract'] for c in changes})};changed=[c['id'] for c in changes if before[c['id']]['version']!=after[c['id']]['version']];affected=[dict(case_id=c['id'],rule_ids=sorted(set(c['derived_dependencies'])&set(changed)),approval_current=c['approval_current'],action='Inspect and regenerate expectations against the changed contract; separate review required') for c in snapshot['scenarios'] if set(c['derived_dependencies'])&set(changed)]
    return dict(changed_rules=[dict(id=i,before=before[i]['version'],proposed=after[i]['version']) for i in changed],affected_scenarios=affected,snapshot_source_current=snapshot['source_hash']==source_hash(),applied=False,scope='What-if candidate impact only. Does not edit policy files, mutate saved proposals, revoke historical records or automatically reapprove tests. Actual contract changes invalidate execution approvals through the existing fingerprint gate.')
