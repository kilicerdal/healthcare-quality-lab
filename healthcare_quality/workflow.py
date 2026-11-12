"""V2 application service: fixtures, ownership, transactional state and evidence."""
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sqlite3
from uuid import uuid4
from healthcare_quality import __version__
from healthcare_quality.catalog import DATA
from healthcare_quality.claims import ContractError, evaluate_claim

MEMBERS=json.loads((DATA/"members.json").read_text())
ACTORS=json.loads((DATA/"actors.json").read_text())
WORKFLOW_RULES=json.loads((DATA/"workflow_rules.json").read_text())
WORKFLOW_HASH=hashlib.sha256(json.dumps({"members":MEMBERS,"actors":ACTORS,"rules":WORKFLOW_RULES},sort_keys=True).encode()).hexdigest()
WORKFLOW_DEFECTS=("none","ownership","duplicate_replay","skip_approval","ledger_amount","history_skip")


class WorkflowError(ValueError):
    def __init__(self,code,message,status=400,rule="WF-002",details=None):
        super().__init__(message)
        self.code,self.status,self.rule,self.details=code,status,rule,details


class ClaimStore:
    def __init__(self,path):
        self.path=Path(path)
        self.path.parent.mkdir(parents=True,exist_ok=True)
        with self.transaction(write=True) as db:
            for statement in (
                "CREATE TABLE IF NOT EXISTS claims (claim_id TEXT PRIMARY KEY, member_id TEXT NOT NULL, status TEXT NOT NULL CHECK(status IN ('submitted','approved','paid')), revision INTEGER NOT NULL CHECK(revision>0), request_json TEXT NOT NULL, evaluation_json TEXT NOT NULL, workflow_hash TEXT NOT NULL, submitted_by TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL)",
                "CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY, claim_id TEXT NOT NULL REFERENCES claims(claim_id), revision INTEGER NOT NULL, actor_id TEXT NOT NULL, from_status TEXT, to_status TEXT NOT NULL, rule_id TEXT NOT NULL, created_at TEXT NOT NULL, UNIQUE(claim_id,revision))",
                "CREATE TABLE IF NOT EXISTS payments (claim_id TEXT PRIMARY KEY REFERENCES claims(claim_id), payment_id TEXT NOT NULL UNIQUE, amount_cents INTEGER NOT NULL CHECK(amount_cents>=0), actor_id TEXT NOT NULL, created_at TEXT NOT NULL)",
                "CREATE INDEX IF NOT EXISTS claims_member ON claims(member_id)"
            ): db.execute(statement)

    @contextmanager
    def transaction(self,*,write=False):
        db=sqlite3.connect(self.path,timeout=5,isolation_level=None)
        db.row_factory=sqlite3.Row
        try:
            db.execute("PRAGMA foreign_keys=ON")
            db.execute("BEGIN IMMEDIATE" if write else "BEGIN")
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()


class WorkflowService:
    def __init__(self,store,*,defect="none"):
        if defect not in WORKFLOW_DEFECTS:raise ValueError("Unknown workflow defect")
        self.store,self.defect=store,defect

    def actor(self,actor_id):
        actor=next((a for a in ACTORS if a["id"]==actor_id),None)
        if actor is None:raise WorkflowError("FORBIDDEN","Select a known demo actor",403,"WF-001")
        return actor

    def _visible(self,actor,claim):
        if actor["role"]=="customer" and actor["member_id"]!=claim["member_id"] and self.defect!="ownership":
            raise WorkflowError("FORBIDDEN","Customers can access only their fixture member's claims",403,"WF-001")

    @staticmethod
    def _claim(db,claim_id):
        row=db.execute("SELECT * FROM claims WHERE claim_id=?",(claim_id,)).fetchone()
        if row is None:raise WorkflowError("NOT_FOUND","Claim not found",404,"WF-005")
        claim=dict(row)
        claim["request"]=json.loads(claim.pop("request_json"))
        claim["evaluation"]=json.loads(claim.pop("evaluation_json"))
        return claim

    @classmethod
    def _evidence(cls,db,claim_id):
        claim=cls._claim(db,claim_id)
        events=[dict(r) for r in db.execute("SELECT revision,actor_id,from_status,to_status,rule_id,created_at FROM events WHERE claim_id=? ORDER BY revision",(claim_id,))]
        payment=db.execute("SELECT * FROM payments WHERE claim_id=?",(claim_id,)).fetchone()
        return {"version":__version__,"synthetic":True,"workflow_contract_hash":claim["workflow_hash"],"claim":claim,"events":events,"payment":dict(payment) if payment else None}

    def _event(self,db,claim_id,revision,actor_id,old,new,rule,now):
        if self.defect=="history_skip" and revision>1:return
        db.execute("INSERT INTO events(claim_id,revision,actor_id,from_status,to_status,rule_id,created_at) VALUES(?,?,?,?,?,?,?)",(claim_id,revision,actor_id,old,new,rule,now))

    def submit(self,actor_id,payload):
        actor=self.actor(actor_id)
        if actor["role"]!="customer":raise WorkflowError("FORBIDDEN","Only customers can submit",403,"WF-001")
        required={"claim_id","member_id","service","amount_cents"}
        optional={"in_network","authorized","formulary"}
        if not isinstance(payload,dict) or not required<=payload.keys() or payload.keys()-required-optional:
            raise WorkflowError("INVALID_REQUEST","Provide claim_id, member_id, service, amount_cents and optional coverage flags only")
        claim_id=payload["claim_id"]
        if not isinstance(claim_id,str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{2,47}",claim_id):
            raise WorkflowError("INVALID_REQUEST","claim_id must be 3–48 ASCII letters, digits, hyphens or underscores")
        if actor["member_id"]!=payload["member_id"] and self.defect!="ownership":
            raise WorkflowError("FORBIDDEN","Customers may submit only for their fixture member",403,"WF-001")
        member=next((m for m in MEMBERS if m["id"]==payload["member_id"]),None)
        if member is None:raise WorkflowError("INVALID_REQUEST","Unknown fixture member")
        evaluation_input={"plan_id":member["plan_id"],"active":member["active"],"service":payload["service"],"amount_cents":payload["amount_cents"],**{k:payload[k] for k in optional if k in payload}}
        try:evaluation=evaluate_claim(evaluation_input)
        except ContractError as error:raise WorkflowError("INVALID_REQUEST",str(error),400,"HC-001") from error
        now=datetime.now(timezone.utc).isoformat()
        with self.store.transaction(write=True) as db:
            if db.execute("SELECT 1 FROM claims WHERE claim_id=?",(claim_id,)).fetchone():
                if self.defect=="duplicate_replay":return self._evidence(db,claim_id)
                raise WorkflowError("DUPLICATE_CLAIM","Claim ID already exists",409,"WF-002")
            if evaluation["decision"]!="approved":
                raise WorkflowError("COVERAGE_DENIED",evaluation["reason"],422,"WF-002",{"evaluation":evaluation})
            normalized={"claim_id":claim_id,"member_id":member["id"],**evaluation["request"]}
            db.execute("INSERT INTO claims(claim_id,member_id,status,revision,request_json,evaluation_json,workflow_hash,submitted_by,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?)",(claim_id,member["id"],"submitted",1,json.dumps(normalized,sort_keys=True),json.dumps(evaluation,sort_keys=True),WORKFLOW_HASH,actor_id,now,now))
            self._event(db,claim_id,1,actor_id,None,"submitted","WF-002",now)
            return self._evidence(db,claim_id)

    def transition(self,actor_id,claim_id,payload):
        actor=self.actor(actor_id)
        if not isinstance(payload,dict) or set(payload)!={"target"} or payload["target"] not in ("approved","paid"):
            raise WorkflowError("INVALID_REQUEST","target must be approved or paid",400,"WF-003")
        target=payload["target"]
        required_role="adjuster" if target=="approved" else "finance"
        if actor["role"]!=required_role:raise WorkflowError("FORBIDDEN",f"Only {required_role} actors can enter {target}",403,"WF-001")
        with self.store.transaction(write=True) as db:
            claim=self._claim(db,claim_id)
            allowed=(claim["status"],target) in (("submitted","approved"),("approved","paid"))
            if self.defect=="skip_approval" and target=="paid" and claim["status"]=="submitted":allowed=True
            if not allowed:raise WorkflowError("INVALID_TRANSITION",f"Cannot move {claim['status']} to {target}",409,"WF-003")
            revision=claim["revision"]+1;now=datetime.now(timezone.utc).isoformat()
            db.execute("UPDATE claims SET status=?,revision=?,updated_at=? WHERE claim_id=?",(target,revision,now,claim_id))
            if target=="paid":
                amount=claim["evaluation"]["payout_cents"]*(2 if self.defect=="ledger_amount" else 1)
                db.execute("INSERT INTO payments VALUES(?,?,?,?,?)",(claim_id,"SIM-"+uuid4().hex,amount,actor_id,now))
            self._event(db,claim_id,revision,actor_id,claim["status"],target,"WF-004" if target=="paid" else "WF-003",now)
            return self._evidence(db,claim_id)

    def get(self,actor_id,claim_id):
        actor=self.actor(actor_id)
        with self.store.transaction() as db:
            claim=self._claim(db,claim_id);self._visible(actor,claim)
            return self._evidence(db,claim_id)

    def list(self,actor_id):
        actor=self.actor(actor_id)
        with self.store.transaction() as db:
            sql="SELECT claim_id,member_id,status,revision,created_at,updated_at FROM claims"
            args=()
            if actor["role"]=="customer":sql+=" WHERE member_id=?";args=(actor["member_id"],)
            rows=db.execute(sql+" ORDER BY created_at DESC,claim_id LIMIT 100",args).fetchall()
            return {"claims":[dict(row) for row in rows],"limit":100,"synthetic":True}
