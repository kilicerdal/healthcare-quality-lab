"""Explicit opt-in live Ollama experiments, outside deterministic CI."""
import argparse
from copy import deepcopy
import json
from pathlib import Path
from uuid import uuid4
from healthcare_quality.app import create_app
from healthcare_quality.ai_schema import validate_cases,contract_fingerprint,digest,DSL_VERSION
from healthcare_quality.ai_studio import now
from healthcare_quality.evaluation import dataset
from tools.assertion_sensitivity import measure
ROOT=Path(__file__).resolve().parents[1]

def main():
    parser=argparse.ArgumentParser();parser.add_argument("--split",choices=("development","held_out","investigation","sensitivity"),required=True)
    args=parser.parse_args();out=ROOT/"artifacts/v4";out.mkdir(exist_ok=True)
    app=create_app();studio=app.extensions["studio"];lab=app.extensions["quality_lab"]
    if args.split in ("development","held_out"):
        ids=[t["id"] for t in dataset()["tasks"] if t["split"]==args.split]
        record=lab.start({"split":args.split,"model":"qwen2.5-coder:3b","task_ids":ids},background=False)
        (out/(args.split+"-comparison.json")).write_text(json.dumps(record,indent=2)+"\n")
        for row in record["results"]:
            if row["experiment_id"]:
                experiment=studio.store.get(row["experiment_id"])
                (out/("proposal-"+row["experiment_id"]+".json")).write_text(json.dumps(experiment,indent=2)+"\n")
        print(json.dumps({"id":record["id"],"state":record["state"],"summary":record["summary"]},indent=2))
    elif args.split=="sensitivity":
        record=measure();(out/"assertion-sensitivity.json").write_text(json.dumps(record,indent=2)+"\n")
        print([(r["label"],r["detected"],r["total"]) for r in record["snapshots"]])
    else:
        # Explicitly authored wrong-oracle fixture, never represented as model-generated.
        case=deepcopy(dataset()["tasks"][0]["reference_case"])
        case.update(id="AI-AUTHORED-WRONG-ORACLE",title="Authored wrong-oracle investigation fixture")
        case["steps"][0]["data"]["amount_cents"]=100000
        case["steps"][0]["expect"]["payout_cents"]=91000
        record={"id":uuid4().hex,"version":"4.0.0","created_at":now(),"requirement":"Authored failure fixture: intentionally wrong payout 91000 for amount 100000. Not AI-generated.","source_ids":["HC-007"],"source_rules":[],"model":"authored-fixture; no model generation","strategy":"engineering-fixture","requested_count":1,
            "prompt":"No generation: authored engineering evidence fixture","prompt_hash":digest("authored fixture"),"settings":{},"dsl_version":DSL_VERSION,"contract_fingerprint":contract_fingerprint(),"state":"proposed","revision":1,"raw_generation":None,"generation_error":None,"proposals":validate_cases([case],["HC-007"]),"approved_ids":[],"approval":None,"history":[],"runs":[],"origin":"Authored by Codex for failure investigation; not learner approval or Ollama test generation"}
        studio.store.create(record)
        record=studio.review(record["id"],{"expected_revision":1,"approved_ids":[case["id"]],"reviewer_label":"Codex authored fault-fixture review","review_note":"Intentionally wrong oracle, approved only to demonstrate an actual failed assertion. Not learner approval.","expectations_checked":True})
        run=studio.execute(record["id"],{"expected_revision":record["revision"]});assert run["failed"]==1
        explanation=lab.investigate({"experiment_id":record["id"],"run_id":run["id"],"model":"qwen2.5-coder:3b"})
        (out/"authored-failure-experiment.json").write_text(json.dumps(studio.store.get(record["id"]),indent=2)+"\n")
        (out/"live-investigation.json").write_text(json.dumps(explanation,indent=2)+"\n")
        print(json.dumps({"state":explanation["state"],"facts":explanation["facts"],"summary":explanation.get("summary"),"hypotheses":explanation["hypotheses"],"reason":explanation.get("reason")},indent=2))
if __name__=="__main__":main()
