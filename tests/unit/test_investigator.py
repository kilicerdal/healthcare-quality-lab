import pytest
from healthcare_quality.investigator import analyze,change_impact
from healthcare_quality.ai_runner import run_cases
from healthcare_quality.ai_schema import contract_fingerprint
from tests.support.ai_fixtures import sample_case
pytestmark=[pytest.mark.unit,pytest.mark.ai,pytest.mark.regression]
def experiment(c,**defect):
    run=run_cases([c],**defect);run.update(id='RUN',status='failed' if run['failed'] else 'passed',approved_cases=[c],contract_fingerprint=contract_fingerprint());return dict(id='EXP',runs=[run])
def test_wrong_oracle_does_not_accuse_product():assert analyze(experiment(sample_case(payout=7)),'RUN')['findings'][0]['category']=='test_oracle_error'
def test_seed_failure_is_potential_fault_and_traceable():
    a=analyze(experiment(sample_case(),evaluation_defect='deductible'),'RUN');assert a['findings'][0]['category']=='potential_application_fault';assert a['traceability'][0]['requirement_id']=='HC-007';assert a['findings'][0]['facts']
def test_stale_evidence_abstains():
    e=experiment(sample_case());e['runs'][0]['contract_fingerprint']='old';assert analyze(e,'RUN')['findings'][0]['category']=='stale_evidence'
def test_infrastructure_not_product():
    e=experiment(sample_case());e['runs'][0]['results'][0]['execution_error']='disk unavailable';assert analyze(e,'RUN')['findings'][0]['category']=='infrastructure_error'
def test_pass_and_unknown_run():
    e=experiment(sample_case());assert analyze(e,'RUN')['findings'][0]['category']=='passed'
    with pytest.raises(ValueError):analyze(e,'missing')
def test_invalid_rule_selection_rejected():
    with pytest.raises(ValueError):change_impact(['invented'],[])
