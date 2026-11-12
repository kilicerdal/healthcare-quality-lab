from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import pytest
from healthcare_quality import reference
from healthcare_quality.ai_studio import StudioService,ExperimentStore,StudioError,correction_prompt
from healthcare_quality.ollama_provider import ProviderError
from tests.support.ai_fixtures import FixtureProvider,sample_case,generation_request,review_request
from tests.unit.test_reference import correction_body
pytestmark=[pytest.mark.unit,pytest.mark.ai,pytest.mark.regression]

def make(tmp_path,case=None):return StudioService(ExperimentStore(tmp_path/'ai.sqlite'),FixtureProvider({'cases':[case or sample_case(payout=1)]}))
def fallback_body(preview):
    return {k:preview[k] for k in ('expected_revision','reference_fingerprint','preview_hash')}|{'reference_confirmed':True,'reviewer_label':'Fixture reference reviewer','review_note':'Inspected exact synthetic reference replacements; not an AI correction.'}

@pytest.mark.parametrize('amount,wrong,right',[(10001,9001,1),(286450,186450,200000),(10000,10000,0),(9999,9999,0),(10002,9002,2),(209999,200000,199999),(210001,200001,200000)])
def test_literal_known_failures_and_nearby_boundaries_repaired_without_model(tmp_path,amount,wrong,right):
    studio=make(tmp_path,sample_case(amount=amount,payout=wrong));parent=studio.generate(generation_request());raw=deepcopy(parent['raw_generation'])
    preview=studio.reference_preview(parent['id']);assert preview['changes'][0]['after']['payout_cents']==right
    assert studio.store.get(parent['id'])==parent  # Preview is read-only.
    child=studio.apply_reference(parent['id'],fallback_body(preview))
    assert len(studio.provider.calls)==1 and child['raw_generation'] is None
    assert child['expectation_origin']=='reviewer_confirmed_reference' and child['reference_assisted_of']==parent['id']
    assert child['approval'] is None and not child['runs'] and child['proposals'][0]['review_ready']
    assert reference.shape([child['proposals'][0]['case']])==reference.shape([parent['proposals'][0]['case']])
    saved=studio.store.get(parent['id']);assert saved['raw_generation']==raw and saved['proposals']==parent['proposals']
    with pytest.raises(StudioError):studio.execute(child['id'],{'expected_revision':1})
    reviewed=studio.review(child['id'],review_request(child));assert studio.execute(child['id'],{'expected_revision':reviewed['revision']})['status']=='passed'

def test_two_attempt_budget_survives_restart_and_blocks_third_on_every_branch(tmp_path):
    studio=make(tmp_path);parent=studio.generate(generation_request());one=studio.correct(parent['id'],correction_body(parent));two=studio.correct(one['id'],correction_body(one))
    restarted=StudioService(studio.store,studio.provider)
    for record in [parent,one,two]:
        latest=restarted.view(record['id']);assert latest['correction_budget']['used']==2
        with pytest.raises(StudioError) as error:restarted.correct(latest['id'],correction_body(latest))
        assert error.value.code=='CORRECTION_LIMIT'
    assert len(studio.provider.calls)==3

def test_failed_provider_attempt_consumes_budget_and_reference_fallback_still_works(tmp_path):
    studio=make(tmp_path);parent=studio.generate(generation_request());studio.provider.error=ProviderError('Fixture outage')
    one=studio.correct(parent['id'],correction_body(parent));assert one['state']=='generation_failed'
    # Failed child has no proposals, but its frozen input snapshot remains usable.
    preview=studio.reference_preview(one['id']);child=studio.apply_reference(one['id'],fallback_body(preview))
    assert studio.view(child['id'])['correction_budget']['used']==1
    assert child['proposals'][0]['reference']['status']=='matched'

def test_sibling_corrections_share_root_budget(tmp_path):
    studio=make(tmp_path);parent=studio.generate(generation_request());studio.correct(parent['id'],correction_body(parent))
    parent=studio.view(parent['id']);second=studio.correct(parent['id'],correction_body(parent))
    assert second['correction_attempt']==2
    with pytest.raises(StudioError) as error:studio.correct(second['id'],correction_body(second))
    assert error.value.code=='CORRECTION_LIMIT'

def test_cross_service_race_reserves_only_last_available_attempt(tmp_path):
    studio=make(tmp_path);parent=studio.generate(generation_request());one=studio.correct(parent['id'],correction_body(parent))
    a=StudioService(studio.store,FixtureProvider({'cases':[sample_case(payout=1)]}));b=StudioService(studio.store,FixtureProvider({'cases':[sample_case(payout=1)]}))
    root=studio.view(parent['id'])
    def attempt(service,record):
        try:return service.correct(record['id'],correction_body(record))['id']
        except StudioError as error:return error.code
    with ThreadPoolExecutor(max_workers=2) as pool:
        first=pool.submit(attempt,a,root);second=pool.submit(attempt,b,one);results=[first.result(),second.result()]
    assert results.count('CORRECTION_LIMIT')==1
    assert len(a.provider.calls)+len(b.provider.calls)==1

@pytest.mark.parametrize('field,value,code',[('reference_confirmed',False,'REFERENCE_CONFIRMATION_REQUIRED'),('reference_confirmed','true','REFERENCE_CONFIRMATION_REQUIRED'),('preview_hash','changed','STALE_REFERENCE_PREVIEW'),('reference_fingerprint','changed','STALE_REFERENCE_PREVIEW'),('expected_revision',0,'STALE_REVISION')])
def test_reference_confirmation_and_stale_preview_guard(tmp_path,field,value,code):
    studio=make(tmp_path);parent=studio.generate(generation_request());preview=studio.reference_preview(parent['id']);body=fallback_body(preview);body[field]=value
    with pytest.raises(StudioError) as error:studio.apply_reference(parent['id'],body)
    assert error.value.code==code and len(studio.store.list())==1

def test_reference_change_between_preview_and_confirmation_is_rejected(tmp_path,monkeypatch):
    studio=make(tmp_path);parent=studio.generate(generation_request());preview=studio.reference_preview(parent['id'])
    monkeypatch.setattr(reference,'fingerprint',lambda:'changed')
    with pytest.raises(StudioError) as error:studio.apply_reference(parent['id'],fallback_body(preview))
    assert error.value.code=='STALE_REFERENCE_PREVIEW'

def test_existing_correct_case_has_no_reference_changes(tmp_path):
    studio=make(tmp_path,sample_case());parent=studio.generate(generation_request())
    with pytest.raises(StudioError) as error:studio.reference_preview(parent['id'])
    assert error.value.code=='NO_CORRECTIONS'

def test_preview_edit_invalidates_confirmation(tmp_path):
    studio=make(tmp_path);parent=studio.generate(generation_request());preview=studio.reference_preview(parent['id']);case=deepcopy(parent['proposals'][0]['case']);case['steps'][0]['expect']['payout_cents']=2
    studio.edit(parent['id'],case['id'],{'expected_revision':1,'case':case,'reviewer_label':'Fixture editor','review_note':'New expectation revision.'})
    with pytest.raises(StudioError) as error:studio.apply_reference(parent['id'],fallback_body(preview))
    assert error.value.code=='STALE_REVISION'

def test_legacy_v53_attempt_is_counted_before_new_correction(tmp_path):
    root=Path(__file__).resolve().parents[2];studio=make(tmp_path)
    child=json.loads((root/'artifacts/v5.3/proposal-f4981b44e49e4703ae299385ee7ca9fe.json').read_text())
    parent=json.loads((root/f"artifacts/v5.3/proposal-{child['correction_of']}.json").read_text())
    studio.store.create(parent);studio.store.create(child)
    assert studio.view(child['id'])['correction_budget']['used']==1
    studio.provider.output={'cases':[deepcopy(child['proposals'][0]['case'])]}
    new=studio.correct(child['id'],correction_body(child));assert new['correction_attempt']==2
    with pytest.raises(StudioError) as error:studio.correct(new['id'],correction_body(new))
    assert error.value.code=='CORRECTION_LIMIT'

def test_targeted_prompt_contains_exact_replacements_and_no_generation_noise():
    case=sample_case(amount=10001,payout=9001);prompt=correction_prompt({'cases':[case],'reference':[reference.check(case)]})
    assert 'replacement_expectations' in prompt and '10001 - deductible 10000 = 1' in prompt
    assert '"payout_cents": 1' in prompt and 'Create exactly' not in prompt

def test_reference_assistance_does_not_reset_ai_budget(tmp_path):
    studio=make(tmp_path);parent=studio.generate(generation_request());one=studio.correct(parent['id'],correction_body(parent));two=studio.correct(one['id'],correction_body(one));preview=studio.reference_preview(two['id']);child=studio.apply_reference(two['id'],fallback_body(preview))
    with pytest.raises(StudioError) as error:studio.correct(child['id'],correction_body(child))
    assert error.value.code=='CORRECTION_LIMIT'

def test_reference_assistance_retains_prior_approval_in_parent_history(tmp_path):
    # An approved partial approved-evaluation expectation can gain the optional reason.
    case=sample_case();del case['steps'][0]['expect']['reason']
    studio=make(tmp_path,case);parent=studio.generate(generation_request());approved=studio.review(parent['id'],review_request(parent));preview=studio.reference_preview(parent['id']);child=studio.apply_reference(parent['id'],fallback_body(preview));saved=studio.store.get(parent['id'])
    assert saved['approval'] is None and saved['history'][-1]['prior_approval']==approved['approval'] and child['approval'] is None


def test_reference_preview_rejects_unsupported_calculation(tmp_path,monkeypatch):
    studio=make(tmp_path);parent=studio.generate(generation_request())
    monkeypatch.setattr(reference,'check',lambda case:{'status':'unsupported'})
    with pytest.raises(StudioError) as error:studio.reference_preview(parent['id'])
    assert error.value.code=='REFERENCE_UNAVAILABLE'

def test_cannot_submit_arbitrary_replacement_values_in_confirmation(tmp_path):
    studio=make(tmp_path);parent=studio.generate(generation_request());preview=studio.reference_preview(parent['id']);body=fallback_body(preview);body['cases']=[sample_case(payout=123)]
    with pytest.raises(StudioError) as error:studio.apply_reference(parent['id'],body)
    assert error.value.code=='INVALID_REQUEST'

def test_failed_and_interrupted_requests_are_both_charged_before_retry(tmp_path):
    from tests.unit.test_operation_recovery import BlockingProvider,expire,raw_record
    studio=make(tmp_path);parent=studio.generate(generation_request());studio.provider.error=ProviderError('Fixture outage')
    failed=studio.correct(parent['id'],correction_body(parent));assert failed['state']=='generation_failed'
    root=studio.view(parent['id']);blocker=BlockingProvider();studio.provider=blocker
    with ThreadPoolExecutor(max_workers=1) as pool:
        future=pool.submit(studio.correct,root['id'],correction_body(root));assert blocker.entered.wait(3)
        child=raw_record(studio);expire(studio,child['id']);studio.recover_interrupted();blocker.release.set()
        with pytest.raises(StudioError):future.result(timeout=5)
    interrupted=studio.view(child['id']);assert interrupted['correction_budget']['used']==2
    with pytest.raises(StudioError) as error:studio.retry(interrupted['id'],correction_body(interrupted))
    assert error.value.code=='CORRECTION_LIMIT'
    preview=studio.reference_preview(interrupted['id']);repaired=studio.apply_reference(interrupted['id'],fallback_body(preview))
    assert repaired['proposals'][0]['reference']['status']=='matched'


def test_reference_provenance_survives_execution_and_pytest_export(tmp_path):
    studio=make(tmp_path);parent=studio.generate(generation_request());preview=studio.reference_preview(parent['id']);child=studio.apply_reference(parent['id'],fallback_body(preview));approved=studio.review(child['id'],review_request(child))
    run=studio.execute(child['id'],{'expected_revision':approved['revision']})
    assert run['expectation_origin']=='reviewer_confirmed_reference' and run['reference_assisted_of']==parent['id']
    namespace={};exec(compile(studio.export_pytest(child['id']),'exported.py','exec'),namespace)
    assert namespace['SNAPSHOT']['expectation_origin']=='reviewer_confirmed_reference' and namespace['SNAPSHOT']['reference_assisted_of']==parent['id']
