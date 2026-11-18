"""Actual isolated loopback HTTP rehearsals with measured assertions and no inference."""
from contextlib import contextmanager,closing
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Thread
from uuid import uuid4
import json,os,sqlite3,subprocess,sys,time
from werkzeug.serving import make_server
from healthcare_quality.integration import Coordinator,IntegrationError
from healthcare_quality.integration_peer import create_peer
from healthcare_quality.benefit_claims import BenefitClaims

SCENARIOS=('normal','lost_ack','temporary_unavailable','permanent_timeout','wrong_receipt','ineligible','stale_claim','crash_recovery','webhook_replay')
@contextmanager
def peer_server(path,token,profile):
    app=create_peer(path,token,profile);server=make_server('127.0.0.1',0,app,threaded=True);thread=Thread(target=server.serve_forever,daemon=True);thread.start()
    try:yield 'http://127.0.0.1:'+str(server.server_port)
    finally:server.shutdown();thread.join(5);server.server_close()

def rehearse(scenario):
    if scenario not in SCENARIOS:raise ValueError('Select a known isolated integration scenario')
    started=time.monotonic();token=uuid4().hex;assertions=[]
    def check(name,observed,expected):assertions.append(dict(name=name,observed=observed,expected=expected,passed=type(observed) is type(expected) and observed==expected))
    with TemporaryDirectory(prefix='hql-integration-') as tmp:
        root=Path(tmp);service=BenefitClaims(root/'benefits.sqlite');member='M400' if scenario=='ineligible' else 'M100';claim='INT-CLAIM';key='intent-'+uuid4().hex
        original=service.operate('customer-'+member.lower(),dict(operation_key='submit-integration',id=claim,member_id=member,plan_id='commercial_ppo',service_date='2026-03-01',lines=[dict(id='LINE-1',service='medical',allowed_cents=100000)]),'submit')
        profile=scenario if scenario in ('lost_ack','temporary_unavailable','permanent_timeout','wrong_receipt') else 'normal'
        with peer_server(root/'peer.sqlite',token,profile) as url:
            coordinator=Coordinator(root/'outbox.sqlite',service,url,token);intent=coordinator.enqueue('finance-demo',claim,key)
            if scenario=='stale_claim':service.operate('finance-demo',dict(operation_key='other-local-payment',expected_revision=1),'pay',claim)
            if scenario=='crash_recovery':
                env={**os.environ,'HQL_PEER_TOKEN':token};result=subprocess.run([sys.executable,'-m','tools.integration_worker','--state',str(coordinator.path),'--benefits',str(service.path),'--url',url,'--key',key],env=env,capture_output=True,timeout=15)
                check('worker really exited after local commit',result.returncode,23)
                check('outbox remained pending',coordinator.get(key)['state'],'pending')
                service=BenefitClaims(service.path);coordinator=Coordinator(coordinator.path,service,url,token)
            result=coordinator.deliver(key)
            if scenario=='webhook_replay':
                event=dict(event_id='event-payment-002',operation_key=key,sequence=2,amount_cents=71200)
                check('new webhook is only a signal',coordinator.webhook(event)['outcome'],'signalled')
                check('duplicate webhook is deduplicated',coordinator.webhook(event)['outcome'],'duplicate')
                stale={**event,'event_id':'event-payment-001','sequence':1};check('older webhook ignored',coordinator.webhook(stale)['outcome'],'stale')
                conflict=False
                try:coordinator.webhook({**event,'amount_cents':71201})
                except IntegrationError:conflict=True
                check('changed replay payload rejected',conflict,True)
                check('webhook never creates extra payment',coordinator.get(key)['state'],'settled')
            if scenario=='normal':
                duplicate=dict(operation_key=key,claim_id=claim,amount_cents=71200)
                check('peer same-key replay returns same receipt',coordinator.request('/payments',duplicate)[1],result['receipt'])
                check('peer changed-key input rejected',coordinator.request('/payments',{**duplicate,'amount_cents':1})[0],409)
            final=service.get('auditor-demo',claim)
            with closing(sqlite3.connect(root/'peer.sqlite')) as db:remote_count=db.execute('SELECT COUNT(*) FROM payments').fetchone()[0]
            state={'permanent_timeout':'pending','wrong_receipt':'quarantined','ineligible':'ineligible','stale_claim':'quarantined'}.get(scenario,'settled')
            check('outbox outcome',coordinator.get(key)['state'],state)
            check('remote payment count',remote_count,0 if scenario in ('permanent_timeout','ineligible','stale_claim') else 1)
            local_paid=scenario not in ('permanent_timeout','wrong_receipt','ineligible')
            check('local ledger entries',len(final['ledger']),1 if local_paid else 0)
            check('local ledger balance',sum(x['amount'] for x in final['ledger']),71200 if local_paid else 0)
            check('local history events',len(final['events']),2 if local_paid else 1)
            check('local revision',final['revision'],2 if local_paid else 1)
            check('attempt budget respected',coordinator.get(key)['attempts']<=3 if scenario!='crash_recovery' else coordinator.get(key)['attempts']<=4,True)
            saved=coordinator.get(key)
    return dict(id=uuid4().hex,scenario=scenario,passed=all(x['passed'] for x in assertions),assertions=assertions,outbox=saved,remote_payments=remote_count,local_ledger=final['ledger'],duration_ms=round((time.monotonic()-started)*1000,2),scope='Actual isolated HTTP eligibility/payment peer, new stores and scripted faults. Synthetic money only. An outbox is eventually reconciled; no atomic cross-service transaction or production payment integration is claimed.')
