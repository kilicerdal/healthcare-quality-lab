"""Independent Fraction-based advanced benefit oracle; reads facts, never imports SUT pricing."""
from fractions import Fraction
from pathlib import Path
from copy import deepcopy
import json
DATA=Path(__file__).with_name('data')
def price(day,plan_id,lines,individual=None,family=None):
    facts=json.loads((DATA/'benefits_v60.json').read_text());plan=next(p for p in json.loads((DATA/'plans.json').read_text()) if p['id']==plan_id);policy=next(p for p in facts['policies'] if p['start']<=day<p['end']);i=deepcopy(individual or dict(deductible=0,oop=0,benefit=0));f=deepcopy(family or dict(deductible=0,oop=0,benefit=0));payout=member=other_total=noncovered=0
    for line in lines:
        other=line.get('other_payer_cents',0);other_total+=other;net=line['allowed_cents']-other
        accepted=line['service'] in plan['services'] and (not plan['network_required'] or line.get('in_network',True)) and (line['service'] not in plan['authorization_services'] or line.get('authorized',True)) and (line['service']!='prescription' or line.get('formulary',True))
        if not accepted:noncovered+=net;continue
        unpaid_ded=max(0,min(policy['individual_deductible']-i['deductible'],policy['family_deductible']-f['deductible']));ded=min(net,unpaid_ded);after=net-ded;nominal=int(Fraction(max(after-policy['copay'],0)*policy['payer_bps'],10000));charge=min(net-nominal,max(0,min(policy['individual_oop']-i['oop'],policy['family_oop']-f['oop'])));paid=min(net-charge,max(0,policy['annual_benefit']-i['benefit']));noncovered+=net-charge-paid;payout+=paid;member+=charge
        for a in (i,f):a['deductible']+=min(ded,charge);a['oop']+=charge;a['benefit']+=paid
    return dict(payout_cents=payout,member_cents=member,other_payer_cents=other_total,noncovered_cents=noncovered,individual=i,family=f)
