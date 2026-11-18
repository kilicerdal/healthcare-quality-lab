"""Pure versioned synthetic line adjudication; never a real coverage determination."""
from copy import deepcopy
from datetime import date
import json
from pathlib import Path
from healthcare_quality.reference import PLANS
from healthcare_quality.workflow import WorkflowError
FACTS=json.loads((Path(__file__).with_name('data')/'benefits_v60.json').read_text())
ZERO={'deductible':0,'oop':0,'benefit':0}
def invalid(message):raise WorkflowError('INVALID_BENEFITS_REQUEST',message,400,'BN-001')
def money(value,name,minimum=0):
    if type(value) is not int or not minimum<=value<=100000000:invalid(name+' must be integer cents within bounds')
    return value
def policy_for(day,plan_id):
    if type(day) is not str:invalid('service_date must be ISO date')
    try:
        parsed=date.fromisoformat(day)
        if parsed.isoformat()!=day:invalid('service_date must be canonical ISO date')
    except ValueError:invalid('service_date must be ISO date')
    if type(plan_id) is not str or plan_id not in PLANS:invalid('Unknown teaching plan')
    p=next((x for x in FACTS['policies'] if x['start']<=day<x['end']),None)
    if p is None:invalid('No effective policy for service date')
    return {**deepcopy(p),'plan':deepcopy(PLANS[plan_id]),'year':parsed.year}
def validate_lines(lines):
    if not isinstance(lines,list) or not 1<=len(lines)<=10:invalid('Provide 1–10 claim lines')
    seen=set()
    for line in lines:
        if not isinstance(line,dict) or not {'id','service','allowed_cents'}<=set(line) or set(line)-{'id','service','allowed_cents','other_payer_cents','in_network','authorized','formulary'}:invalid('Invalid line fields')
        if type(line['id']) is not str or not 1<=len(line['id'])<=30 or line['id'] in seen:invalid('Line IDs must be unique nonempty strings')
        seen.add(line['id'])
        if type(line['service']) is not str or len(line['service'])>40:invalid('Invalid service')
        allowed=money(line['allowed_cents'],'allowed_cents',1);other=money(line.get('other_payer_cents',0),'other_payer_cents')
        if other>allowed:invalid('Other payer cannot exceed allowed amount')
        for flag in ('in_network','authorized','formulary'):
            if flag in line and type(line[flag]) is not bool:invalid(flag+' must be boolean')
    return lines
def calculate(policy,lines,individual=None,family=None):
    validate_lines(lines);ind=deepcopy(individual or ZERO);fam=deepcopy(family or ZERO);start=deepcopy(ind);rows=[];plan=policy['plan']
    for line in lines:
        allowed=line['allowed_cents'];other=line.get('other_payer_cents',0);eligible=allowed-other
        reason='COVERED'
        if line['service'] not in plan['services']:reason='SERVICE_NOT_COVERED'
        elif plan['network_required'] and not line.get('in_network',True):reason='OUT_OF_NETWORK'
        elif line['service'] in plan['authorization_services'] and not line.get('authorized',True):reason='AUTH_REQUIRED'
        elif line['service']=='prescription' and not line.get('formulary',True):reason='NON_FORMULARY'
        ded=copay=payout=member=0;noncovered=eligible
        if reason=='COVERED':
            ded=min(eligible,max(0,policy['individual_deductible']-ind['deductible']),max(0,policy['family_deductible']-fam['deductible']))
            copay=min(eligible-ded,policy['copay']);remaining=eligible-ded-copay
            preliminary=remaining*policy['payer_bps']//10000
            member=min(eligible-preliminary,max(0,policy['individual_oop']-ind['oop']),max(0,policy['family_oop']-fam['oop']))
            payout=min(eligible-member,max(0,policy['annual_benefit']-ind['benefit']))
            noncovered=eligible-member-payout;ded=min(ded,member)
            for account in (ind,fam):account['deductible']+=ded;account['oop']+=member;account['benefit']+=payout
        rows.append(dict(id=line['id'],reason=reason,allowed_cents=allowed,other_payer_cents=other,deductible_cents=ded,copay_cents=copay,member_cents=member,noncovered_cents=noncovered,payout_cents=payout))
    totals={k:sum(x[k] for x in rows) for k in ('allowed_cents','other_payer_cents','deductible_cents','copay_cents','member_cents','noncovered_cents','payout_cents')}
    return dict(rule_trace=[dict(rule_id='BN-002',line_id=x['id'],outcome=x['reason']) for x in rows]+[dict(rule_id='BN-004',outcome='Integer cost sharing and caps calculated'),dict(rule_id='BN-005',outcome='Annual allocation reserved')],policy_id=policy['id'],year=policy['year'],lines=rows,totals=totals,allocation={k:ind[k]-start[k] for k in ZERO},individual=ind,family=fam,partial=any(x['reason']!='COVERED' for x in rows) and any(x['reason']=='COVERED' for x in rows))
