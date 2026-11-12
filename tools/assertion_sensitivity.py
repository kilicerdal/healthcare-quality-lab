"""Re-run two existing engineering-reviewed V3 snapshots against two known faults."""
import json
from pathlib import Path
from healthcare_quality.ai_runner import run_cases
from healthcare_quality.ai_schema import digest,contract_fingerprint,validate_cases

ROOT=Path(__file__).resolve().parents[1]
def measure():
    record=json.loads((ROOT/"artifacts/v3/live-demo-experiment.json").read_text())
    rows=[]
    for label,run in zip(("narrow-original","strengthened-reviewed"),record["runs"][:2]):
        cases=run["approved_cases"]
        assert run["contract_fingerprint"]==contract_fingerprint()
        assert all(run["approval"]["hashes"].get(case["id"])==digest(case) for case in cases)
        assert all(p["valid"] for p in validate_cases(cases,record["source_ids"]))
        baseline=run_cases(cases);assert baseline["failed"]==0
        experiments=[]
        for fault in ("ledger_amount","history_skip"):
            result=run_cases(cases,workflow_defect=fault)
            experiments.append({"fault":fault,"detected":result["failed"]>0,"result":result})
        rows.append({"label":label,"original_run_id":run["id"],"reviewer_label":run["approval"]["reviewer_label"],"baseline":baseline,"detected":sum(r["detected"] for r in experiments),"total":2,"experiments":experiments})
    return {"scope":"Two already-known workflow faults, two engineering-reviewed snapshots. Assertion sensitivity demonstration, not independent mutation coverage or learner approval.","snapshots":rows}
if __name__=="__main__":print(json.dumps(measure(),indent=2))
