from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import json,os,subprocess,sys,threading,time
from pathlib import Path
import pytest
from healthcare_quality.ai_studio import StudioService,ExperimentStore,StudioError
from tests.support.ai_fixtures import FixtureProvider,generation_request,review_request
from tools.fingerprints import ROOT
pytestmark=[pytest.mark.unit,pytest.mark.ai,pytest.mark.regression]

def make(tmp_path,provider=None,**kw):return StudioService(ExperimentStore(tmp_path/'ai.sqlite'),provider or FixtureProvider(),**kw)
def expire(service,id):
    with service.store.transaction() as db:db.execute('UPDATE studio_operations SET expires_at=0 WHERE experiment_id=?',(id,))
def raw_record(service):
    with service.store.transaction() as db:
        row=db.execute('SELECT record_json FROM ai_experiments ORDER BY created_at DESC LIMIT 1').fetchone()
        return json.loads(row['record_json'])

class BlockingProvider(FixtureProvider):
    def __init__(self):super().__init__();self.entered=threading.Event();self.release=threading.Event()
    def generate(self,*args):
        self.entered.set();assert self.release.wait(5),'Test provider was not released'
        return super().generate(*args)


def test_heartbeat_preserves_active_generation_across_service_restart(tmp_path):
    provider=BlockingProvider();service=make(tmp_path,provider,lease_seconds=.6,heartbeat_interval=.05)
    with ThreadPoolExecutor(max_workers=1) as pool:
        future=pool.submit(service.generate,generation_request())
        try:
            assert provider.entered.wait(2);record=raw_record(service)
            time.sleep(.8) # Longer than the original lease: renewal must be real.
            restarted=make(tmp_path)
            assert restarted.store.get(record['id'])['state']=='generating'
            with pytest.raises(StudioError) as error:restarted.review(record['id'],review_request(record))
            assert error.value.code=='EXPERIMENT_BUSY'
        finally:provider.release.set()
        assert future.result(timeout=3)['state']=='proposed'


def test_expired_generation_is_recovered_and_late_worker_is_fenced(tmp_path):
    provider=BlockingProvider();service=make(tmp_path,provider)
    with ThreadPoolExecutor(max_workers=1) as pool:
        future=pool.submit(service.generate,generation_request())
        try:
            assert provider.entered.wait(2);record=raw_record(service);expire(service,record['id'])
            saved=service.store.get(record['id']);assert saved['state']=='interrupted'
            revision=saved['revision'];assert saved['raw_generation'] is None
        finally:provider.release.set()
        with pytest.raises(StudioError) as error:future.result(timeout=3)
        assert error.value.code=='OPERATION_LOST'
    saved=service.store.get(record['id']);assert saved['state']=='interrupted' and saved['revision']==revision
    assert saved['raw_generation'] is None


def test_interrupted_execution_preserves_snapshot_invalidates_approval_and_fences_completion(tmp_path,monkeypatch):
    import healthcare_quality.ai_studio as module
    service=make(tmp_path);record=service.generate(generation_request());record=service.review(record['id'],review_request(record))
    entered,release=threading.Event(),threading.Event();original=module.run_cases
    def block(cases):entered.set();assert release.wait(5);return original(cases)
    monkeypatch.setattr(module,'run_cases',block)
    with ThreadPoolExecutor(max_workers=1) as pool:
        future=pool.submit(service.execute,record['id'],{'expected_revision':record['revision']})
        try:
            assert entered.wait(2);active=service.store.get(record['id']);pending=deepcopy(active['pending_run'])
            expire(service,record['id']);restarted=make(tmp_path);saved=restarted.store.get(record['id'])
            assert saved['state']=='interrupted' and saved['approval'] is None and saved['approved_ids']==[]
            assert saved['runs'][-1]['id']==pending['id'] and saved['runs'][-1]['status']=='interrupted'
            assert saved['runs'][-1]['approved_cases']==pending['approved_cases']
            with pytest.raises(StudioError) as error:restarted.execute(record['id'],{'expected_revision':saved['revision']})
            assert error.value.code=='REVIEW_REQUIRED'
            reviewed=restarted.review(record['id'],review_request(saved))
        finally:release.set()
        with pytest.raises(StudioError) as error:future.result(timeout=3)
        assert error.value.code=='OPERATION_LOST'
    saved=service.store.get(record['id']);assert saved['state']=='approved' and saved['revision']==reviewed['revision'] and len(saved['runs'])==1
    monkeypatch.setattr(module,'run_cases',original)
    assert service.execute(record['id'],{'expected_revision':saved['revision']})['status']=='passed'


def test_successful_operations_leave_no_leases_or_pending_run(tmp_path):
    service=make(tmp_path);record=service.generate(generation_request());record=service.review(record['id'],review_request(record));service.execute(record['id'],{'expected_revision':record['revision']})
    with service.store.transaction() as db:assert db.execute('SELECT COUNT(*) FROM studio_operations').fetchone()[0]==0
    saved=service.store.get(record['id']);assert 'pending_run' not in saved and 'operation' not in saved


def test_explicit_generation_retry_creates_new_unapproved_child_and_rejects_stale_click(tmp_path):
    service=make(tmp_path);parent=service.generate(generation_request())
    with service.store.transaction() as db:parent['state']='generating';service.store.save(db,parent)
    parent=make(tmp_path).store.get(parent['id']);before=deepcopy(parent)
    body={'expected_revision':parent['revision'],'reviewer_label':'Recovery test operator','review_note':'Explicitly retry interrupted generation'}
    child=service.retry(parent['id'],body)
    assert child['id']!=parent['id'] and child['retry_of']==parent['id'] and child['state']=='proposed'
    assert child['approved_ids']==[] and child['approval'] is None and child['runs']==[]
    saved=service.store.get(parent['id']);assert saved['raw_generation']==before['raw_generation'] and saved['proposals']==before['proposals']
    assert saved['history'][-1]['child_experiment_id']==child['id']
    with pytest.raises(StudioError) as error:service.retry(parent['id'],body)
    assert error.value.code=='STALE_REVISION'

@pytest.mark.parametrize('kind',['generation','execution'])
def test_real_process_death_recovers_after_lease_expiry_without_automatic_replay(tmp_path,kind):
    database=tmp_path/'crash.sqlite';marker=tmp_path/'started';ids=tmp_path/'id'
    script="""
import sys,time
from pathlib import Path
from healthcare_quality.ai_studio import StudioService,ExperimentStore
from tests.support.ai_fixtures import FixtureProvider,generation_request,review_request
import healthcare_quality.ai_studio as module
kind,database,marker,ids=sys.argv[1:]
service=StudioService(ExperimentStore(database),FixtureProvider(),lease_seconds=.6,heartbeat_interval=.05)
if kind=='generation':
    def block(*args):
        Path(marker).write_text('inference entered')
        while True:time.sleep(1)
    service.provider.generate=block
    service.generate(generation_request())
else:
    record=service.generate(generation_request());record=service.review(record['id'],review_request(record));Path(ids).write_text(record['id'])
    def block(cases):
        Path(marker).write_text('execution entered')
        while True:time.sleep(1)
    module.run_cases=block
    service.execute(record['id'],{'expected_revision':record['revision']})
"""
    process=subprocess.Popen([sys.executable,'-B','-c',script,kind,str(database),str(marker),str(ids)],cwd=ROOT,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
    try:
        deadline=time.monotonic()+5
        while not marker.exists() and time.monotonic()<deadline:
            if process.poll() is not None:pytest.fail(process.stderr.read().decode())
            time.sleep(.02)
        assert marker.exists();process.kill();process.wait(timeout=3)
        service=StudioService(ExperimentStore(database),FixtureProvider())
        deadline=time.monotonic()+3
        while time.monotonic()<deadline:
            records=service.store.list();record=service.store.get(records[0]['id'])
            if record['state']=='interrupted':break
            time.sleep(.03)
        assert record['state']=='interrupted' and record['interruption']['kind']==kind
        assert not service.provider.calls and record['approval'] is None
        assert len([h for h in record['history'] if h['event']=='operation_interrupted'])==1
        if kind=='execution':assert record['runs'][-1]['status']=='interrupted' and record['runs'][-1]['approved_cases']
    finally:
        if process.poll() is None:process.kill();process.wait(timeout=3)
        process.stderr.close()


def test_recovery_commits_even_when_a_stale_execution_request_is_rejected(tmp_path):
    service=make(tmp_path);record=service.generate(generation_request());record=service.review(record['id'],review_request(record))
    with service.store.transaction() as db:record['state']='running';service.store.save(db,record)
    with pytest.raises(StudioError) as error:service.execute(record['id'],{'expected_revision':record['revision']})
    assert error.value.code=='STALE_REVISION'
    with service.store.transaction() as db:saved=service.store.load(db,record['id'])
    assert saved['state']=='interrupted' and saved['approval'] is None


def test_concurrent_retry_requests_create_only_one_child(tmp_path):
    service=make(tmp_path);parent=service.generate(generation_request())
    with service.store.transaction() as db:parent['state']='generating';service.store.save(db,parent)
    parent=service.store.get(parent['id']);services=[make(tmp_path),make(tmp_path)];barrier=threading.Barrier(2)
    body={'expected_revision':parent['revision'],'reviewer_label':'Concurrent recovery operator','review_note':'Retry the same interrupted parent once'}
    def attempt(worker):
        barrier.wait()
        try:return worker.retry(parent['id'],body)['id']
        except StudioError as error:return error.code
    with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(attempt,services))
    assert results.count('STALE_REVISION')==1
    assert len(service.store.list())==2


def test_interrupted_execution_cannot_export_an_old_approved_wrapper(tmp_path):
    service=make(tmp_path);record=service.generate(generation_request());record=service.review(record['id'],review_request(record))
    with service.store.transaction() as db:record['state']='running';service.store.save(db,record)
    with pytest.raises(StudioError) as error:service.export_pytest(record['id'])
    assert error.value.code=='REVIEW_REQUIRED'


def test_heartbeat_also_covers_output_validation_before_commit(tmp_path,monkeypatch):
    import healthcare_quality.ai_studio as module
    entered,release=threading.Event(),threading.Event();original=module.validate_cases
    def block(*args):entered.set();assert release.wait(4);return original(*args)
    monkeypatch.setattr(module,'validate_cases',block)
    service=make(tmp_path,lease_seconds=.6,heartbeat_interval=.05)
    with ThreadPoolExecutor(max_workers=1) as pool:
        future=pool.submit(service.generate,generation_request())
        try:
            assert entered.wait(2);record=raw_record(service);time.sleep(.8)
            assert make(tmp_path).store.get(record['id'])['state']=='generating'
        finally:release.set()
        assert future.result(timeout=2)['state']=='proposed'
