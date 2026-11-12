"""Persistent operation leases and fenced completion for local Studio jobs.
Wall-clock leases allow recovery after process death without trusting PID reuse.
"""
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime,timezone
import json
import sqlite3
import threading
import time
from uuid import uuid4

class LeaseLost(RuntimeError):pass

def stamp():return datetime.now(timezone.utc).isoformat()

def start(db,record,kind,seconds):
    token=uuid4().hex;at=time.time()
    db.execute("INSERT INTO studio_operations VALUES(?,?,?,?,?,?)",(record["id"],token,kind,at,at,at+seconds))
    record["operation"]={"token":token,"kind":kind,"started_at":stamp(),"lease_seconds":seconds}
    return token

def finish(db,record,token):
    row=db.execute("SELECT token,expires_at FROM studio_operations WHERE experiment_id=?",(record["id"],)).fetchone()
    if row is None or row["token"]!=token or row["expires_at"]<=time.time():raise LeaseLost("Operation lease expired or was recovered; late results were not accepted")
    db.execute("DELETE FROM studio_operations WHERE experiment_id=? AND token=?",(record["id"],token))
    record.pop("operation",None)

def recover(db):
    recovered=[];at=time.time()
    for row in db.execute("SELECT record_json FROM ai_experiments").fetchall():
        record=json.loads(row["record_json"])
        if record.get("kind") is not None or record.get("state") not in ("generating","running"):continue
        lease=db.execute("SELECT * FROM studio_operations WHERE experiment_id=?",(record["id"],)).fetchone()
        if lease is not None and lease["expires_at"]>at:continue
        kind="generation" if record["state"]=="generating" else "execution"
        reason="Operation heartbeat lease expired" if lease else "Legacy busy record has no operation lease; recovered during V5.1 upgrade"
        interrupted_at=stamp();approval=deepcopy(record.get("approval"))
        pending=record.pop("pending_run",None)
        if pending:
            pending.update(status="interrupted",error="Worker completion was not recorded; execution outcome is unknown",interrupted_at=interrupted_at)
            record["runs"].append(pending)
        record.update(state="interrupted",revision=record["revision"]+1,approval=None,approved_ids=[],interruption={"kind":kind,"reason":reason,"at":interrupted_at})
        record["history"].append({"event":"operation_interrupted","at":interrupted_at,"revision":record["revision"],"kind":kind,"reason":reason,"previous_approval":approval,"previous_operation":record.pop("operation",None)})
        db.execute("DELETE FROM studio_operations WHERE experiment_id=?",(record["id"],))
        db.execute("UPDATE ai_experiments SET record_json=? WHERE id=?",(json.dumps(record,allow_nan=False),record["id"]))
        recovered.append(record["id"])
    return recovered

@contextmanager
def keepalive(path,token,seconds,interval):
    stop=threading.Event()
    def heartbeat():
        while not stop.wait(interval):
            db=None
            try:
                db=sqlite3.connect(path,timeout=1,isolation_level=None);db.execute("BEGIN IMMEDIATE");at=time.time()
                cursor=db.execute("UPDATE studio_operations SET heartbeat_at=?,expires_at=? WHERE token=? AND expires_at>?",(at,at+seconds,token,at));db.commit()
                if cursor.rowcount==0:return
            except sqlite3.Error:
                if db is not None:db.rollback()
                # Failed heartbeats cannot extend ownership; expiry/fencing handles loss.
            finally:
                if db is not None:db.close()
    thread=threading.Thread(target=heartbeat,name="hql-operation-heartbeat",daemon=True);thread.start()
    try:yield
    finally:stop.set();thread.join(timeout=2)
