"""Execute approved declarative cases in disposable databases, never generated code."""
from pathlib import Path
from tempfile import TemporaryDirectory
import time
from healthcare_quality.claims import ContractError,evaluate_claim,DEFECTS as EVALUATION_DEFECTS
from healthcare_quality.workflow import ClaimStore,WorkflowService,WorkflowError,WORKFLOW_DEFECTS
from healthcare_quality.ai_schema import MAX_CASES,MAX_STEPS


def project_evidence(evidence,status=200):
    claim=evidence["claim"]
    return {"status":status,"claim_status":claim["status"],"revision":claim["revision"],
            "payout_cents":claim["evaluation"]["payout_cents"],"event_count":len(evidence["events"]),
            "payment_cents":evidence["payment"]["amount_cents"] if evidence["payment"] else None}


def perform(step,service,*,evaluation_defect="none"):
    action,actor,data=step["action"],step["actor"],step["data"]
    try:
        if action=="evaluate":
            raw=evaluate_claim(data,defect=evaluation_defect)
            return {"status":200,**{k:raw[k] for k in ("decision","reason","payout_cents")}},raw
        if action=="submit":raw=service.submit(actor,data);return project_evidence(raw,201),raw
        if action=="transition":
            raw=service.transition(actor,data["claim_id"],{"target":data["target"]})
            return project_evidence(raw),raw
        if action=="read":raw=service.get(actor,data["claim_id"]);return project_evidence(raw),raw
        raise ValueError("Action outside allowlist")
    except ContractError as error:
        return {"status":400,"error":"INVALID_REQUEST"},{"error":str(error),"rule_id":"HC-001"}
    except WorkflowError as error:
        observed={"status":error.status,"error":error.code}
        raw={"error":error.code,"message":str(error),"rule_id":error.rule,"details":error.details}
        if error.details and "evaluation" in error.details:observed["reason"]=error.details["evaluation"]["reason"]
        return observed,raw


def run_cases(cases,*,workflow_defect="none",evaluation_defect="none"):
    if evaluation_defect not in EVALUATION_DEFECTS:raise ValueError("Unknown internal evaluator fault profile")
    if workflow_defect not in WORKFLOW_DEFECTS:raise ValueError("Unknown internal fault profile")
    if not 1<=len(cases)<=MAX_CASES:raise ValueError("Case budget exceeded")
    results=[];actions=0;started=time.monotonic()
    with TemporaryDirectory(prefix="hql-v3-execution-") as directory:
        for index,case in enumerate(cases):
            if not 1<=len(case["steps"])<=MAX_STEPS:raise ValueError("Step budget exceeded")
            service=WorkflowService(ClaimStore(Path(directory)/f"case-{index}.sqlite"),defect=workflow_defect)
            steps=[];execution_error=None
            for number,step in enumerate(case["steps"],1):
                if actions>=MAX_CASES*MAX_STEPS or time.monotonic()-started>10:
                    execution_error="Execution action/time budget exhausted";break
                actions+=1
                try:
                    observed,raw=perform(step,service) if evaluation_defect=="none" else perform(step,service,evaluation_defect=evaluation_defect)
                    assertions=[{"field":key,"expected":value,"observed":observed.get(key),
                                 "passed":key in observed and type(observed[key]) is type(value) and observed[key]==value}
                                for key,value in step["expect"].items()]
                    passed=all(a["passed"] for a in assertions)
                    steps.append({"number":number,"action":step["action"],"actor":step["actor"],"data":step["data"],
                                  "expected":step["expect"],"observed":observed,"assertions":assertions,"evidence":raw,"passed":passed})
                    if not passed:break
                except Exception as error:
                    execution_error=f"{type(error).__name__}: {error}"[:500];break
            results.append({"case_id":case["id"],"title":case["title"],"rule_ids":case["rule_ids"],"steps":steps,
                            "execution_error":execution_error,"passed":not execution_error and len(steps)==len(case["steps"]) and all(s["passed"] for s in steps)})
    return {"results":results,"passed":sum(r["passed"] for r in results),"failed":sum(not r["passed"] for r in results),
            "actions_executed":actions,"action_budget":MAX_CASES*MAX_STEPS,"duration_ms":round((time.monotonic()-started)*1000,2),
            "isolation":"Fresh SQLite file per case; all execution files removed after the run. Interactive claims are never used.",
            "scope":"Generated declarative cases against Python services, not generated browser automation or an independent proof of oracle correctness."}
