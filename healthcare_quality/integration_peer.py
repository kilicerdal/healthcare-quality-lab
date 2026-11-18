"""Synthetic external eligibility/payment peer, served only by isolated rehearsals."""
from contextlib import closing
from pathlib import Path
import hashlib,json,sqlite3,threading,time,re
from flask import Flask,request,jsonify

PROFILES=('normal','lost_ack','temporary_unavailable','permanent_timeout','wrong_receipt')

def create_peer(path,token,profile='normal'):
    if profile not in PROFILES:raise ValueError('Unknown trusted peer profile')
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    with closing(sqlite3.connect(path)) as db:
        db.execute('CREATE TABLE IF NOT EXISTS payments(operation_key TEXT PRIMARY KEY, request_hash TEXT NOT NULL, payload TEXT NOT NULL)');db.commit()
    app=Flask('synthetic-payment-peer');counter={};lock=threading.Lock()
    @app.before_request
    def authenticate():
        if request.headers.get('X-Lab-Token')!=token:return jsonify(error='PEER_TOKEN_REQUIRED'),403
    @app.get('/eligibility/<member>')
    def eligibility(member):
        if member not in ('M100','M200','M300','M400'):return jsonify(error='UNKNOWN_MEMBER'),404
        return jsonify(member_id=member,active=member!='M400',version='synthetic-eligibility-1')
    @app.get('/payments/<key>')
    def lookup(key):
        with closing(sqlite3.connect(path)) as db:row=db.execute('SELECT payload FROM payments WHERE operation_key=?',(key,)).fetchone()
        return (jsonify(json.loads(row[0])),200) if row else (jsonify(error='NOT_FOUND'),404)
    @app.post('/payments')
    def pay():
        b=request.get_json(silent=True)
        if not isinstance(b,dict) or set(b)!={'operation_key','claim_id','amount_cents'} or not isinstance(b['operation_key'],str) or not re.fullmatch(r'[A-Za-z0-9_-]{8,80}',b['operation_key']) or not isinstance(b['claim_id'],str) or not re.fullmatch(r'[A-Za-z0-9_-]{3,48}',b['claim_id']) or type(b['amount_cents']) is not int or not 0<=b['amount_cents']<=100000000:return jsonify(error='INVALID_PEER_REQUEST'),400
        key=b['operation_key'];fingerprint=hashlib.sha256(json.dumps(b,sort_keys=True).encode()).hexdigest()
        with lock:counter[key]=counter.get(key,0)+1;attempt=counter[key]
        if profile=='temporary_unavailable' and attempt==1:return jsonify(error='TEMPORARY_UNAVAILABLE'),503
        if profile=='permanent_timeout':time.sleep(.7);return jsonify(error='NOT_COMMITTED'),503
        with closing(sqlite3.connect(path,timeout=5)) as db:
            db.execute('BEGIN IMMEDIATE');old=db.execute('SELECT request_hash,payload FROM payments WHERE operation_key=?',(key,)).fetchone()
            if old:
                if old[0]!=fingerprint:return jsonify(error='IDEMPOTENCY_CONFLICT'),409
                value=json.loads(old[1])
            else:
                value={**b,'status':'paid','receipt_id':'PEER-'+key};db.execute('INSERT INTO payments VALUES(?,?,?)',(key,fingerprint,json.dumps(value)))
            db.commit()
        if profile=='lost_ack' and attempt==1:time.sleep(.7)
        if profile=='wrong_receipt':value={**value,'amount_cents':value['amount_cents']+1}
        return jsonify(value)
    return app
