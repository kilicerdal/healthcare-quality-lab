from copy import deepcopy
import json
from concurrent.futures import ThreadPoolExecutor
import threading
import pytest
from healthcare_quality.ai_schema import validate_cases,contract_fingerprint,suite_schema,generation_schema
from healthcare_quality.ai_studio import StudioService,ExperimentStore,StudioError
from healthcare_quality.ai_runner import run_cases
from healthcare_quality.ollama_provider import ProviderError
from tests.support.ai_fixtures import FixtureProvider,sample_case,generation_request,review_request

pytestmark=[pytest.mark.unit,pytest.mark.ai,pytest.mark.regression]

@pytest.fixture
def studio(tmp_path):return StudioService(ExperimentStore(tmp_path/'studio.sqlite'),FixtureProvider())


def test_generation_creates_new_unapproved_cases_and_preserves_raw_provenance(studio):
    request=generation_request();record=studio.generate(request)
    assert record['state']=='proposed' and record['revision']==1
    assert record['approved_ids']==[] and record['approval'] is None and record['runs']==[]
    assert record['proposals'][0]['case']['steps'][0]['expect']['payout_cents']==90000
    assert request['requirement'] in record['prompt']
    assert record['raw_generation']['raw_envelope']['response']
    assert record['source_rules'][0]['id']=='HC-007'
    assert record['contract_fingerprint']==contract_fingerprint()
    assert studio.provider.calls[0]['schema']==generation_schema(1,['HC-007'])


@pytest.mark.smoke
def test_approved_generated_case_executes_and_records_snapshot(studio):
    record=studio.generate(generation_request())
    reviewed=studio.review(record['id'],review_request(record))
    assert reviewed['revision']==2
    result=studio.execute(record['id'],{'expected_revision':2})
    assert result['status']=='passed' and result['passed']==1
    assert result['results'][0]['steps'][0]['observed']['payout_cents']==90000
    assert result['approval']['reviewer_label']=='Automated test-fixture reviewer'
    assert studio.store.get(record['id'])['runs'][0]==result


@pytest.mark.parametrize('change',[{'model':'cloud-model'},{'model':[]},{'strategy':{}},{'count':0},{'count':5},{'count':True},{'source_ids':['invented']},{'source_ids':[]},{'source_ids':['HC-007','HC-007']},{'requirement':'x'}])
def test_invalid_generation_request_never_calls_provider(studio,change):
    with pytest.raises(StudioError):studio.generate({**generation_request(),**change})
    assert studio.provider.calls==[] and studio.store.list()==[]


@pytest.mark.parametrize('output',['not JSON',{'cases':[]},{'cases':[sample_case(),sample_case()]},{'unexpected':[]}])
def test_malformed_generation_is_saved_as_explicit_failure(studio,output):
    studio.provider=FixtureProvider(output)
    record=studio.generate(generation_request())
    assert record['state']=='generation_failed'
    assert record['generation_error']
    assert record['raw_generation'] is not None
    assert record['approved_ids']==[]


def test_provider_failure_has_no_fixture_fallback_and_is_not_reviewable(studio):
    studio.provider=FixtureProvider(error=ProviderError('Model unavailable'))
    record=studio.generate(generation_request())
    assert record['state']=='generation_failed' and record['proposals']==[]
    with pytest.raises(StudioError) as error:studio.review(record['id'],review_request(record,[]))
    assert error.value.code=='INVALID_STATE'


def test_generation_semaphore_rejects_a_second_inflight_request(studio):
    studio.generation_lock.acquire()
    try:
        with pytest.raises(StudioError) as error:studio.generate(generation_request())
        assert error.value.status==429
        assert studio.provider.calls==[]
    finally:studio.generation_lock.release()


@pytest.mark.sanity
def test_execution_before_review_is_blocked(studio):
    record=studio.generate(generation_request())
    with pytest.raises(StudioError) as error:studio.execute(record['id'],{'expected_revision':1})
    assert error.value.code=='REVIEW_REQUIRED'
    assert studio.store.get(record['id'])['runs']==[]


def test_review_requires_explicit_attestation(studio):
    record=studio.generate(generation_request())
    with pytest.raises(StudioError):studio.review(record['id'],{**review_request(record),'expectations_checked':False})
    assert studio.store.get(record['id'])['approval'] is None


def test_only_selected_cases_execute(studio):
    record=studio.generate(generation_request(2));first=record['proposals'][0]['case']['id']
    reviewed=studio.review(record['id'],review_request(record,[first]))
    run=studio.execute(record['id'],{'expected_revision':reviewed['revision']})
    assert [r['case_id'] for r in run['results']]==[first]


def test_empty_review_is_not_approval(studio):
    record=studio.generate(generation_request());reviewed=studio.review(record['id'],review_request(record,[]))
    assert reviewed['state']=='reviewed_no_approval'
    with pytest.raises(StudioError):studio.execute(record['id'],{'expected_revision':reviewed['revision']})


def test_edits_invalidate_approval_and_keep_raw_generation_and_prior_versions(studio):
    record=studio.generate(generation_request());reviewed=studio.review(record['id'],review_request(record))
    changed=deepcopy(record['proposals'][0]['case']);changed['steps'][0]['data']['amount_cents']=20000;changed['steps'][0]['expect']['payout_cents']=10000
    edited=studio.edit(record['id'],changed['id'],{'expected_revision':reviewed['revision'],'case':changed,'reviewer_label':'Fixture reviewer','review_note':'Corrected independently from HC-007.'})
    assert edited['revision']==3 and edited['approval'] is None and edited['approved_ids']==[]
    assert edited['raw_generation']==record['raw_generation']
    assert edited['history'][-1]['before']==record['proposals'][0]['case']
    with pytest.raises(StudioError):studio.execute(record['id'],{'expected_revision':3})


def test_stale_review_or_run_revision_is_rejected(studio):
    record=studio.generate(generation_request());studio.review(record['id'],review_request(record))
    with pytest.raises(StudioError) as error:studio.review(record['id'],review_request(record))
    assert error.value.code=='STALE_REVISION'
    with pytest.raises(StudioError):studio.execute(record['id'],{'expected_revision':1})


def test_structurally_valid_wrong_oracle_is_blocked_before_execution(studio):
    wrong=sample_case(payout=1);studio.provider=FixtureProvider({'cases':[wrong]})
    record=studio.generate(generation_request());assert record['proposals'][0]['valid']
    assert record['proposals'][0]['reference']['status']=='mismatch'
    with pytest.raises(StudioError) as error:studio.review(record['id'],review_request(record))
    assert error.value.code=='REFERENCE_MISMATCH'
    assert not studio.store.get(record['id'])['runs']


def test_unknown_or_invalid_case_cannot_be_approved(studio):
    record=studio.generate(generation_request())
    with pytest.raises(StudioError):studio.review(record['id'],review_request(record,['AI-NOT-THERE']))


def test_contract_change_blocks_review_and_execution(studio,monkeypatch):
    record=studio.generate(generation_request());approved=studio.review(record['id'],review_request(record))
    monkeypatch.setattr('healthcare_quality.ai_studio.contract_fingerprint',lambda:'changed')
    with pytest.raises(StudioError) as error:studio.execute(record['id'],{'expected_revision':approved['revision']})
    assert error.value.code=='STALE_CONTRACT'


def test_tampered_case_does_not_match_approved_hash(studio):
    record=studio.generate(generation_request());approved=studio.review(record['id'],review_request(record))
    with studio.store.transaction() as db:
        tampered=studio.store.load(db,record['id']);tampered['proposals'][0]['case']['steps'][0]['expect']['payout_cents']=12;studio.store.save(db,tampered)
    with pytest.raises(StudioError) as error:studio.execute(record['id'],{'expected_revision':approved['revision']})
    assert error.value.code=='STALE_APPROVAL'


def test_concurrent_execution_and_edit_are_blocked_while_run_is_active(studio,monkeypatch):
    record=studio.generate(generation_request());approved=studio.review(record['id'],review_request(record))
    started,release=threading.Event(),threading.Event()
    def slow_runner(cases):started.set();assert release.wait(3);return run_cases(cases)
    monkeypatch.setattr('healthcare_quality.ai_studio.run_cases',slow_runner)
    with ThreadPoolExecutor(max_workers=1) as pool:
        future=pool.submit(studio.execute,record['id'],{'expected_revision':approved['revision']})
        assert started.wait(3)
        with pytest.raises(StudioError) as error:studio.execute(record['id'],{'expected_revision':approved['revision']})
        assert error.value.code=='EXPERIMENT_BUSY'
        release.set();assert future.result()['status']=='passed'


def test_reopening_store_preserves_generation_and_review(studio):
    record=studio.generate(generation_request());approved=studio.review(record['id'],review_request(record))
    assert ExperimentStore(studio.store.path).get(record['id'])==approved


@pytest.mark.parametrize('mutation',[
    lambda c:c.update(python='print(1)'),
    lambda c:c['steps'][0].update(action='shell'),
    lambda c:c['steps'][0]['data'].update(command='rm -rf'),
    lambda c:c['steps'][0]['data'].update(amount_cents='100000'),
    lambda c:c['steps'][0]['data'].update(amount_cents=True),
    lambda c:c['steps'][0]['expect'].update(event_count=1),
    lambda c:c['steps'][0].update(expect={'status':200}),
    lambda c:c.update(rule_ids=['HC-999']),
    lambda c:c['steps'][0]['expect'].update(payout_cents=90000.0),
    lambda c:c.update(steps=c['steps']*9),
])
def test_schema_blocks_unsafe_unsupported_or_weak_cases(mutation):
    case=sample_case();mutation(case)
    assert not validate_cases([case],['HC-007'])[0]['valid']


def test_duplicate_case_ids_are_all_blocked_and_duplicate_actions_are_flagged():
    case=sample_case();other=deepcopy(case);other['title']='Different title'
    assert all(not p['valid'] for p in validate_cases([case,other],['HC-007']))
    other['id']='AI-DIFFERENT'
    assert not validate_cases([case,other],['HC-007'])[1]['valid']


def test_run_cases_isolated_between_cases_and_cleans_databases(monkeypatch):
    from healthcare_quality import ai_runner
    paths=[];original=ai_runner.ClaimStore
    def capture(path):paths.append(path);return original(path)
    monkeypatch.setattr(ai_runner,'ClaimStore',capture)
    cases=[sample_case(),sample_case('AI-TEST-2',20000,10000)]
    assert run_cases(cases)['passed']==2
    assert len(set(paths))==2 and all(not p.exists() for p in paths)


def test_unapproved_pytest_export_is_blocked(studio):
    record=studio.generate(generation_request())
    with pytest.raises(StudioError):studio.export_pytest(record['id'])


def test_reviewed_pytest_wrapper_runs_selected_cases(tmp_path,studio):
    import subprocess,sys
    from tools.fingerprints import ROOT
    record=studio.generate(generation_request(2));studio.review(record['id'],review_request(record))
    script=studio.export_pytest(record['id'])
    path=tmp_path/'test_exported_ai.py';path.write_text(script)
    result=subprocess.run([sys.executable,'-m','pytest','-c',str(ROOT/'pytest.ini'),str(path),'-q','-p','no:cacheprovider'],cwd=ROOT,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
    assert result.returncode==0,result.stdout
    assert '2 passed' in result.stdout


def test_reason_prose_is_not_accepted_as_a_reason_code():
    case=sample_case();case['steps'][0]['expect']['reason']='COVERED with some explanation'
    assert not validate_cases([case],['HC-007'])[0]['valid']


def test_missing_payment_assertion_is_flagged_as_quality_warning():
    case=sample_case();case['rule_ids']=['HC-007','WF-004']
    checked=validate_cases([case],['HC-007','WF-004'])[0]
    assert checked['valid']
    assert any('no simulated-payment amount assertion' in warning for warning in checked['warnings'])


def test_execution_exception_is_recorded_and_does_not_leave_busy_state(studio,monkeypatch):
    record=studio.generate(generation_request());approved=studio.review(record['id'],review_request(record))
    def fail():raise OSError('injected fingerprint read error')
    monkeypatch.setattr('healthcare_quality.ai_studio.source_hash',fail)
    result=studio.execute(record['id'],{'expected_revision':approved['revision']})
    assert result['status']=='execution_error'
    saved=studio.store.get(record['id'])
    assert saved['state']=='approved' and saved['runs'][0]['status']=='execution_error'
