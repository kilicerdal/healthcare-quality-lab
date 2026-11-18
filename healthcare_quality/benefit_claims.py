"""Atomic synthetic claim lines, annual family accumulators and balanced adjustment ledger."""
from copy import deepcopy
from contextlib import contextmanager
import json,sqlite3,re
from pathlib import Path
from healthcare_quality.benefits import calculate,policy_for,ZERO,invalid
from healthcare_quality.ai_schema import digest
from healthcare_quality.workflow import ACTORS,WorkflowError
FAMILIES={'M100':'F100','M200':'F100','M300':'F100','M400':'F400'}
class BenefitClaims:
    def __init__(self,path):
        self.path=Path(path);self.path.parent.mkdir(parents=True,exist_ok=True)
        with self.tx() as db:
            for sql in ["CREATE TABLE IF NOT EXISTS benefit_claims(id TEXT PRIMARY KEY, member TEXT NOT NULL, family TEXT NOT NULL, year INTEGER NOT NULL, record TEXT NOT NULL)","CREATE TABLE IF NOT EXISTS accumulators(scope TEXT, owner TEXT, year INTEGER, record TEXT NOT NULL, PRIMARY KEY(scope,owner,year))","CREATE TABLE IF NOT EXISTS benefit_ledger(seq INTEGER PRIMARY KEY, claim_id TEXT NOT NULL, operation TEXT NOT NULL, amount INTEGER NOT NULL)","CREATE TABLE IF NOT EXISTS benefit_operations(key TEXT PRIMARY KEY, request_hash TEXT NOT NULL, result TEXT NOT NULL)"]:db.execute(sql)
    @contextmanager
    def tx(self):
        db=sqlite3.connect(self.path,timeout=5,isolation_level=None);db.row_factory=sqlite3.Row
        try:db.execute('BEGIN IMMEDIATE');yield db;db.commit()
        except BaseException:db.rollback();raise
        finally:db.close()
    def actor(self,id):
        a=next((a for a in ACTORS if a['id']==id),None)
        if not a:raise WorkflowError('FORBIDDEN','Known actor required',403)
        return a
    def account(self,db,scope,owner,year):
        row=db.execute('SELECT record FROM accumulators WHERE scope=? AND owner=? AND year=?',(scope,owner,year)).fetchone();return json.loads(row[0]) if row else deepcopy(ZERO)
    def put_account(self,db,scope,owner,year,value):
        if any(type(v) is not int or v<0 for v in value.values()):raise RuntimeError('Accumulator invariant failed')
        db.execute('INSERT INTO accumulators VALUES(?,?,?,?) ON CONFLICT(scope,owner,year) DO UPDATE SET record=excluded.record',(scope,owner,year,json.dumps(value)))
    def load(self,db,id):
        row=db.execute('SELECT record FROM benefit_claims WHERE id=?',(id,)).fetchone()
        if not row:raise WorkflowError('NOT_FOUND','Benefit claim not found',404)
        return json.loads(row[0])
    def visible(self,actor,r):
        if actor['role']=='customer' and actor['member_id']!=r['member_id']:raise WorkflowError('FORBIDDEN','Own member only',403)
    def save(self,db,r):db.execute('UPDATE benefit_claims SET record=? WHERE id=?',(json.dumps(r),r['id']))
    def apply(self,db,r,lines,credit=False):
        ind=self.account(db,'member',r['member_id'],r['year']);fam=self.account(db,'family',r['family_id'],r['year'])
        if credit:
            for a in (ind,fam):
                for k,v in r['calculation']['allocation'].items():a[k]-=v
        else:
            policy=r.get('policy_snapshot') or policy_for(r['service_date'],r['plan_id'])
            if r.get('policy_hash') and digest(policy)!=r['policy_hash']:raise WorkflowError('POLICY_SNAPSHOT_MISMATCH','Stored policy snapshot changed',409)
            c=calculate(policy,lines,ind,fam);r['calculation']=c;ind=c['individual'];fam=c['family']
        self.put_account(db,'member',r['member_id'],r['year'],ind);self.put_account(db,'family',r['family_id'],r['year'],fam)
    def operate(self,actor_id,body,action,id=None):
        actor=self.actor(actor_id)
        if not isinstance(body,dict) or type(body.get('operation_key')) is not str or not re.fullmatch(r'[A-Za-z0-9_-]{8,80}',body['operation_key']):invalid('Provide an 8–80 character operation_key')
        allowed={'submit':{'operation_key','id','member_id','plan_id','service_date','lines'},'pay':{'operation_key','expected_revision'},'reverse':{'operation_key','expected_revision','note'},'adjust':{'operation_key','expected_revision','lines','note'},'appeal':{'operation_key','expected_revision','note'},'resolve':{'operation_key','expected_revision','lines','note'}}
        if action not in allowed or set(body)!=allowed[action]:invalid('Exact fields required for '+str(action))
        if action!='submit' and (type(body['expected_revision']) is not int or body['expected_revision']<1):invalid('expected_revision must be positive integer')
        if 'note' in body and (type(body['note']) is not str or not 3<=len(body['note'])<=1000):invalid('Provide a review note')
        request_hash=digest(dict(actor=actor_id,action=action,id=id,body=body))
        with self.tx() as db:
            old=db.execute('SELECT request_hash,result FROM benefit_operations WHERE key=?',(body['operation_key'],)).fetchone()
            if old:
                if old[0]!=request_hash:raise WorkflowError('IDEMPOTENCY_CONFLICT','Operation key already used with different input',409)
                return json.loads(old[1])
            if action=='submit':
                id=body['id']
                if type(id) is not str or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{2,47}',id):invalid('Invalid claim ID')
                if actor['role']!='customer' or actor['member_id']!=body['member_id'] or body['member_id'] not in FAMILIES:raise WorkflowError('FORBIDDEN','Submit only supported own-member teaching claims',403)
                if db.execute('SELECT 1 FROM benefit_claims WHERE id=?',(id,)).fetchone():raise WorkflowError('DUPLICATE_CLAIM','Claim already exists',409)
                p=policy_for(body['service_date'],body['plan_id']);r=dict(id=id,member_id=body['member_id'],family_id=FAMILIES[body['member_id']],plan_id=body['plan_id'],service_date=body['service_date'],year=p['year'],policy_snapshot=deepcopy(p),policy_hash=digest(p),lines=deepcopy(body['lines']),revision=1,state='adjudicated',events=[])
                self.apply(db,r,r['lines']);db.execute('INSERT INTO benefit_claims VALUES(?,?,?,?,?)',(id,r['member_id'],r['family_id'],r['year'],json.dumps(r)))
            else:
                r=self.load(db,id);self.visible(actor,r)
                role={'pay':'finance','reverse':'finance','adjust':'adjuster','appeal':'customer','resolve':'adjuster'}[action]
                if actor['role']!=role:raise WorkflowError('FORBIDDEN','Role cannot perform this operation',403)
                if r['revision']!=body['expected_revision']:raise WorkflowError('REVISION_CONFLICT','Reload current claim',409)
                expected={'pay':'adjudicated','reverse':'paid','adjust':'paid','appeal':'adjudicated','resolve':'appealed'}[action]
                if r['state']!=expected:raise WorkflowError('INVALID_TRANSITION','Operation not allowed from current state',409)
                if action=='pay':db.execute('INSERT INTO benefit_ledger(claim_id,operation,amount) VALUES(?,?,?)',(id,body['operation_key'],r['calculation']['totals']['payout_cents']));r['state']='paid'
                elif action=='reverse':
                    self.apply(db,r,r['lines'],True);db.execute('INSERT INTO benefit_ledger(claim_id,operation,amount) VALUES(?,?,?)',(id,body['operation_key'],-r['calculation']['totals']['payout_cents']));r['state']='reversed'
                elif action in ('adjust','resolve'):
                    prior=r['calculation']['totals']['payout_cents'];self.apply(db,r,r['lines'],True);r['lines']=deepcopy(body['lines']);self.apply(db,r,r['lines'])
                    if action=='adjust':
                        db.execute('INSERT INTO benefit_ledger(claim_id,operation,amount) VALUES(?,?,?)',(id,body['operation_key'],-prior));db.execute('INSERT INTO benefit_ledger(claim_id,operation,amount) VALUES(?,?,?)',(id,body['operation_key'],r['calculation']['totals']['payout_cents']))
                    else:r['state']='adjudicated'
                else:r['state']='appealed'
                r['revision']+=1
            r['events'].append(dict(rule_ids=['BN-001','BN-005'] if action=='submit' else ['BN-007'] if action in ('appeal','resolve') else ['BN-006'],action=action,actor=actor_id,revision=r['revision'],operation_key=body['operation_key'],note=body.get('note')));self.save(db,r)
            result=self.project(db,r);db.execute('INSERT INTO benefit_operations VALUES(?,?,?)',(body['operation_key'],request_hash,json.dumps(result)));return result
    def project(self,db,r):return {**deepcopy(r),'ledger':[dict(x) for x in db.execute('SELECT seq,operation,amount FROM benefit_ledger WHERE claim_id=? ORDER BY seq',(r['id'],))],'current_member_accumulators':self.account(db,'member',r['member_id'],r['year']),'current_family_accumulators':self.account(db,'family',r['family_id'],r['year'])}
    def get(self,actor_id,id):
        actor=self.actor(actor_id)
        with self.tx() as db:r=self.load(db,id);self.visible(actor,r);return self.project(db,r)
