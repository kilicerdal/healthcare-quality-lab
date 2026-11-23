"""Fixed authored rule vectors. No expected values derived from either calculator."""
from copy import deepcopy
from healthcare_quality.benefit_reference import price
from healthcare_quality.benefits import calculate,policy_for
from healthcare_quality.ai_schema import digest
ZERO=dict(deductible=0,oop=0,benefit=0)
# Integer cents. These literals are written from the synthetic BN contracts.
VECTORS=[
 dict(id='deductible-before-copay',amount=11001,expected=(0,11001,0,10000,11001,0),why='10000 deductible + 1000 copay; floor(1*0.8)=0 payer.',rules=['BN-004']),
 dict(id='floor-coinsurance',amount=11002,expected=(1,11001,0,10000,11001,1),why='After 10000 deductible and 1000 copay: floor(2*0.8)=1.',rules=['BN-004']),
 dict(id='oop-binding',amount=200000,expected=(170000,30000,0,10000,30000,170000),why='Nominal member 48800 is clipped to 30000 OOP; payer receives remainder.',rules=['BN-004']),
 dict(id='benefit-not-oop',amount=300000,expected=(200000,30000,70000,10000,30000,200000),why='OOP clips member at 30000; annual payer cap 200000 leaves 70000 noncovered.',rules=['BN-004']),
 dict(id='other-payer-first',amount=21002,other=10000,expected=(1,11001,0,10000,11001,1),why='Other payer reduces eligible from 21002 to 11002 before cost sharing.',rules=['BN-003','BN-004']),
 dict(id='rejected-service',amount=21002,service='dental',expected=(0,0,21002,0,0,0),why='PPO excludes dental; no deductible, OOP or benefit allocation.',rules=['BN-002','BN-005']),
 dict(id='family-deductible-binding',amount=2000,individual=dict(deductible=0,oop=0,benefit=0),family=dict(deductible=19500,oop=0,benefit=0),expected=(400,1600,0,500,1600,400),why='Family remaining500 caps deductible; copay1000 leaves500 at80%=400.',rules=['BN-004','BN-005']),
 dict(id='family-oop-binding',amount=20000,individual=dict(deductible=10000,oop=0,benefit=0),family=dict(deductible=20000,oop=59900,benefit=0),expected=(19900,100,0,10000,100,19900),why='Family OOP has100 remaining; final member100, payer19900; deductible already used10000.',rules=['BN-004','BN-005']),
 dict(id='july-boundary',amount=12002,day='2026-07-01',expected=(401,11601,0,10000,11601,401),why='July copay1500: floor((12002-10000-1500)*0.8)=401.',rules=['BN-001','BN-004']),
 dict(id='next-year-policy',amount=14002,day='2027-01-01',expected=(376,13626,0,12000,13626,376),why='2027 deductible12000 copay1500: floor(502*0.75)=376.',rules=['BN-001','BN-004'])]

def review():
 rows=[]
 for v in VECTORS:
  i=deepcopy(v.get('individual',ZERO));f=deepcopy(v.get('family',ZERO));lines=[dict(id='LINE-ONE',service=v.get('service','medical'),allowed_cents=v['amount'],other_payer_cents=v.get('other',0))];day=v.get('day','2026-03-01')
  oracle=price(day,'commercial_ppo',lines,i,f);production=calculate(policy_for(day,'commercial_ppo'),lines,i,f)
  def projection(result):
   totals=result.get('totals',result)
   return tuple(totals[k] for k in ('payout_cents','member_cents','noncovered_cents'))+tuple(result['individual'][k] for k in ('deductible','oop','benefit'))
  expected=tuple(v['expected']);a=projection(oracle);b=projection(production)
  rows.append(dict(id=v['id'],rules=v['rules'],reasoning=v['why'],expected=list(expected),reference=list(a),application=list(b),passed=a==expected and b==expected))
 return dict(kind='authored_rule_review',passed=all(r['passed'] for r in rows),vectors=rows,vectors_hash=digest(VECTORS),independent_human_review=False,scope='Fixed manually reasoned engineering vectors check both calculators; not external review or real insurance policy certification.')
