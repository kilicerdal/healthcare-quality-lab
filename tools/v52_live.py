"""Opt-in paired local-model measurement. All prompts frozen before inference.
Reuses V4 tasks explicitly; there is no new/fresh held-out claim.
"""
import json
from copy import deepcopy
from pathlib import Path
from uuid import uuid4
from healthcare_quality.ai_studio import StudioService,ExperimentStore,build_prompt,now
from healthcare_quality.ai_schema import suite_schema,generation_schema,digest
from healthcare_quality.evaluation import dataset,score,summarize
from healthcare_quality.assertion_quality import policy_fingerprint
from healthcare_quality.ollama_provider import SETTINGS
from tools.fingerprints import source_hash
ROOT=Path(__file__).resolve().parents[1]

def run():
    output=ROOT/"artifacts/v5.2";output.mkdir(exist_ok=True)
    destination=output/"live-comparison.json"
    if destination.exists():raise ValueError("Preserve prior measurements; choose a separate run rather than overwriting")
    studio=StudioService(ExperimentStore(ROOT/".local/v52-live/ai-v3.sqlite"))
    provider=studio.provider.status()
    if not provider["available"]:raise RuntimeError("Local Ollama unavailable; no fixture fallback")
    baseline={}
    for split in ("development","held_out"):
        historical=json.loads((ROOT/f"artifacts/v4/{split}-comparison.json").read_text())
        for job in historical["jobs"]:
            if job["request"]["strategy"]=="balanced-v1":baseline[job["task"]["id"]]=job["prompt"]
    jobs=[]
    for index,task in enumerate(dataset()["tasks"]):
        pair=[]
        for mode in ("baseline-v51","complete-v52"):
            request={"requirement":task["brief"],"source_ids":task["source_ids"],"model":"qwen2.5-coder:3b","strategy":"balanced-v1" if mode=="baseline-v51" else "assertions-v2","count":1}
            prompt=baseline[task["id"]] if mode=="baseline-v51" else build_prompt(task["brief"],task["source_ids"],"assertions-v2",1)
            schema=suite_schema(1,task["source_ids"]) if mode=="baseline-v51" else generation_schema(1,task["source_ids"])
            pair.append({"mode":mode,"task":deepcopy(task),"request":request,"prompt":prompt,"prompt_hash":digest(prompt),"schema":schema,"schema_hash":digest(schema)})
        jobs.extend(pair if index%2==0 else pair[::-1])
    record={"id":uuid4().hex,"created_at":now(),"state":"running","kind":"paired-generation-evaluation","dataset_hash":digest(dataset()),"source_hash":source_hash(),"assertion_policy_fingerprint":policy_fingerprint(),"provider":provider,"settings":dict(SETTINGS),"jobs":jobs,"results":[],"summary":{},"scope":"16 contemporary local requests on 8 reused authored V4 tasks, alternating order. Baseline frozen historical prompts/loose schema versus V5.2 prompt/strict schema together. Measures the combined change; no independent prompt-only causal claim, no fresh held-out set, no automatic approval/execution."}
    def save():destination.write_text(json.dumps(record,indent=2)+"\n")
    save()
    for job in jobs:
        request=job["request"]
        profile={"kind":"frozen-baseline-v51","prompt":job["prompt"],"schema":job["schema"]} if job["mode"]=="baseline-v51" else None
        if profile is None and digest(build_prompt(request["requirement"],request["source_ids"],request["strategy"],1))!=job["prompt_hash"]:raise RuntimeError("Frozen prompt drift")
        experiment=studio.generate(request,_evaluation_profile=profile)
        assert experiment["approval"] is None and not experiment["runs"]
        (output/("proposal-"+experiment["id"]+".json")).write_text(json.dumps(experiment,indent=2)+"\n")
        row=score(job["task"],experiment);row.update(mode=job["mode"],experiment_id=experiment["id"],generation_error=experiment["generation_error"],generation_schema_issues=experiment["generation_schema_issues"])
        record["results"].append(row);record["summary"]={mode:summarize([r for r in record["results"] if r["mode"]==mode]) for mode in ("baseline-v51","complete-v52")};save()
        print(job["task"]["id"],job["mode"],"complete",row["policy_complete"],"reference_pass",row["strict_pass"],flush=True)
    record["state"]="completed";record["finished_at"]=now();save();print(json.dumps(record["summary"],indent=2))
if __name__=="__main__":run()
