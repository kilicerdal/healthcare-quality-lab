from copy import deepcopy
import pytest
from healthcare_quality.effectiveness import variants,properties,lifecycle_properties,compare,suite_run,reduce_prefix
from tests.unit.test_advanced_cases import CASES
pytestmark=[pytest.mark.unit,pytest.mark.regression]

def test_seeded_properties_reproducible_and_money_conserved():
    a=properties(611,20);assert a['passed'] and a['checks_passed']==100 and a==properties(611,20)

def test_real_payment_replay_and_reversal_relations():assert lifecycle_properties()['passed']

def test_trusted_mutants_change_production_behavior_and_restore_it():
    mutants=variants();assert len(mutants)>=20 and len({x['id'] for x in mutants})==len(mutants);assert any(not suite_run(CASES[:1],v)['passed'] for v in mutants);assert suite_run(CASES[:1])['passed']

def test_bad_expected_values_cannot_receive_mutation_credit():
    c=deepcopy(CASES[0]);c['steps'][0]['expect']['payout_cents']+=1;r=compare({'wrong':[c]},examples=2);assert not r['suites'][0]['scored'] and not r['suites'][0]['trials']

def test_prefix_reduction_retains_original_expectations_and_fault():
    c=deepcopy(CASES[0]);v=next(v for v in variants() if not suite_run([c],v)['passed']);r=reduce_prefix(c,v['id']);assert 1<=r['reduced_steps']<=r['original_steps'];assert c==CASES[0] and r['case']['steps']==c['steps'][:r['reduced_steps']];assert not suite_run([r['case']],v)['passed']

@pytest.mark.parametrize('seed,count',[(True,1),(-1,1),(1,0),(1,201)])
def test_properties_reject_unbounded_inputs(seed,count):
    with pytest.raises(ValueError):properties(seed,count)

def test_two_authored_boundary_controls_close_named_survivors():
    import json
    from pathlib import Path
    gaps=json.loads((Path(__file__).resolve().parents[2]/'healthcare_quality/data/advanced_cases_v611.json').read_text())['cases'];selected=[v for v in variants() if v['id'] in ('AST-218','AST-324')];assert len(selected)==2 and all(not suite_run(gaps,v)['passed'] for v in selected);assert suite_run(gaps)['passed']
