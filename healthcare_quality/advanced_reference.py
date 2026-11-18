"""Independent in-memory benefit lifecycle oracle, using the separate Fraction calculator.
Never imports BenefitClaims or the production calculate function. Expectations are not
learned from application responses. It models the bounded valid DSL, not arbitrary APIs.
"""
from copy import deepcopy
import json
from pathlib import Path
from healthcare_quality.benefit_reference import price
from healthcare_quality.ai_schema import digest

DATA=Path(__file__).with_name('data')
FACTS=json.loads((DATA/'benefits_v60.json').read_text())
PLANS={x['id']:x for x in json.loads((DATA/'plans.json').read_text())}
ACTORS={x['id']:x for x in json.loads((DATA/'actors.json').read_text())}
FAMILY={'M100':'F100','M200':'F100','M300':'F100','M400':'F400'}
ZERO=dict(deductible=0,oop=0,benefit=0)

class Rejection(Exception):
    def __init__(self,status,error):self.status,self.error=status,error

class Oracle:
    def __init__(self):self.claims={};self.accounts={};self.operations={}
    def account(self,scope,owner,year):return self.accounts.setdefault((scope,owner,year),deepcopy(ZERO))
    def projection(self,r,status=200):
        i=self.account('member',r['member'],r['year']);f=self.account('family',r['family'],r['year'])
        return dict(status=status,state=r['state'],revision=r['revision'],event_count=r['events'],
                    **r['totals'],ledger_cents=sum(r['ledger']),ledger_count=len(r['ledger']),
                    **{'individual_'+k:v for k,v in i.items()},**{'family_'+k:v for k,v in f.items()},
                    policy_id=r['policy']['id'],partial=r['partial'])
    def reprice(self,r,lines,credit=False):
        i=self.account('member',r['member'],r['year']);f=self.account('family',r['family'],r['year'])
        if credit:
            for a in (i,f):
                for k,v in r['allocation'].items():a[k]-=v
            return
        prior=deepcopy(i);value=price(r['date'],r['plan'],lines,i,f)
        r['allocation']={k:value['individual'][k]-prior[k] for k in ZERO}
        i.update(value['individual']);f.update(value['family'])
        r['totals']={k:value[k] for k in ('payout_cents','member_cents','other_payer_cents','noncovered_cents')}
        plan=PLANS[r['plan']];accepted=[]
        for line in lines:
            accepted.append(line['service'] in plan['services'] and (not plan['network_required'] or line.get('in_network',True)) and (line['service'] not in plan['authorization_services'] or line.get('authorized',True)) and (line['service']!='prescription' or line.get('formulary',True)))
        r['partial']=any(accepted) and not all(accepted)
    def step(self,s):
        snapshot=deepcopy((self.claims,self.accounts,self.operations))
        try:return self._step(s)
        except Rejection as e:
            self.claims,self.accounts,self.operations=snapshot
            return dict(status=e.status,error=e.error)
    def _step(self,s):
        a=s['action'];d=s['data'];id=d['claim_id'];actor=ACTORS[s['actor']]
        if a=='read':
            if id not in self.claims:raise Rejection(404,'NOT_FOUND')
            r=self.claims[id]
            if actor['role']=='customer' and actor['member_id']!=r['member']:raise Rejection(403,'FORBIDDEN')
            return deepcopy(self.projection(r))
        key=d['operation_key'];request=digest(dict(action=a,actor=s['actor'],data=d))
        if key in self.operations:
            prior,value=self.operations[key]
            if prior!=request:raise Rejection(409,'IDEMPOTENCY_CONFLICT')
            return deepcopy(value)
        if a=='submit':
            if actor['role']!='customer' or actor['member_id']!=d['member_id']:raise Rejection(403,'FORBIDDEN')
            if id in self.claims:raise Rejection(409,'DUPLICATE_CLAIM')
            from datetime import date
            try:date.fromisoformat(d['service_date'])
            except ValueError:raise Rejection(400,'INVALID_BENEFITS_REQUEST')
            p=next((p for p in FACTS['policies'] if p['start']<=d['service_date']<p['end']),None)
            if p is None or any(l.get('other_payer_cents',0)>l['allowed_cents'] or len({x['id'] for x in d['lines']})!=len(d['lines']) for l in d['lines']):raise Rejection(400,'INVALID_BENEFITS_REQUEST')
            r=dict(member=d['member_id'],family=FAMILY[d['member_id']],year=int(d['service_date'][:4]),date=d['service_date'],plan=d['plan_id'],policy=deepcopy(p),revision=1,events=1,state='adjudicated',ledger=[])
            self.reprice(r,d['lines']);self.claims[id]=r
        else:
            if id not in self.claims:raise Rejection(404,'NOT_FOUND')
            r=self.claims[id]
            if actor['role']=='customer' and actor['member_id']!=r['member']:raise Rejection(403,'FORBIDDEN')
            role={'pay':'finance','reverse':'finance','adjust':'adjuster','appeal':'customer','resolve':'adjuster'}[a]
            if actor['role']!=role:raise Rejection(403,'FORBIDDEN')
            if r['revision']!=d['expected_revision']:raise Rejection(409,'REVISION_CONFLICT')
            state={'pay':'adjudicated','reverse':'paid','adjust':'paid','appeal':'adjudicated','resolve':'appealed'}[a]
            if r['state']!=state:raise Rejection(409,'INVALID_TRANSITION')
            if a=='pay':r['ledger'].append(r['totals']['payout_cents']);r['state']='paid'
            elif a=='reverse':self.reprice(r,[],True);r['ledger'].append(-r['totals']['payout_cents']);r['state']='reversed'
            elif a in ('adjust','resolve'):
                if any(l.get('other_payer_cents',0)>l['allowed_cents'] for l in d['lines']) or len({x['id'] for x in d['lines']})!=len(d['lines']):raise Rejection(400,'INVALID_BENEFITS_REQUEST')
                old=r['totals']['payout_cents'];self.reprice(r,[],True);self.reprice(r,d['lines'])
                if a=='adjust':r['ledger'].extend([-old,r['totals']['payout_cents']])
                else:r['state']='adjudicated'
            else:r['state']='appealed'
            r['revision']+=1;r['events']+=1
        value=self.projection(r,201 if a=='submit' else 200);self.operations[key]=(request,deepcopy(value));return deepcopy(value)

def assess(case):
    oracle=Oracle();rows=[]
    for n,s in enumerate(case['steps'],1):
        expected=oracle.step(s);proposed=s['expect']
        diffs=[dict(field=k,proposed=proposed.get(k),reference=expected.get(k)) for k in set(expected)|set(proposed) if k not in proposed or k not in expected or type(proposed[k]) is not type(expected[k]) or proposed[k]!=expected[k]]
        rows.append(dict(step=n,expected=expected,mismatches=sorted(diffs,key=lambda d:d['field'])))
    return dict(matched=not any(r['mismatches'] for r in rows),steps=rows)
