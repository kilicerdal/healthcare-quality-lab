"""Durable synthetic payment outbox/inbox and bounded loopback HTTP reconciliation.
No distributed transaction is claimed. Unknown outcomes remain pending, and retries
bind to the original intent. Webhooks are signals, never independent payment authority.
"""
from contextlib import contextmanager
from copy import deepcopy
from pathlib import Path
import json,re,sqlite3,urllib.request,urllib.error
from urllib.parse import urlsplit
from healthcare_quality.ai_schema import digest
from healthcare_quality.workflow import WorkflowError

class IntegrationError(ValueError):pass

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):raise IntegrationError('Peer redirects are forbidden')

class Coordinator:
    def __init__(self,path,benefits,peer_url,token,timeout=.3):
        u=urlsplit(peer_url)
        if u.scheme!='http' or u.hostname!='127.0.0.1' or u.path not in ('','/') or u.query or u.fragment or u.username or u.password or not u.port:raise IntegrationError('Only an isolated loopback peer URL is allowed')
        if not .05<=timeout<=2:raise IntegrationError('Bounded peer timeout required')
        self.path=Path(path);self.path.parent.mkdir(parents=True,exist_ok=True);self.benefits=benefits;self.url=peer_url.rstrip('/');self.token=token;self.timeout=timeout
        with self.tx() as db:
            db.execute('CREATE TABLE IF NOT EXISTS outbox(key TEXT PRIMARY KEY, claim_id TEXT NOT NULL UNIQUE, record TEXT NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS inbox(event_id TEXT PRIMARY KEY, fingerprint TEXT NOT NULL, record TEXT NOT NULL)')
    @contextmanager
    def tx(self):
        db=sqlite3.connect(self.path,timeout=5,isolation_level=None)
        try:db.execute('BEGIN IMMEDIATE');yield db;db.commit()
        except BaseException:db.rollback();raise
        finally:db.close()
    def request(self,path,body=None):
        req=urllib.request.Request(self.url+path,data=json.dumps(body).encode() if body is not None else None,headers={'Content-Type':'application/json','X-Lab-Token':self.token})
        try:response=urllib.request.build_opener(NoRedirect).open(req,timeout=self.timeout)
        except urllib.error.HTTPError as error:response=error
        with response:
            raw=response.read(65537)
            if len(raw)>65536:raise IntegrationError('Peer response budget exceeded')
            return response.status,json.loads(raw)
    def get(self,key):
        with self.tx() as db:row=db.execute('SELECT record FROM outbox WHERE key=?',(key,)).fetchone()
        if not row:raise IntegrationError('Unknown intent')
        return json.loads(row[0])
    def enqueue(self,actor,claim_id,key):
        if actor!='finance-demo' or not isinstance(key,str) or not re.fullmatch(r'[A-Za-z0-9_-]{8,70}',key):raise IntegrationError('Finance and a bounded idempotency key are required')
        r=self.benefits.get(actor,claim_id);binding=dict(claim_id=claim_id,amount_cents=r['calculation']['totals']['payout_cents'],member_id=r['member_id'],revision=r['revision'],policy_hash=r['policy_hash'])
        with self.tx() as db:
            old=db.execute('SELECT record FROM outbox WHERE key=?',(key,)).fetchone()
            if old:
                prior=json.loads(old[0])
                # Retrying enqueue after settlement must retain the original binding.
                if prior['binding']['claim_id']!=claim_id or prior['binding']['amount_cents']!=binding['amount_cents'] or prior['binding']['policy_hash']!=binding['policy_hash']:raise IntegrationError('Intent key is already bound to different input')
                return prior
            if db.execute('SELECT 1 FROM outbox WHERE claim_id=?',(claim_id,)).fetchone():raise IntegrationError('Only one payment intent per claim is allowed')
            if r['state']!='adjudicated':raise IntegrationError('Only adjudicated claims can enter the outbox')
            record=dict(key=key,binding=binding,state='pending',attempts=0,events=[],last_sequence=0,receipt=None)
            db.execute('INSERT INTO outbox VALUES(?,?,?)',(key,claim_id,json.dumps(record)));return record
    def update(self,key,fn):
        with self.tx() as db:
            row=db.execute('SELECT record FROM outbox WHERE key=?',(key,)).fetchone()
            if not row:raise IntegrationError('Unknown intent')
            r=json.loads(row[0]);fn(r);db.execute('UPDATE outbox SET record=? WHERE key=?',(json.dumps(r),key));return r
    def settle(self,key,receipt,crash_after_local=False):
        r=self.get(key);b=r['binding']
        if not isinstance(receipt,dict) or receipt.get('operation_key')!=key or receipt.get('claim_id')!=b['claim_id'] or type(receipt.get('amount_cents')) is not int or receipt['amount_cents']!=b['amount_cents'] or receipt.get('status')!='paid':
            return self.update(key,lambda x:x.update(state='quarantined',error='Peer receipt does not match frozen payment intent'))
        try:
            result=self.benefits.operate('finance-demo',dict(operation_key='local-'+key,expected_revision=b['revision']),'pay',b['claim_id'])
        except WorkflowError as error:return self.update(key,lambda x:x.update(state='reconciliation_required',error=error.code,receipt=receipt))
        if crash_after_local:raise RuntimeError('Injected interruption after local commit before outbox acknowledgement')
        return self.update(key,lambda x:x.update(state='settled',receipt=receipt,local_revision=result['revision']))
    def deliver(self,key,crash_after_local=False):
        r=self.get(key)
        if r['state']!='pending':return r
        b=r['binding'];current=self.benefits.get('finance-demo',b['claim_id'])
        owned_local=any(x['operation']=='local-'+key for x in current['ledger'])
        if current['policy_hash']!=b['policy_hash'] or current['member_id']!=b['member_id'] or current['calculation']['totals']['payout_cents']!=b['amount_cents'] or (not owned_local and (current['revision']!=b['revision'] or current['state']!='adjudicated')):
            return self.update(key,lambda x:x.update(state='quarantined',error='Claim snapshot changed before delivery'))
        # An ambiguous outcome is queried before retrying the exact original key.
        for attempt in range(3):
            r=self.update(key,lambda x:x.update(attempts=x['attempts']+1))
            try:
                status,receipt=self.request('/payments/'+key)
                if status==200:return self.settle(key,receipt,crash_after_local)
                if status!=404:raise IntegrationError('Unexpected peer lookup status')
                status,eligibility=self.request('/eligibility/'+b['member_id'])
                if status!=200 or eligibility.get('member_id')!=b['member_id'] or eligibility.get('active') is not True:return self.update(key,lambda x:x.update(state='ineligible',error='Synthetic eligibility not active'))
                status,receipt=self.request('/payments',dict(operation_key=key,claim_id=b['claim_id'],amount_cents=b['amount_cents']))
                if status==200:return self.settle(key,receipt,crash_after_local)
                if status not in (429,503):return self.update(key,lambda x:x.update(state='quarantined',error='Unexpected peer response '+str(status)))
                self.update(key,lambda x:x['events'].append(dict(event='retryable_response',status=status)))
            except (urllib.error.URLError,TimeoutError,ConnectionError,IntegrationError,ValueError) as error:
                self.update(key,lambda x:x['events'].append(dict(event='ambiguous_peer_outcome',error_type=type(error).__name__)))
        return self.get(key)
    def webhook(self,event):
        if not isinstance(event,dict) or set(event)!={'event_id','operation_key','sequence','amount_cents'} or not isinstance(event['event_id'],str) or not re.fullmatch(r'[A-Za-z0-9_-]{8,80}',event['event_id']) or not isinstance(event['operation_key'],str) or not re.fullmatch(r'[A-Za-z0-9_-]{8,70}',event['operation_key']) or type(event['sequence']) is not int or not 1<=event['sequence']<=1000 or type(event['amount_cents']) is not int:raise IntegrationError('Invalid bounded webhook')
        fingerprint=digest(event)
        with self.tx() as db:
            old=db.execute('SELECT fingerprint,record FROM inbox WHERE event_id=?',(event['event_id'],)).fetchone()
            if old:
                if old[0]!=fingerprint:raise IntegrationError('Event ID reused with changed payload')
                return dict(outcome='duplicate',event_id=event['event_id'])
            row=db.execute('SELECT record FROM outbox WHERE key=?',(event['operation_key'],)).fetchone()
            if not row:raise IntegrationError('Unknown intent signal')
            r=json.loads(row[0]);outcome='stale' if event['sequence']<=r['last_sequence'] else 'signalled'
            if event['amount_cents']!=r['binding']['amount_cents']:outcome='quarantined'
            if outcome=='signalled':r['last_sequence']=event['sequence']
            r['events'].append(dict(event='webhook',outcome=outcome,event_id=event['event_id']))
            db.execute('INSERT INTO inbox VALUES(?,?,?)',(event['event_id'],fingerprint,json.dumps(dict(event=event,outcome=outcome))))
            db.execute('UPDATE outbox SET record=? WHERE key=?',(json.dumps(r),r['key']))
            return dict(outcome=outcome,event_id=event['event_id'],scope='Notification only; reconcile against peer receipt before any local payment.')
