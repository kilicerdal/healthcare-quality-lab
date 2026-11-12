import pytest
from healthcare_quality.ollama_provider import OllamaProvider,ProviderError
from healthcare_quality.quality_lab import QualityLab
from healthcare_quality.ai_studio import StudioService,ExperimentStore
from tests.support.ai_fixtures import FixtureProvider,generation_request
pytestmark=[pytest.mark.unit,pytest.mark.ai,pytest.mark.regression]

def test_socket_timeout_is_bounded_and_never_falls_back(monkeypatch):
    calls=[]
    def timeout(request,timeout):calls.append(timeout);raise TimeoutError('injected timeout')
    monkeypatch.setattr('urllib.request.urlopen',timeout)
    with pytest.raises(ProviderError,match='TimeoutError'):OllamaProvider().generate('qwen2.5:3b','synthetic',{})
    assert calls==[90]


def test_generation_lock_is_released_after_provider_failure(tmp_path):
    provider=FixtureProvider(error=ProviderError('offline'));service=StudioService(ExperimentStore(tmp_path/'ai.sqlite'),provider)
    assert service.generate(generation_request())['state']=='generation_failed'
    provider.error=None
    assert service.generate(generation_request())['state']=='proposed'


def test_comparison_soft_budget_stops_between_calls_and_releases_lock(tmp_path,monkeypatch):
    provider=FixtureProvider();studio=StudioService(ExperimentStore(tmp_path/'ai.sqlite'),provider);lab=QualityLab(tmp_path/'quality.sqlite',studio)
    clock=iter([0,181,182]);monkeypatch.setattr('healthcare_quality.quality_lab.time.monotonic',lambda:next(clock))
    record=lab.start({'split':'development','model':'qwen2.5:3b','task_ids':['D01']},background=False)
    assert record['state']=='failed' and 'budget' in record['error'] and not provider.calls
    assert lab.lock.acquire(False);lab.lock.release()


def test_real_http_header_casing_does_not_break_release_smoke(monkeypatch):
    import io
    from tools.rehearse import request
    class Response(io.BytesIO):
        status=200
        headers={"X-Request-Id":"a"*32}
    monkeypatch.setattr('urllib.request.urlopen',lambda *a,**k:Response(b'{"status":"ok"}'))
    status,body,headers=request('http://127.0.0.1:9999','/api/health')
    assert status==200 and headers['x-request-id']=='a'*32
