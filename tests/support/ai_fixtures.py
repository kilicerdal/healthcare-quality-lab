"""Explicit offline provider doubles; these are never a live-generator fallback."""
from copy import deepcopy
import json
from healthcare_quality.ollama_provider import ProviderError


def sample_case(id="AI-TEST-1",amount=100000,payout=90000):
    return {"id":id,"title":"Synthetic payout assertion","rule_ids":["HC-007"],"rationale":"Check payout against the written synthetic contract.","assumptions":[],
            "steps":[{"action":"evaluate","actor":"none","data":{"plan_id":"commercial_ppo","service":"medical","amount_cents":amount},"expect":{"status":200,"decision":"approved","reason":"COVERED","payout_cents":payout}}]}


class FixtureProvider:
    def __init__(self,output=None,error=None):self.output,self.error,self.calls=output,error,[]
    def status(self):return {"available":True,"models":[{"name":"fixture-provider; no live inference"}],"mode":"offline test double"}
    def generate(self,model,prompt,schema):
        self.calls.append({"model":model,"prompt":prompt,"schema":schema})
        if self.error:raise self.error
        count=schema["properties"].get("cases",{}).get("minItems",1)
        output=deepcopy(self.output) if self.output is not None else {"cases":[sample_case(f"AI-TEST-{i+1}",100000+i,90000+i) for i in range(count)]}
        text=output if isinstance(output,str) else json.dumps(output)
        return {"text":text,"raw_envelope":{"done":True,"response":text},"model":"offline-test-double","input_tokens":10,"output_tokens":20,"latency_ms":1,"endpoint":"fixture://no-live-model"}


def generation_request(count=1):
    return {"requirement":"Test the synthetic deductible payout with explicit expected results.","source_ids":["HC-007"],"model":"qwen2.5-coder:3b","strategy":"balanced-v1","count":count}


def review_request(record,ids=None):
    return {"expected_revision":record["revision"],"approved_ids":ids if ids is not None else [p["case"]["id"] for p in record["proposals"] if p["valid"]],"reviewer_label":"Automated test-fixture reviewer","review_note":"Fixture expectations independently checked against the synthetic contract.","expectations_checked":True}


def historical_failed_experiment(store):
    """Import actual retained V4 evidence, never bypass current approval gates."""
    from pathlib import Path
    record=json.loads((Path(__file__).resolve().parents[2]/'artifacts/v4/authored-failure-experiment.json').read_text())
    record['test_provenance']='Historical V4 failed execution imported for investigation regression; not a current approval.'
    store.create(record)
    return record
