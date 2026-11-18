"""Bounded synthetic performance, concurrency, restart and storage-failure rehearsal."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from tempfile import TemporaryDirectory
import argparse,json,sqlite3,statistics,time,math
from healthcare_quality.benefit_claims import BenefitClaims
from healthcare_quality.workflow import WorkflowError
from tools.fingerprints import source_hash

def benchmark(count=40):
    latencies=[];at=time.monotonic()
    with TemporaryDirectory(prefix='hql-resilience-') as folder:
        path=Path(folder)/'claims.sqlite';s=BenefitClaims(path)
        for i in range(count):
            start=time.monotonic();s.operate('customer-m100',dict(operation_key='load-submit-'+str(i),id='LOAD-'+str(i),member_id='M100',plan_id='commercial_ppo',service_date='2026-03-01',lines=[dict(id='L1',service='medical',allowed_cents=45000)]),'submit');latencies.append((time.monotonic()-start)*1000)
        def pay(i):
            try:s.operate('finance-demo',dict(operation_key='load-pay-'+str(i),expected_revision=1),'pay','LOAD-0');return 'paid'
            except WorkflowError as e:return e.code
        with ThreadPoolExecutor(max_workers=8) as pool:outcomes=list(pool.map(pay,range(16)))
        current=BenefitClaims(path).get('auditor-demo','LOAD-0');assert outcomes.count('paid')==1 and len(current['ledger'])==1
        before=s.get('auditor-demo','LOAD-1')
        with s.tx() as db:db.execute("CREATE TRIGGER fail_ledger BEFORE INSERT ON benefit_ledger BEGIN SELECT RAISE(ABORT,'injected failure'); END")
        rollback=False
        try:s.operate('finance-demo',dict(operation_key='failure-test',expected_revision=1),'pay','LOAD-1')
        except sqlite3.IntegrityError:rollback=s.get('auditor-demo','LOAD-1')==before
        assert rollback
    return dict(status='passed',source_hash=source_hash(),operations=count,latency_median_ms=statistics.median(latencies),latency_p95_ms=sorted(latencies)[math.ceil(.95*len(latencies))-1],duration_seconds=round(time.monotonic()-at,3),concurrent_attempts=16,successful_payments=1,ledger_entries=1,restart_preserved=True,rollback_preserved=True,scope='Bounded local synthetic rehearsal; timings describe this machine, not capacity, SLA or production load certification.')
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    if a.output.exists():p.error('Refusing to overwrite evidence')
    result=benchmark();a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
