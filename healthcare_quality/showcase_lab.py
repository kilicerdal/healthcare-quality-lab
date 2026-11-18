"""Authored, repeatable demonstrations. No inference or persistent user-store writes."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
from tempfile import TemporaryDirectory
import threading
import urllib.request
from urllib.error import HTTPError
from uuid import uuid4
from healthcare_quality import reference
from healthcare_quality.workflow import ClaimStore, WorkflowService, WorkflowError

ROOT = Path(__file__).resolve().parents[1]
SCENARIOS = {
    'oracle': 'A plausible AI expectation is blocked',
    'concurrency': 'Two payment requests, one ledger entry',
    'recovery': 'Worker interruption rolls back partial payment',
    'rule-change': 'A requirement change invalidates reviewed evidence',
}

def checkpoint(label, expected, observed):
    return {'label': label, 'expected': expected, 'observed': observed,
            'passed': type(expected) is type(observed) and expected == observed}

def prepared(path):
    service = WorkflowService(ClaimStore(path))
    service.submit('customer-m100', {'claim_id': 'PROOF-100', 'member_id': 'M100',
                                   'service': 'medical', 'amount_cents': 100000})
    service.transition('adjuster-demo', 'PROOF-100', {'target': 'approved'})
    return service

def counts(service):
    value = service.get('auditor-demo', 'PROOF-100')
    with service.store.transaction() as db:
        ledger = db.execute('SELECT COUNT(*) FROM payments').fetchone()[0]
    return {'status': value['claim']['status'], 'revision': value['claim']['revision'],
            'events': len(value['events']), 'ledger_entries': ledger,
            'payment_cents': value['payment']['amount_cents'] if value['payment'] else None}

@contextmanager
def http_runtime(path):
    from healthcare_quality.app import create_app
    from werkzeug.serving import make_server
    app = create_app({'TESTING': True, 'DATABASE': str(path)})
    server = make_server('127.0.0.1', 0, app, threaded=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f'http://127.0.0.1:{server.server_port}'
    finally:
        server.shutdown(); thread.join(timeout=5); server.server_close()

def concurrency(path):
    service = prepared(path)
    barrier = threading.Barrier(2)
    with http_runtime(path) as base:
        def pay(_):
            barrier.wait(timeout=5)
            request = urllib.request.Request(base + '/api/claims/PROOF-100/transitions',
                data=b'{"target":"paid"}', headers={'Content-Type': 'application/json',
                                                    'X-Demo-Actor': 'finance-demo'})
            try:
                response = urllib.request.urlopen(request, timeout=10)
            except HTTPError as error:
                response = error
            with response:
                return {'status': response.status, 'request_id': response.headers['X-Request-ID'],
                        'body': json.load(response)}
        with ThreadPoolExecutor(max_workers=2) as pool:
            responses = list(pool.map(pay, range(2)))
    state = counts(service)
    checks = [checkpoint('HTTP outcomes', [200, 409], sorted(r['status'] for r in responses)),
              checkpoint('One simulated payment', 1, state['ledger_entries']),
              checkpoint('Stored payment equals payout', 90000, state['payment_cents']),
              checkpoint('Exactly three committed revisions', 3, state['revision']),
              checkpoint('Exactly three history events', 3, state['events'])]
    return {'checks': checks, 'responses': responses, 'state': state,
            'timeline': service.get('auditor-demo', 'PROOF-100')['events'],
            'method': 'Two real loopback HTTP clients released by a thread barrier; SQLite serializes writes. This is not a distributed load test.'}

def crash_worker(path):
    # Deliberately terminate after service writes, before the transaction commits.
    class InterruptedStore(ClaimStore):
        armed = False
        @contextmanager
        def transaction(self, *, write=False):
            with super().transaction(write=write) as db:
                yield db
                if write and self.armed:
                    import os
                    os._exit(73)
    store = InterruptedStore(path); store.armed = True
    WorkflowService(store).transition('finance-demo', 'PROOF-100', {'target': 'paid'})

def recovery(path):
    service = prepared(path); before = counts(service)
    child = subprocess.run([sys.executable, '-m', 'healthcare_quality.showcase_lab',
                            '_interrupt', str(path)], cwd=ROOT, capture_output=True, timeout=15)
    after = counts(service)
    service.transition('finance-demo', 'PROOF-100', {'target': 'paid'})
    committed = counts(service)
    try:
        service.transition('finance-demo', 'PROOF-100', {'target': 'paid'})
        replay = 200
    except WorkflowError as error:
        replay = error.status
    unchanged = counts(service)
    return {'checks': [checkpoint('Worker exited at injected checkpoint', 73, child.returncode),
             checkpoint('Uncommitted writes rolled back', before, after),
             checkpoint('Retry created one ledger entry', 1, committed['ledger_entries']),
             checkpoint('Retry paid the correct amount', 90000, committed['payment_cents']),
             checkpoint('Repeated payment rejected', 409, replay),
             checkpoint('Rejected replay left state unchanged', committed, unchanged)],
            'before': before, 'after_interruption': after, 'after_retry': committed,
            'timeline': service.get('auditor-demo', 'PROOF-100')['events'],
            'method': 'Actual subprocess exit after payment/state/history writes and before SQLite commit. No production crash hook is installed.'}

def oracle(_path):
    from healthcare_quality.ai_studio import checked_cases, ExperimentStore, StudioService, StudioError
    case = {'id': 'AI-PROOF-ORACLE', 'title': 'Inspect the payout before trusting the case',
            'rule_ids': ['HC-007'], 'rationale': 'Authored demonstration of a plausible wrong expectation.',
            'assumptions': ['Synthetic data; this example was authored, not generated by a model.'],
            'steps': [{'action': 'evaluate', 'actor': 'none',
                       'data': {'plan_id': 'commercial_ppo', 'service': 'medical', 'amount_cents': 112345},
                       'expect': {'status': 200, 'decision': 'approved', 'reason': 'COVERED', 'payout_cents': 112345}}]}
    wrong = checked_cases([case], ['HC-007'])[0]
    fixed = deepcopy(case); fixed['steps'][0]['expect']['payout_cents'] = 102345
    corrected = checked_cases([fixed], ['HC-007'])[0]
    from healthcare_quality.ai_runner import run_cases
    healthy = run_cases([fixed])
    faulty = run_cases([fixed], evaluation_defect='deductible')
    # These are authored controls, not generated cases or a human approval claim.
    return {'checks': [checkpoint('Wrong expectation cannot be approved', False, wrong['review_ready']),
             checkpoint('Corrected expectation reaches review', True, corrected['review_ready']),
             checkpoint('Authored healthy control passes', 1, healthy['passed']),
             checkpoint('Seeded deductible defect produces a failed assertion', 1, faulty['failed']),
             checkpoint('Fault was a mismatch, not an execution error', None, faulty['results'][0]['execution_error'])],
            'investigation': {'input': case['steps'][0]['data'], 'rule': next(r for r in reference.FACTS['rules.json'] if r['id']=='HC-007'),
                'proposed': case['steps'][0]['expect'], 'independent_expected': reference.evaluate(case['steps'][0]['data'])[0],
                'mismatches': reference.check(case)['mismatches'],
                'actual_fault_observation': faulty['results'][0]['steps'][0]['observed'],
                'healthy_control': healthy, 'seeded_fault': faulty,
                'corrected': fixed['steps'][0]['expect'], 'approval': 'Not approved; explicit human review is still required.',
                'next_step': 'Inspect the mismatch, correct the expectation, then explicitly review the snapshot in AI Test Studio.'},
            'method': 'Authored wrong-answer fixture, not a live AI response. The corrected authored control passes the healthy service and detects a seeded skipped-deductible fault through an assertion mismatch. Generated cases still require explicit Studio review.'}

def rule_change_worker(path):
    from unittest.mock import patch
    from healthcare_quality.ai_studio import StudioService, ExperimentStore, StudioError
    from healthcare_quality import focused
    data = {'plan_id': 'commercial_ppo', 'service': 'medical', 'amount_cents': 112345}
    case = {'id':'AI-RULE-CHANGE','title':'Authored requirement-change control',
            'rule_ids':['HC-007'],'rationale':'Scripted review-control demonstration, not model generation.',
            'assumptions':['Synthetic authored fixture; scripted attestation is not a human review.'],
            'steps':[{'action':'evaluate','actor':'none','data':data,
                      'expect':{'status':200,'decision':'approved','reason':'COVERED','payout_cents':102345}}]}
    class AuthoredProvider:
        def generate(self, *args):
            return {'text':json.dumps({'cases':[case]}),'model':'authored-fixture',
                    'output_mode':'authored deterministic fixture; no inference'}
    studio=StudioService(ExperimentStore(path),AuthoredProvider())
    record=studio.generate({'requirement':'Exercise review freshness with an authored synthetic expectation.',
                'source_ids':['HC-007'],'model':'qwen2.5-coder:3b','strategy':'balanced-v1','count':1})
    reviewed=studio.review(record['id'],{'expected_revision':record['revision'],
        'approved_ids':[case['id']],'reviewer_label':'Scripted control demonstration',
        'review_note':'Authored control; test of review mechanics, not a human/model accuracy claim.',
        'expectations_checked':True})
    context=focused.context_for(data); old=reference.fingerprint()
    facts=deepcopy(reference.FACTS)
    next(p for p in facts['plans.json'] if p['id']=='commercial_ppo')['deductible_cents']=15000
    plans={p['id']:p for p in facts['plans.json']}
    with patch.object(reference,'FACTS',facts), patch.object(reference,'PLANS',plans):
        changed=reference.fingerprint(); new=reference.evaluate(data)[0]
        approval_current=studio.view(record['id'])['approval_matches_reference']
        try:
            studio.execute(record['id'],{'expected_revision':reviewed['revision']})
            blocked='EXECUTION_WAS_NOT_BLOCKED'
        except StudioError as error:blocked=error.code
        stale=focused.current(context)
    return {'checks':[checkpoint('Old focused context is stale',False,stale),
             checkpoint('Old review no longer matches reference',False,approval_current),
             checkpoint('Actual Studio execution guard blocks stale approval','STALE_REFERENCE',blocked),
             checkpoint('Original payout',102345,case['steps'][0]['expect']['payout_cents']),
             checkpoint('Changed reference observes new payout',97345,new['payout_cents'])],
            'change':{'plan':'commercial_ppo','deductible_before_cents':10000,'deductible_after_cents':15000,
                      'original_reference_fingerprint':old,'candidate_reference_fingerprint':changed,
                      'affected':['Focused context','Expected payout','Reference-bound review','Recorded measurements'],
                      'required_action':'Revise affected expectations and independently review them again before execution.'},
            'method':'Isolated child-process what-if contract, actual Studio review and stale-execution guard. Scripted authored fixture, no model or human-review claim. Runtime fixtures and user stores are unchanged.'}

def rule_change(path):
    child=subprocess.run([sys.executable,'-m','healthcare_quality.showcase_lab','_rule-change',str(path)],
                         cwd=ROOT,capture_output=True,text=True,timeout=15,check=True)
    return json.loads(child.stdout)

RUNNERS = {'oracle': oracle, 'concurrency': concurrency, 'recovery': recovery, 'rule-change': rule_change}

def run(scenario):
    if scenario not in RUNNERS:
        raise ValueError('Unknown authored scenario')
    with TemporaryDirectory(prefix='healthcare-proof-') as temporary:
        result = RUNNERS[scenario](Path(temporary) / 'claims.sqlite')
    return {'run_id': uuid4().hex, 'scenario': scenario, 'title': SCENARIOS[scenario], 'recorded_at': datetime.now(timezone.utc).isoformat(),
            'status': 'passed' if all(c['passed'] for c in result['checks']) else 'failed',
            'provenance': 'Authored deterministic scenario; executed now against disposable synthetic state.',
            'live_model_calls': 0, 'paid_api_calls': 0, **result}

if __name__ == '__main__':
    if len(sys.argv) == 3 and sys.argv[1] == '_interrupt':
        crash_worker(Path(sys.argv[2]))
    elif len(sys.argv) == 3 and sys.argv[1] == '_rule-change':
        print(json.dumps(rule_change_worker(Path(sys.argv[2]))))
    else:
        print(json.dumps(run(sys.argv[1]), indent=2))
