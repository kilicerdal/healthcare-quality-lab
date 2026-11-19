"""Snapshot-bound ownership and review decisions, never automatic approval."""
from pathlib import Path
from datetime import datetime,timezone
from contextlib import contextmanager
import sqlite3,json
from healthcare_quality.ai_schema import digest
from healthcare_quality.advanced_lab import contract_hash
from healthcare_quality.ai_studio import StudioError
from tools.fingerprints import source_hash

class TeamWorkflow:
 def __init__(self,path):
  self.path=Path(path);self.path.parent.mkdir(parents=True,exist_ok=True)
  with self.db() as db:db.execute('CREATE TABLE IF NOT EXISTS decisions(seq INTEGER PRIMARY KEY, proposal TEXT NOT NULL, snapshot TEXT NOT NULL, owner TEXT NOT NULL, decision TEXT NOT NULL, note TEXT NOT NULL, actor TEXT NOT NULL, at TEXT NOT NULL)')
 @contextmanager
 def db(self):
  with sqlite3.connect(self.path,timeout=5) as db:
   db.execute('BEGIN IMMEDIATE');yield db
 def snapshot(self,r):return digest(dict(cases=r['cases'],revision=r['revision'],source=r['source_hash'],contract=r['contract_hash']))
 def decide(self,r,owner,decision,note,actor):
  if type(owner) is not str or not 2<=len(owner)<=80 or decision not in ('assigned','changes_requested','ready_for_review') or type(note) is not str or not 5<=len(note)<=1000:raise StudioError('INVALID_DECISION','Provide bounded owner, decision and inspection note')
  if r['source_hash']!=source_hash() or r['contract_hash']!=contract_hash():raise StudioError('STALE_PROPOSAL','Create a current proposal before routing it',409)
  if decision=='ready_for_review' and not r['assessment']['review_ready']:raise StudioError('REVIEW_BLOCKED','Independent checks must pass before review routing',409)
  with self.db() as db:db.execute('INSERT INTO decisions(proposal,snapshot,owner,decision,note,actor,at) VALUES(?,?,?,?,?,?,?)',(r['id'],self.snapshot(r),owner,decision,note,actor,datetime.now(timezone.utc).isoformat()))
  return self.history(r)
 def history(self,r):
  with self.db() as db:
   db.row_factory=sqlite3.Row;rows=[dict(x) for x in db.execute('SELECT * FROM decisions WHERE proposal=? ORDER BY seq',(r['id'],))]
  snap=self.snapshot(r)
  return dict(proposal=r['id'],snapshot=snap,events=rows,current=[x for x in rows if x['snapshot']==snap],approval=r.get('approval'),scope='Routing is not approval. Actual review remains a separate identity-bound AdvancedLab action.')
 def queue(self,records):
  rows=[];fingerprint=source_hash();contract=contract_hash()
  for r in records:
   h=self.history(r);events=h['current'];latest=events[-1] if events else {}
   rows.append(dict(id=r['id'],state=r['state'],owner=latest.get('owner'),decision=latest.get('decision','unassigned'),eligible=r['assessment']['review_ready'],stale=r['source_hash']!=fingerprint or r['contract_hash']!=contract,approved=bool(r.get('approval')),runs=len(r['runs'])))
  return rows
