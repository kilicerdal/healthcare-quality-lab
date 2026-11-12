"""Literal answers and independence checks, not application-derived expectations."""
import ast
from copy import deepcopy
import pytest
from healthcare_quality import reference
from healthcare_quality.ai_studio import StudioService,ExperimentStore,StudioError
from tests.support.ai_fixtures import sample_case,FixtureProvider,generation_request,review_request
pytestmark=[pytest.mark.unit,pytest.mark.ai,pytest.mark.regression]

@pytest.mark.parametrize('amount,payout',[(1,0),(7600,0),(9999,0),(10000,0),(10001,1),(100000,90000),(209999,199999),(210000,200000),(210001,200000),(278900,200000),(100000000,200000)])
def test_literal_payout_boundaries(amount,payout):
    assert reference.check(sample_case(amount=amount,payout=payout))['status']=='matched'

@pytest.mark.parametrize('amount',[True,0,-1,1.5,'10000',100000001,None])
def test_invalid_money_never_produces_financial_result(amount):
    result,_=reference.evaluate({'plan_id':'medicare_b','service':'medical','amount_cents':amount})
    assert result=={'status':400,'error':'INVALID_REQUEST'}

def test_independent_imports_and_poisoned_application(monkeypatch):
    tree=ast.parse(reference.ROOT.joinpath('reference.py').read_text())
    names={n.module.split('.')[0] for n in ast.walk(tree) if isinstance(n,ast.ImportFrom)}|{a.name.split('.')[0] for n in ast.walk(tree) if isinstance(n,ast.Import) for a in n.names}
    assert names <= {'pathlib','copy','hashlib','json','re'}
    def forbidden(*a,**k):raise AssertionError('Application called by reference')
    monkeypatch.setattr('healthcare_quality.claims.evaluate_claim',forbidden)
    monkeypatch.setattr('healthcare_quality.ai_runner.run_cases',forbidden)
    assert reference.check(sample_case())['status']=='matched'

def test_workflow_state_is_derived_from_inputs_not_guessed_expectations():
    model=reference.Model()
    steps=[{'action':'submit','actor':'customer-m100','data':{'claim_id':'REF-100','member_id':'M100','service':'medical','amount_cents':100000}}, {'action':'transition','actor':'adjuster-demo','data':{'claim_id':'REF-100','target':'approved'}}, {'action':'transition','actor':'finance-demo','data':{'claim_id':'REF-100','target':'paid'}}, {'action':'read','actor':'customer-m100','data':{'claim_id':'REF-100'}}]
    expected=[{'status':201,'claim_status':'submitted','revision':1,'event_count':1,'payout_cents':90000,'payment_cents':None},{'status':200,'claim_status':'approved','revision':2,'event_count':2,'payout_cents':90000,'payment_cents':None},{'status':200,'claim_status':'paid','revision':3,'event_count':3,'payout_cents':90000,'payment_cents':90000},{'status':200,'claim_status':'paid','revision':3,'event_count':3,'payout_cents':90000,'payment_cents':90000}]
    for step,answer in zip(steps,expected):assert model.step(step)[0]==answer
    case=sample_case();case['steps']=[{**step,'expect':answer} for step,answer in zip(steps,expected)]
    case['steps'][0]['expect']['payout_cents']=0
    checked=reference.check(case)
    assert len(checked['mismatches'])==1 and checked['steps'][2]['expected']['payment_cents']==90000

def service(tmp_path,case=None):
    return StudioService(ExperimentStore(tmp_path/'studio.sqlite'),FixtureProvider({'cases':[case or sample_case(payout=1)]}))
def correction_body(record):return {'expected_revision':record['revision'],'reviewer_label':'Reference reviewer','review_note':'Explicit single correction with frozen scenario.'}

def test_correction_preserves_parent_and_needs_fresh_approval(tmp_path):
    studio=service(tmp_path);parent=studio.generate(generation_request());raw=deepcopy(parent['raw_generation'])
    studio.provider.output={'cases':[sample_case()]}
    child=studio.correct(parent['id'],correction_body(parent))
    saved=studio.store.get(parent['id'])
    assert saved['raw_generation']==raw and saved['proposals']==parent['proposals']
    assert child['correction_of']==parent['id'] and child['approval'] is None and not child['runs']
    assert child['proposals'][0]['reference']['status']=='matched'
    assert len(studio.provider.calls)==2
    with pytest.raises(StudioError):studio.execute(child['id'],{'expected_revision':1})
    approved=studio.review(child['id'],review_request(child))
    assert studio.execute(child['id'],{'expected_revision':approved['revision']})['status']=='passed'

@pytest.mark.parametrize('field',['amount','actor','title','order'])
def test_correction_rejects_scenario_drift(tmp_path,field):
    studio=service(tmp_path);parent=studio.generate(generation_request());changed=sample_case()
    if field=='amount':changed['steps'][0]['data']['amount_cents']=100001
    elif field=='actor':changed['steps'][0]['actor']='auditor-demo'
    elif field=='title':changed['title']='Changed scenario'
    else:changed['steps'].append(deepcopy(changed['steps'][0]))
    studio.provider.output={'cases':[changed]};child=studio.correct(parent['id'],correction_body(parent))
    assert child['state']=='generation_failed' and child['raw_generation'] and not child['proposals']
    assert 'only expect' in child['generation_error']

def test_still_wrong_correction_remains_blocked_without_loop(tmp_path):
    studio=service(tmp_path);parent=studio.generate(generation_request());child=studio.correct(parent['id'],correction_body(parent))
    assert child['state']=='proposed' and not child['proposals'][0]['review_ready']
    with pytest.raises(StudioError) as error:studio.review(child['id'],review_request(child))
    assert error.value.code=='REFERENCE_MISMATCH' and len(studio.provider.calls)==2

def test_reference_change_invalidates_execution_and_export(tmp_path,monkeypatch):
    studio=service(tmp_path,sample_case());record=studio.generate(generation_request());record=studio.review(record['id'],review_request(record))
    monkeypatch.setattr(reference,'fingerprint',lambda:'new-reference')
    for action in [lambda:studio.execute(record['id'],{'expected_revision':record['revision']}),lambda:studio.export_pytest(record['id'])]:
        with pytest.raises(StudioError) as error:action()
        assert error.value.code=='STALE_REFERENCE'

def test_stale_correction_does_not_call_provider(tmp_path):
    studio=service(tmp_path);parent=studio.generate(generation_request());body=correction_body(parent);body['expected_revision']=0
    with pytest.raises(StudioError):studio.correct(parent['id'],body)
    assert len(studio.provider.calls)==1

@pytest.mark.parametrize('plan,service,flags,reason',[('medicare_b','medical',{'active':False},'INACTIVE_POLICY'),('medicare_b','dental',{},'SERVICE_NOT_COVERED'),('commercial_hmo','medical',{'in_network':False},'OUT_OF_NETWORK'),('medicare_a','skilled_nursing',{'authorized':False},'AUTH_REQUIRED'),('medicare_d','prescription',{'formulary':False},'NON_FORMULARY')])
def test_literal_denial_rules(plan,service,flags,reason):
    result,_=reference.evaluate({'plan_id':plan,'service':service,'amount_cents':100000,**flags})
    assert result=={'status':200,'decision':'denied','reason':reason,'payout_cents':0}

def test_denial_precedence_and_duplicate_rejection_leave_state_unchanged():
    result,_=reference.evaluate({'plan_id':'commercial_hmo','service':'dental','amount_cents':100000,'active':False,'in_network':False})
    assert result['reason']=='INACTIVE_POLICY'
    model=reference.Model();step={'action':'submit','actor':'customer-m100','data':{'claim_id':'DUP-123','member_id':'M100','service':'medical','amount_cents':100000}}
    before=model.step(step)[0]
    assert model.step(step)[0]=={'status':409,'error':'DUPLICATE_CLAIM'}
    assert model.step({'action':'read','actor':'customer-m100','data':{'claim_id':'DUP-123'}})[0]=={**before,'status':200}

def test_correction_failure_is_saved_not_silently_repaired(tmp_path):
    from healthcare_quality.ollama_provider import ProviderError
    studio=service(tmp_path);parent=studio.generate(generation_request());studio.provider.error=ProviderError('Offline fixture outage')
    child=studio.correct(parent['id'],correction_body(parent))
    assert child['state']=='generation_failed' and child['correction_snapshot']['cases']==[p['case'] for p in parent['proposals']]
    assert not child['proposals'] and not child['runs'] and child['approval'] is None

def test_exported_wrapper_checks_reference_before_runner(tmp_path):
    studio=service(tmp_path,sample_case());record=studio.generate(generation_request());studio.review(record['id'],review_request(record))
    wrapper=studio.export_pytest(record['id'])
    assert 'reference.fingerprint()' in wrapper and 'reference.check(case)' in wrapper
    compile(wrapper,'exported.py','exec')


def test_reference_disagrees_with_all_seven_seeded_evaluator_defects():
    import json
    from healthcare_quality.claims import evaluate_claim
    from tools.benchmark import MUTATIONS,ROOT
    golden=json.loads((ROOT/'tests/data/golden.json').read_text())
    for defect,id in MUTATIONS.items():
        authored=next(c for c in golden if c['id']==id)
        correct,_=reference.evaluate(authored['request'])
        broken=evaluate_claim(authored['request'],defect=defect)
        assert any(correct[k]!=broken[k] for k in ('decision','reason','payout_cents'))

def test_interrupted_correction_retry_retains_frozen_shape(tmp_path):
    from tests.unit.test_operation_recovery import BlockingProvider,expire,raw_record
    from concurrent.futures import ThreadPoolExecutor
    studio=service(tmp_path);parent=studio.generate(generation_request())
    blocker=BlockingProvider();studio.provider=blocker
    with ThreadPoolExecutor(max_workers=1) as pool:
        future=pool.submit(studio.correct,parent['id'],correction_body(parent))
        assert blocker.entered.wait(3)
        child=raw_record(studio);expire(studio,child['id']);studio.recover_interrupted();blocker.release.set()
        with pytest.raises(StudioError):future.result(timeout=5)
    interrupted=studio.store.get(child['id']);assert interrupted['state']=='interrupted'
    changed=sample_case();changed['steps'][0]['data']['amount_cents']=100001
    studio.provider=FixtureProvider({'cases':[changed]})
    retried=studio.retry(interrupted['id'],correction_body(interrupted))
    assert retried['state']=='generation_failed' and retried['correction_of']==interrupted['id']
    assert retried['correction_snapshot']['cases']==child['correction_snapshot']['cases']
