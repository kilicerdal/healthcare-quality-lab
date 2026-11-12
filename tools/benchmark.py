"""A small seeded-defect experiment, not a comprehensive mutation score."""
import json
from pathlib import Path
from healthcare_quality.claims import evaluate_claim
from healthcare_quality.catalog import CONTRACT_HASH

ROOT = Path(__file__).resolve().parents[1]
MUTATIONS = {"eligibility":"G09","coverage":"G10","network":"G11","authorization":"G12","formulary":"G13","deductible":"G14","limit":"G18"}


def benchmark():
    cases = json.loads((ROOT/"tests/data/golden.json").read_text())
    experiments = []
    reference_failures = []
    for case in cases:
        actual = evaluate_claim(case["request"])
        if any(actual[k] != v for k,v in case["expected"].items()):
            reference_failures.append(case["id"])
    for defect,case_id in MUTATIONS.items():
        case = next(case for case in cases if case["id"]==case_id)
        result = evaluate_claim(case["request"],defect=defect)
        observed = {k:result[k] for k in case["expected"]}
        experiments.append({"defect":defect,"case_id":case_id,"rule_id":case["rule_id"],"expected":case["expected"],"observed":observed,"detected":observed != case["expected"]})
    return {"experiment":"Seven authored defect seeds against reviewed synthetic examples","contract_hash":CONTRACT_HASH,
            "reference_cases":len(cases),"reference_failures":reference_failures,
            "detected":sum(e["detected"] for e in experiments),"total":len(experiments),"experiments":experiments,
            "limitation":"Authored seeds and examples are known to the implementation. This is not exhaustive mutation testing, held-out AI evaluation, or evidence of real insurance correctness."}


def main():
    report = benchmark()
    destination=ROOT/"artifacts/defect-benchmark.json"
    destination.parent.mkdir(exist_ok=True)
    destination.write_text(json.dumps(report,indent=2)+"\n")
    print(f"Reference: {report['reference_cases']} cases; {len(report['reference_failures'])} failures. Seeds detected: {report['detected']}/{report['total']}.")
    return 0 if report["detected"]==report["total"] and not report["reference_failures"] else 1

if __name__=="__main__":
    raise SystemExit(main())
