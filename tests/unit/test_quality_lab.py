from copy import deepcopy
import pytest
from healthcare_quality.evaluation import dataset,score,signature,retrieve,summarize
from healthcare_quality.ai_schema import validate_cases,digest
from healthcare_quality.ai_runner import run_cases
from healthcare_quality.ai_studio import ExperimentStore,StudioService
from healthcare_quality.quality_lab import QualityLab
from tests.support.ai_fixtures import FixtureProvider,generation_request,review_request

pytestmark=[pytest.mark.unit,pytest.mark.ai,pytest.mark.regression]
TASKS=dataset()["tasks"]
def proposal(task,case=None):
    return {"state":"proposed","proposals":validate_cases([case or task["reference_case"]],task["source_ids"])}

@pytest.mark.parametrize("task",TASKS,ids=lambda t:t["id"])
def test_authored_references_are_valid_and_observed_behavior_agrees(task):
    record=proposal(task)
    assert record["proposals"][0]["valid"]
    assert score(task,record)["strict_pass"]
    assert run_cases([task["reference_case"]])["failed"]==0


def test_wrong_oracle_is_rejected_despite_schema_acceptance():
    task=TASKS[0];case=deepcopy(task["reference_case"]);case["steps"][0]["expect"]["payout_cents"]+=1
    result=score(task,proposal(task,case))
    assert result["schema_valid"] and result["input_match"] and not result["strict_pass"]
    assert result["required_correct"]==2 and result["required_total"]==3


def test_missing_monetary_assertion_does_not_get_full_credit():
    task=TASKS[0];case=deepcopy(task["reference_case"]);del case["steps"][0]["expect"]["payout_cents"]
    result=score(task,proposal(task,case));assert result["required_present"]==2 and not result["strict_pass"]


def test_different_valid_scenario_is_unmatched_not_compared():
    task=TASKS[0];case=deepcopy(task["reference_case"]);case["steps"][0]["data"]["amount_cents"]+=1
    result=score(task,proposal(task,case));assert result["schema_valid"] and not result["input_match"] and result["comparable_total"]==0


def test_identifier_normalization_preserves_identity_relationships():
    case=deepcopy(TASKS[2]["reference_case"]);original=signature(case)
    for step in case["steps"]:step["data"]["claim_id"]="NEW-777"
    assert signature(case)==original
    case["steps"][-1]["data"]["claim_id"]="DIFFERENT-777"
    assert signature(case)!=original


def test_explicit_default_flags_match_omitted_defaults():
    case=deepcopy(TASKS[0]["reference_case"])
    case["steps"][0]["data"].update(active=True,in_network=True,authorized=True,formulary=True)
    assert signature(case)==signature(TASKS[0]["reference_case"])


def test_generation_failure_has_zero_comparable_denominator():
    result=score(TASKS[0],{"state":"generation_failed","proposals":[]})
    assert not result["generation_ok"] and summarize([result])["comparable_total"]==0


def test_retrieval_exact_rule_boost_and_abstention():
    assert retrieve("WF-004 payment")[0]["rule_id"]=="WF-004"
    assert retrieve("xyzzyquux") == []
    with pytest.raises(ValueError):retrieve("")


def lab(tmp_path,provider=None):
    studio=StudioService(ExperimentStore(tmp_path/"ai.sqlite"),provider or FixtureProvider())
    return QualityLab(tmp_path/"quality.sqlite",studio)


def test_comparison_freezes_prompts_and_never_approves_or_executes(tmp_path):
    service=lab(tmp_path);record=service.start({"split":"development","model":"qwen2.5-coder:3b","task_ids":["D01"]},background=False)
    assert record["state"]=="completed" and len(record["results"])==2
    for job in record["jobs"]:assert digest(job["prompt"])==job["prompt_hash"]
    for row in record["results"]:
        experiment=service.studio.store.get(row["experiment_id"])
        assert experiment["approval"] is None and not experiment["runs"]
    assert service.studio.provider.calls[0]["prompt"]==record["jobs"][0]["prompt"]


def test_heldout_first_use_and_reuse_are_labeled(tmp_path):
    service=lab(tmp_path);body={"split":"held_out","model":"qwen2.5:3b","task_ids":["H01"]}
    assert service.start(body,background=False)["fresh_holdout"]
    assert not service.start(body,background=False)["fresh_holdout"]

@pytest.mark.parametrize("body",[None,{}, {"split":"development","model":"cloud","task_ids":["D01"]},{"split":"development","model":"qwen2.5:3b","task_ids":["H01"]},{"split":"development","model":"qwen2.5:3b","task_ids":["D01","D01"]}])
def test_comparison_rejects_invalid_request(tmp_path,body):
    from healthcare_quality.ai_studio import StudioError
    with pytest.raises(StudioError):lab(tmp_path).start(body,background=False)


def test_busy_comparison_rejected_and_restart_marks_interrupted(tmp_path):
    from healthcare_quality.ai_studio import StudioError
    service=lab(tmp_path);service.lock.acquire()
    with pytest.raises(StudioError):service.start({"split":"development","model":"qwen2.5:3b","task_ids":["D01"]})
    service.lock.release()
    record=service.start({"split":"development","model":"qwen2.5:3b","task_ids":["D01"]},background=False)
    record["state"]="running";record["owner_pid"]=None;service.save(record)
    assert lab(tmp_path).store.get(record["id"])["state"]=="interrupted"


def stored_run(service,wrong=False):
    if wrong:
        from tests.support.ai_fixtures import historical_failed_experiment
        record=historical_failed_experiment(service.studio.store);run=record['runs'][0]
    else:
        record=service.studio.generate(generation_request())
        record=service.studio.review(record["id"],review_request(record));run=service.studio.execute(record["id"],{"expected_revision":record["revision"]})
    return {"experiment_id":record["id"],"run_id":run["id"],"model":"qwen2.5:3b"}


def test_passing_run_abstains_without_model_call(tmp_path):
    service=lab(tmp_path);body=stored_run(service);count=len(service.studio.provider.calls)
    result=service.investigate(body)
    assert result["state"]=="abstained" and not result["facts"]
    assert len(service.studio.provider.calls)==count


def test_investigation_rejects_unknown_citations_preserves_facts(tmp_path):
    service=lab(tmp_path);body=stored_run(service,True)
    service.studio.provider.output={"summary":"guess","insufficient_evidence":False,"hypotheses":[{"description":"bad","evidence_ids":["E999"],"rule_ids":["HC-007"],"confidence":"low","next_check":"inspect"}]}
    result=service.investigate(body)
    assert result["state"]=="invalid_or_unavailable"
    assert result["facts"][0]["assertion"]["expected"]==91000 and result["facts"][0]["assertion"]["observed"]==90000
    assert not result["hypotheses"]


def test_valid_hypothesis_is_stored_separately_from_observed_facts(tmp_path):
    service=lab(tmp_path);body=stored_run(service,True)
    service.studio.provider.output={"summary":"Check oracle","insufficient_evidence":False,"hypotheses":[{"description":"Oracle may be wrong","evidence_ids":["E1"],"rule_ids":["HC-007"],"confidence":"medium","next_check":"Recalculate the deductible"}]}
    result=service.investigate(body)
    assert result["state"]=="explained" and len(result["facts"])==1 and result["hypotheses"][0]["confidence"]=="medium"
    original=service.studio.store.get(body["experiment_id"])
    assert len(original["runs"])==1 and original["proposals"][0]["case"]["steps"][0]["expect"]["payout_cents"]==91000


def test_known_faults_reveal_why_narrow_assertions_are_insufficient():
    from tools.assertion_sensitivity import measure
    rows=measure()["snapshots"]
    assert rows[0]["detected"]==0 and rows[1]["detected"]==2


def test_internal_fault_profile_is_not_an_arbitrary_execution_parameter():
    with pytest.raises(ValueError):run_cases([TASKS[0]["reference_case"]],workflow_defect="arbitrary")


def test_provider_failure_is_recorded_without_fixture_fallback(tmp_path):
    from healthcare_quality.ollama_provider import ProviderError
    service=lab(tmp_path,FixtureProvider(error=ProviderError("Local inference unavailable")))
    record=service.start({"split":"development","model":"qwen2.5:3b","task_ids":["D01"]},background=False)
    assert record["state"]=="completed" and all(not r["generation_ok"] for r in record["results"])
    assert record["summary"]["balanced-v1"]["strict_pass"]==0


def test_stale_run_abstains_without_new_inference(tmp_path):
    service=lab(tmp_path);body=stored_run(service,True)
    with service.studio.store.transaction() as db:
        record=service.studio.store.load(db,body["experiment_id"]);record["runs"][0]["contract_fingerprint"]="stale";service.studio.store.save(db,record)
    count=len(service.studio.provider.calls);result=service.investigate(body)
    assert result["state"]=="abstained" and result["reason"]=="Stored contract is stale"
    assert len(service.studio.provider.calls)==count


def test_unverified_extra_observable_prevents_strict_pass():
    task=TASKS[0];case=deepcopy(task["reference_case"]);case["steps"][0]["expect"]["event_count"]=999
    assert not score(task,proposal(task,case))["strict_pass"]
