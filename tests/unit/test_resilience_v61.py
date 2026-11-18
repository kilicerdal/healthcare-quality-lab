from concurrent.futures import ThreadPoolExecutor
import sqlite3,random
import pytest
from healthcare_quality.benefit_claims import BenefitClaims
from healthcare_quality.workflow import WorkflowError
from tests.unit.test_benefits_v60 import submit,action,line
from healthcare_quality.ai_runner import run_cases
from tests.support.ai_fixtures import sample_case
from tests.unit.test_focused_v57 import replay_output
pytestmark=[pytest.mark.unit,pytest.mark.regression]
def test_simultaneous_payments_exactly_once_and_restart(tmp_path):
    path=tmp_path/'b.sqlite';s=BenefitClaims(path);r=submit(s)
    def pay(i):
        try:return action(BenefitClaims(path),r,'pay',key='parallel-'+str(i))
        except WorkflowError as e:return e.code
    with ThreadPoolExecutor(max_workers=8) as pool:results=list(pool.map(pay,range(16)))
    assert sum(isinstance(x,dict) for x in results)==1;current=BenefitClaims(path).get('auditor-demo',r['id']);assert len(current['ledger'])==1 and current['revision']==2 and len(current['events'])==2

def test_same_idempotency_key_concurrent_submit(tmp_path):
    s=BenefitClaims(tmp_path/'b.sqlite')
    with ThreadPoolExecutor(max_workers=6) as pool:rows=list(pool.map(lambda _:submit(s),range(12)))
    assert all(x==rows[0] for x in rows);assert len(s.get('auditor-demo','BEN-100')['events'])==1

def test_database_failure_rolls_back_payment(tmp_path):
    s=BenefitClaims(tmp_path/'b.sqlite');r=submit(s)
    with s.tx() as db:db.execute("CREATE TRIGGER abort_pay BEFORE INSERT ON benefit_ledger BEGIN SELECT RAISE(ABORT,'injected storage failure'); END")
    with pytest.raises(sqlite3.IntegrityError):action(s,r,'pay')
    current=s.get('auditor-demo',r['id']);assert current['state']=='adjudicated' and current['revision']==1 and not current['ledger']
    with s.tx() as db:db.execute('DROP TRIGGER abort_pay')
    assert action(s,r,'pay')['state']=='paid'

def test_seeded_state_machine_rejections_never_mutate(tmp_path):
    s=BenefitClaims(tmp_path/'b.sqlite');r=submit(s);rng=random.Random(61)
    for i in range(50):
        before=s.get('auditor-demo',r['id']);kind=rng.choice(['pay','reverse','adjust'])
        try:
            extra={} if kind=='pay' else dict(note='State machine generated check')
            if kind=='adjust':extra['lines']=[line(rng.randint(1,100000))]
            r=action(s,before,kind,key='machine-'+str(i),**extra)
            assert sum(x['amount'] for x in r['ledger'])==(r['calculation']['totals']['payout_cents'] if r['state']=='paid' else 0)
        except WorkflowError:assert s.get('auditor-demo',r['id'])==before

@pytest.mark.parametrize('case',[sample_case(),replay_output()['cases'][0]])
def test_real_http_and_service_observations_agree(case):
    service=run_cases([case]);http=run_cases([case],transport='http');assert http['failed']==service['failed']==0
    assert [s['observed'] for s in http['results'][0]['steps']]==[s['observed'] for s in service['results'][0]['steps']]

def test_mutation_sweep_retains_survivors():
    from tools.mutations import benchmark
    r=benchmark();assert r['total']>=10 and r['detected']>=5 and len(r['survived'])==r['total']-r['detected']
