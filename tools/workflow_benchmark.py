"""Five authored stateful fault experiments; no changes to the interactive DB."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from healthcare_quality.workflow import ClaimStore,WorkflowService,WorkflowError,WORKFLOW_HASH
BASE={"claim_id":"BENCH-100","member_id":"M100","service":"medical","amount_cents":100000}


def observe(service,kind):
    service.submit("customer-m100",BASE)
    if kind=="ownership":
        try:service.get("customer-m200","BENCH-100");return "accessible"
        except WorkflowError as error:return error.status
    if kind=="duplicate_replay":
        try:service.submit("customer-m100",BASE);return "accepted"
        except WorkflowError as error:return error.code
    if kind=="skip_approval":
        try:service.transition("finance-demo","BENCH-100",{"target":"paid"});return "paid"
        except WorkflowError as error:return error.code
    service.transition("adjuster-demo","BENCH-100",{"target":"approved"})
    paid=service.transition("finance-demo","BENCH-100",{"target":"paid"})
    return paid["payment"]["amount_cents"] if kind=="ledger_amount" else len(paid["events"])


def workflow_benchmark():
    expected={"ownership":403,"duplicate_replay":"DUPLICATE_CLAIM","skip_approval":"INVALID_TRANSITION","ledger_amount":90000,"history_skip":3}
    rules={"ownership":"WF-001","duplicate_replay":"WF-002","skip_approval":"WF-003","ledger_amount":"WF-004","history_skip":"WF-005"}
    experiments=[]
    with TemporaryDirectory(prefix="hql-v2-benchmark-") as directory:
        for kind,value in expected.items():
            reference=WorkflowService(ClaimStore(Path(directory)/(kind+"-reference.sqlite")))
            mutant=WorkflowService(ClaimStore(Path(directory)/(kind+"-mutant.sqlite")),defect=kind)
            baseline=observe(reference,kind);actual=observe(mutant,kind)
            experiments.append({"defect":kind,"rule_id":rules[kind],"expected":value,"reference":baseline,"observed_mutant":actual,"reference_passed":baseline==value,"detected":actual!=value})
    return {"workflow_contract_hash":WORKFLOW_HASH,"detected":sum(e["detected"] for e in experiments),"total":len(experiments),"reference_failures":sum(not e["reference_passed"] for e in experiments),"experiments":experiments,"limitation":"Five authored internal fault modes and known expectations. Not exhaustive mutation coverage or a blind benchmark."}


def main():
    from tools.fingerprints import ROOT
    result=workflow_benchmark();path=ROOT/"artifacts/workflow-benchmark.json";path.parent.mkdir(exist_ok=True);path.write_text(json.dumps(result,indent=2)+"\n")
    print(f"Workflow seeds: {result['detected']}/{result['total']} detected; {result['reference_failures']} reference failures.")
    return 0 if result["detected"]==result["total"] and not result["reference_failures"] else 1

if __name__=="__main__":raise SystemExit(main())
