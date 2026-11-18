"""Optional shared-lab authentication, CSRF protection, reviewer identity and hash-linked audit."""
from collections import defaultdict,deque
from pathlib import Path
from datetime import datetime,timezone
from contextlib import contextmanager
import hashlib,hmac,json,secrets,sqlite3,time
from flask import g,request,session,jsonify
from werkzeug.security import check_password_hash
from healthcare_quality.workflow import ACTORS
from healthcare_quality.ai_schema import digest

class Audit:
    def __init__(self,path):
        self.path=Path(path);self.path.parent.mkdir(parents=True,exist_ok=True)
        with sqlite3.connect(self.path) as db:db.execute('CREATE TABLE IF NOT EXISTS review_audit(seq INTEGER PRIMARY KEY, record TEXT NOT NULL, previous TEXT NOT NULL, hash TEXT NOT NULL)')
    def append(self,record):
        with sqlite3.connect(self.path,timeout=5) as db:
            db.execute('BEGIN IMMEDIATE');row=db.execute('SELECT hash FROM review_audit ORDER BY seq DESC LIMIT 1').fetchone();previous=row[0] if row else '0'*64;record={**record,'at':datetime.now(timezone.utc).isoformat()};db.execute('INSERT INTO review_audit(record,previous,hash) VALUES(?,?,?)',(json.dumps(record,sort_keys=True),previous,digest(dict(previous=previous,record=record))))
    def verify(self):
        with sqlite3.connect(self.path) as db:rows=db.execute('SELECT seq,record,previous,hash FROM review_audit ORDER BY seq').fetchall()
        previous='0'*64;entries=[]
        for seq,raw,prior,hashed in rows:
            record=json.loads(raw)
            if seq!=len(entries)+1 or prior!=previous or hashed!=digest(dict(previous=prior,record=record)):return dict(valid=False,broken_at=seq,entries=entries)
            entries.append(dict(seq=seq,**record,hash=hashed));previous=hashed
        return dict(valid=True,entries=entries,head=previous,scope='Application hash chain detects modification/reordering; no external anchor or protection against privileged full-chain replacement.')

def configure(app):
    mode=app.config.get('AUTH_MODE','local');users=app.config.get('IDENTITIES',{});audit=Audit(Path(app.config['DATABASE']).with_name('review-audit.sqlite'));app.extensions['audit']=audit
    if mode not in ('local','shared'):raise ValueError('AUTH_MODE must be local or shared')
    if mode=='shared':
        if not app.config.get('SECRET_KEY') or len(app.config['SECRET_KEY'])<32 or not isinstance(users,dict) or not users:raise ValueError('Shared mode requires external SECRET_KEY of at least 32 characters and configured hashed identities')
        actor_ids={x['id'] for x in ACTORS}
        for name,u in users.items():
            if not isinstance(name,str) or not isinstance(u,dict) or set(u)!={'password_hash','roles','actor_id'} or not isinstance(u['password_hash'],str) or not u['password_hash'].startswith(('scrypt:','pbkdf2:')) or not isinstance(u['roles'],list) or not set(u['roles'])<={'analyst','reviewer','auditor','admin','customer','finance','adjuster'} or not u['roles'] or u['actor_id'] not in actor_ids:raise ValueError('Invalid hashed identity configuration')
    app.config.update(SESSION_COOKIE_HTTPONLY=True,SESSION_COOKIE_SAMESITE='Strict')
    attempts=defaultdict(deque)
    def identity():
        name=session.get('username') if mode=='shared' else None
        return dict(username=name,roles=users[name]['roles'],actor_id=users[name]['actor_id']) if name in users else None
    @app.before_request
    def protect():
        g.identity=identity()
        if mode!='shared' or not request.path.startswith('/api/') or request.path in ('/api/health','/api/ready','/api/auth/login','/api/auth/session'):return
        if not g.identity:return jsonify(error='AUTHENTICATION_REQUIRED'),401
        roles=set(g.identity['roles'])
        if request.headers.get('X-Demo-Actor') and request.headers['X-Demo-Actor']!=g.identity['actor_id']:return jsonify(error='ACTOR_SPOOFING_REJECTED'),403
        if request.path.startswith(('/api/ai','/api/quality','/api/coverage','/api/research')) and not roles&{'analyst','reviewer','auditor','admin'}:return jsonify(error='ROLE_REQUIRED'),403
        if request.method not in ('GET','HEAD','OPTIONS'):
            if not hmac.compare_digest(request.headers.get('X-CSRF-Token',''),session.get('csrf','!')):return jsonify(error='CSRF_REQUIRED'),403
            if request.path.startswith(('/api/ai','/api/quality','/api/coverage','/api/research')) and not roles&{'analyst','reviewer','admin'}:return jsonify(error='WRITE_ROLE_REQUIRED'),403
            if request.path.endswith('/review') and not roles&{'reviewer','admin'}:return jsonify(error='REVIEWER_ROLE_REQUIRED'),403
    @app.get('/api/auth/session')
    def who():return jsonify(mode=mode,identity=identity(),csrf_token=session.get('csrf') if mode=='shared' else None,scope='Local mode retains teaching selectors. Shared mode authenticates configured accounts; use TLS for any non-loopback deployment.')
    @app.post('/api/auth/login')
    def login():
        if mode!='shared':return jsonify(error='LOCAL_MODE'),400
        ip=request.remote_addr or 'unknown';now=time.monotonic();queue=attempts[ip]
        while queue and now-queue[0]>60:queue.popleft()
        if len(queue)>=10:return jsonify(error='LOGIN_RATE_LIMIT'),429
        queue.append(now)
        if len(attempts)>1024:attempts.clear();attempts[ip]=queue
        data=request.get_json(silent=True)
        if not isinstance(data,dict) or set(data)!={'username','password'} or type(data['username']) is not str or type(data['password']) is not str or len(data['password'])>1024:return jsonify(error='INVALID_LOGIN'),400
        u=users.get(data['username']);valid=bool(u and check_password_hash(u['password_hash'],data['password']))
        if not valid:return jsonify(error='INVALID_CREDENTIALS'),401
        session.clear();session.update(username=data['username'],csrf=secrets.token_urlsafe(32));return jsonify(identity=identity(),csrf_token=session['csrf'])
    @app.post('/api/auth/logout')
    def logout():
        if mode=='shared':session.clear()
        return jsonify(status='signed_out')
    @app.get('/api/auth/audit')
    def audit_records():
        if mode=='shared' and not set(g.identity['roles'])&{'auditor','admin'}:return jsonify(error='AUDITOR_ROLE_REQUIRED'),403
        return jsonify(audit.verify())
    @app.after_request
    def log(response):
        if request.path.startswith('/api/') and request.path!='/api/ready':audit.append(dict(request_id=getattr(g,'request_id',None),identity=getattr(g,'identity',None),method=request.method,route=request.url_rule.rule if request.url_rule else 'unmatched',status=response.status_code))
        return response
