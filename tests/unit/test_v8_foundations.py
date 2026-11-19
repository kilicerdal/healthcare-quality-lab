from copy import deepcopy
import pytest
from healthcare_quality.coverage_packs import packs,journeys,plan_for
from healthcare_quality.test_design import compile_plan
from healthcare_quality.scenario_quality import inspect,add_readbacks
from healthcare_quality.evaluation_v8 import cohort,matrix
from healthcare_quality.advanced_runner import run
from healthcare_quality.advanced_schema import semantic_key
from tools.doctor import diagnose
pytestmark=[pytest.mark.unit,pytest.mark.regression]

def test_runtime_diagnostics_are_read_only_and_model_optional():
 r=diagnose();assert r['ready'];assert 'optional_ollama' not in r

def test_scenario_quality_blocks_missing_readback_and_duplicates():
 p=plan_for('commercial_ppo');assert inspect(p)['ready']
 p['case']['steps'].pop();r=inspect(p);assert not r['ready'];assert r['issues'][0]['code']=='MISSING_READBACK'
 transformed=add_readbacks(p);assert transformed['model_authored'] is False;assert inspect(transformed['plan'])['ready']
 r=inspect(transformed['plan'],[semantic_key(p['case'])]);assert r['ready'] # transformed sequence differs
 p=transformed['plan'];assert not inspect(p,[semantic_key(p['case'])])['ready']

def test_scenario_quality_rejects_model_expected_values_and_invalid_input():
 p=plan_for('commercial_ppo');p['case']['steps'][0]['expect']={'payout_cents':1}
 assert not inspect(p)['valid'];assert not inspect(None)['valid']

@pytest.mark.parametrize('pack',packs(),ids=lambda p:p['id'])
def test_each_pack_has_independently_checked_boundaries(pack):
 assert not pack['real_world_policy'];assert len(pack['plans'])>=3
 for p in pack['plans']:
  assert inspect(p)['ready'];c=compile_plan(p);assert run([c])['passed']==1
  if p['case']['title'].endswith('deductible'):assert c['steps'][0]['expect']['payout_cents']==0
  if p['case']['title'].endswith(('noncovered','network','authorization','formulary')):assert c['steps'][0]['expect']['noncovered_cents']==97003

@pytest.mark.parametrize('plan',journeys(),ids=lambda p:p['case']['title'])
def test_lifecycle_journeys_have_complete_matching_observations(plan):
 assert inspect(plan)['ready'];c=compile_plan(plan);assert run([c])['passed']==1
 assert all('event_count' in s['expect'] and 'ledger_cents' in s['expect'] for s in c['steps'])

def test_evaluation_cohort_has_disjoint_families_and_fixed_budget():
 c=cohort();assert len(c['tasks'])==31;assert len({t['id'] for t in c['tasks']})==31
 dev={t['family'] for t in c['tasks'] if t['split']=='development'};reserved={t['family'] for t in c['tasks'] if t['split']!='development'};assert not dev&reserved
 for t in c['tasks']:compile_plan(t['plan'])
 r=matrix(['EV8-01','EV8-02'],['qwen2.5-coder:3b'],['focused-v68'],2);assert r['request_budget']==4 and r['correction_budget']==0
 with pytest.raises(ValueError):matrix([t['id'] for t in c['tasks']],['qwen2.5-coder:3b'],['focused-v68'])
 with pytest.raises(ValueError):matrix(['unknown'],['qwen2.5-coder:3b'],['focused-v68'])


@pytest.mark.parametrize('plan,index,expected',[
 (plan_for('medicare_b'),-1,dict(payout_cents=68802,member_cents=28201,ledger_cents=68802,ledger_count=1,event_count=2,revision=2)),
 (journeys()[0],-1,dict(payout_cents=101570,member_cents=30000,ledger_cents=101570)),
 (journeys()[1],-1,dict(ledger_cents=0,ledger_count=4,event_count=4,individual_deductible=0,individual_oop=0)),
 (journeys()[2],-1,dict(payout_cents=68802,ledger_count=1,event_count=4)),
 (journeys()[4],-1,dict(payout_cents=49865,member_cents=23467,other_payer_cents=23671))])
def test_hand_calculated_literal_anchors_match_actual_application(plan,index,expected):
 c=compile_plan(plan);r=run([c]);observed=r['results'][0]['steps'][index]['observed']
 assert {k:observed[k] for k in expected}==expected
 assert {k:c['steps'][index]['expect'][k] for k in expected}==expected
