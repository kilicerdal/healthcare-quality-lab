import pytest
pytestmark=[pytest.mark.unit,pytest.mark.regression]
from tools.ollama_ci import plan

def test_request_budget_includes_correction_calls():
    assert plan('qwen3.5:27b','reserved-full',2,True)['maximum_requests']==24
    with pytest.raises(ValueError):plan('qwen3.5:27b','reserved-full',3,True)

@pytest.mark.parametrize('values',[('unknown','development',1,False),('qwen3.5:27b','unknown',1,False),('qwen3.5:27b','development',True,False),('qwen3.5:27b','development',1,'true')])
def test_untrusted_or_ambiguous_runner_inputs_are_rejected(values):
    with pytest.raises(ValueError):plan(*values)
