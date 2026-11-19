import json,zipfile
from copy import deepcopy
import pytest
from healthcare_quality.advanced_lab import AdvancedLab
from healthcare_quality.team_workflow import TeamWorkflow
from healthcare_quality.test_design import compile_plan
from healthcare_quality.coverage_packs import plan_for
from healthcare_quality.assistant_v8 import explain
from healthcare_quality.ai_studio import StudioError
from tools.evidence_bundle import build,verify,compare,ROOT
pytestmark=[pytest.mark.unit,pytest.mark.regression]

def test_team_events_are_snapshot_bound_and_survive_restart(tmp_path):
 import threading
 lab=AdvancedLab(tmp_path/'advanced.sqlite',object(),threading.Lock());r=lab.propose([compile_plan(plan_for('commercial_ppo'))]);team=TeamWorkflow(tmp_path/'team.sqlite')
 team.decide(r,'QE','assigned','Inspect all observations','engineer')
 assert len(TeamWorkflow(team.path).history(r)['current'])==1
 changed=deepcopy(r);changed['revision']+=1;assert not team.history(changed)['current'];assert len(team.history(changed)['events'])==1
 assert lab.get(r['id'])['approval'] is None
 changed['source_hash']='stale'
 with pytest.raises(StudioError):team.decide(changed,'QE','assigned','Inspect all observations','engineer')
 assert explain(r)['facts'] and not explain(r)['can_execute']

def test_bundle_detects_tampering_and_compares_explicit_members(tmp_path):
 path=ROOT/'docs/V7.0_REPORT.md';old=tmp_path/'old.zip';new=tmp_path/'new.zip'
 build([path],old);build([path,ROOT/'docs/V6.12_REPORT.md'],new);assert verify(old)['files'];assert compare(old,new)['added']==['docs/V6.12_REPORT.md']
 with pytest.raises(ValueError):build([path],old)
 with zipfile.ZipFile(old) as z:items={n:z.read(n) for n in z.namelist()}
 items['docs/V7.0_REPORT.md']=b'tampered'
 bad=tmp_path/'bad.zip'
 with zipfile.ZipFile(bad,'w') as z:
  for n,b in items.items():z.writestr(n,b)
 with pytest.raises(ValueError):verify(bad)
 with pytest.raises(ValueError):build([ROOT/'.local/secret.json'],tmp_path/'private.zip')


def test_bundle_refuses_symlink_evidence(tmp_path):
 link=tmp_path/'report.md';link.symlink_to(ROOT/'docs/V7.0_REPORT.md')
 with pytest.raises(ValueError):build([link],tmp_path/'symlink.zip')
