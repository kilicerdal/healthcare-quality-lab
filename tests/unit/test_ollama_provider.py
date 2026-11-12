import io,json
from urllib.error import URLError
import pytest
from healthcare_quality.ollama_provider import OllamaProvider,ProviderError
from healthcare_quality.ai_schema import suite_schema
from tests.support.ai_fixtures import sample_case
pytestmark=[pytest.mark.unit,pytest.mark.ai,pytest.mark.regression]


def test_real_provider_contract_uses_fixed_loopback_schema_and_budgets(monkeypatch):
    output=json.dumps({'cases':[sample_case()]})
    def respond(request,timeout):
        assert request.full_url=='http://127.0.0.1:11434/api/generate'
        body=json.loads(request.data)
        assert body['format']==suite_schema(1,['HC-007'])
        assert body['stream'] is False and body['options']['num_predict']==2600
        assert timeout==90
        return io.BytesIO(json.dumps({'done':True,'response':output,'eval_count':100,'prompt_eval_count':200}).encode())
    monkeypatch.setattr('urllib.request.urlopen',respond)
    result=OllamaProvider().generate('qwen2.5-coder:3b','prompt',suite_schema(1,['HC-007']))
    assert result['text']==output and result['output_tokens']==100


@pytest.mark.parametrize('body',[{'done':False},{'done':True,'done_reason':'length'},{'done':True,'response':None},[]])
def test_bad_completion_is_explicit_and_keeps_raw_envelope(monkeypatch,body):
    monkeypatch.setattr('urllib.request.urlopen',lambda *a,**k:io.BytesIO(json.dumps(body).encode()))
    with pytest.raises(ProviderError):OllamaProvider().generate('qwen2.5:3b','prompt',{})


def test_network_error_and_unallowed_model_do_not_fallback(monkeypatch):
    def fail(*a,**k):raise URLError('offline')
    monkeypatch.setattr('urllib.request.urlopen',fail)
    with pytest.raises(ProviderError):OllamaProvider().generate('qwen2.5:3b','prompt',{})
    with pytest.raises(ProviderError):OllamaProvider().generate('cloud-model','prompt',{})


def test_oversized_response_is_rejected(monkeypatch):
    monkeypatch.setattr('urllib.request.urlopen',lambda *a,**k:io.BytesIO(b'x'*262145))
    with pytest.raises(ProviderError,match='256 KiB'):OllamaProvider().generate('qwen2.5:3b','prompt',{})


def test_installed_larger_model_disables_hidden_thinking_without_changing_budgets(monkeypatch):
    def respond(request,timeout):
        body=json.loads(request.data)
        assert body['model']=='qwen3.5:27b' and body['think'] is False
        assert 'format' not in body and 'OUTPUT JSON SCHEMA' in body['prompt']
        assert body['options']['num_predict']==2600 and timeout==90
        return io.BytesIO(json.dumps({'done':True,'response':'{}'}).encode())
    monkeypatch.setattr('urllib.request.urlopen',respond)
    assert OllamaProvider().generate('qwen3.5:27b','prompt',{})['text']=='{}'
