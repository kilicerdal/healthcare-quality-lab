from copy import deepcopy
import pytest
from healthcare_quality.traceability import graph,impact,requirements
from healthcare_quality.advanced_lab import contract_hash
from healthcare_quality.ai_schema import digest
from healthcare_quality.advanced_runner import run
from tools.fingerprints import source_hash
from tests.unit.test_advanced_cases import CASES
pytestmark=[pytest.mark.unit,pytest.mark.regression]

def proposal(approved=False):
    c=CASES[:1];p=dict(id='P1',cases=deepcopy(c),source_hash=source_hash(),contract_hash=contract_hash(),approval=None,runs=[])
    if approved:p['approval']=dict(cases_hash=digest(c),source_hash=source_hash(),contract_hash=contract_hash());p['runs']=[dict(id='R1',**run(c))]
    return p

def test_declaring_all_rules_does_not_invent_appeal_coverage():
    g=graph([proposal()]);r=next(x for x in g['coverage'] if x['rule_id']=='BN-007');assert r['scenario_count']==0 and r['current_passing_scenarios']==0;assert g['assertions'] and g['edges']

def test_passing_execution_requires_current_review_snapshot():
    p=proposal(True);g=graph([p]);assert next(x for x in g['coverage'] if x['rule_id']=='BN-004')['current_passing_scenarios']==1;p['approval']['source_hash']='stale';assert all(x['current_passing_scenarios']==0 for x in graph([p])['coverage'])

def test_changed_case_cannot_inherit_passing_coverage():
    p=proposal(True);p['cases'][0]['steps'][0]['expect']['payout_cents']+=1;assert all(x['current_passing_scenarios']==0 for x in graph([p])['coverage'])

def test_what_if_impact_preserves_original_contract_and_proposals():
    p=proposal(True);before=deepcopy(p);g=graph([p]);out=impact(g,[dict(id='BN-004',contract='A proposed synthetic cost sharing rule changes')]);assert len(out['affected_scenarios'])==1 and not out['applied'];assert p==before;assert requirements()==g['requirements']

def test_unchanged_contract_has_no_spurious_impact():
    g=graph([proposal()]);r=g['requirements'][3];assert impact(g,[dict(id=r['id'],contract=r['contract'])])['affected_scenarios']==[]

@pytest.mark.parametrize('changes',[[],[{'id':'unknown','contract':'bad rule'}],[{'id':'BN-004','contract':True}],[{'id':'BN-004','contract':'valid rule','code':'run'}]])
def test_invalid_impact_input(changes):
    with pytest.raises(ValueError):impact(graph([]),changes)

def test_invalid_proposal_does_not_crash_graph():assert graph([{'id':'bad','cases':[]}])['invalid_proposals']==['bad']
