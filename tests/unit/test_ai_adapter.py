"""AI adapter behavior is deterministic here; these tests do not require Ollama."""
import io
import json
from urllib.error import URLError
import pytest
from tools.ai_review import review_contracts

pytestmark=[pytest.mark.unit,pytest.mark.ai,pytest.mark.regression]


def envelope(reviews):
    return {"done":True,"response":json.dumps({"reviews":reviews}),"prompt_eval_count":10,"eval_count":20}


def suggestions():
    return [{"rule_id":"HC-007","observation":"Check a boundary","suggested_test":"Test one cent above the deductible"} for _ in range(3)]


def mock_response(monkeypatch,body):
    monkeypatch.setattr("urllib.request.urlopen",lambda *args,**kwargs:io.BytesIO(json.dumps(body).encode()))


def test_valid_local_review_is_nonexecutable_and_unreviewed(monkeypatch):
    mock_response(monkeypatch,envelope(suggestions()))
    result=review_contracts("test-model")
    assert result["model"]=="test-model"
    assert result["executable"] is False
    assert result["review_status"]=="unreviewed"
    assert result["input_tokens"]==10
    assert len(result["reviews"])==3


@pytest.mark.parametrize("body", [{"done":False}, {"done":True,"done_reason":"length"}, {"done":True,"response":"not-json"}, envelope([]), envelope([{"rule_id":"invented"}]*3)])
def test_incomplete_malformed_or_unsupported_model_output_is_rejected(monkeypatch,body):
    mock_response(monkeypatch,body)
    with pytest.raises((ValueError,KeyError)):
        review_contracts()


def test_unavailable_model_does_not_silently_use_demo_output(monkeypatch):
    def unavailable(*args,**kwargs):
        raise URLError("unavailable")
    monkeypatch.setattr("urllib.request.urlopen",unavailable)
    with pytest.raises(URLError):
        review_contracts()


def test_ai_request_is_loopback_bounded_and_uses_supplied_model(monkeypatch):
    def capture(request,timeout):
        assert request.full_url=="http://127.0.0.1:11434/api/generate"
        body=json.loads(request.data)
        assert body["model"]=="test-model"
        assert body["stream"] is False
        assert body["options"]["num_predict"]==1000
        assert timeout==7
        return io.BytesIO(json.dumps(envelope(suggestions())).encode())
    monkeypatch.setattr("urllib.request.urlopen",capture)
    review_contracts("test-model",7)
