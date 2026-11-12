"""Opt-in V5.4 known-failure repair and separate newly authored measurement.
Engineering operator initiates each bounded request; UI never auto-retries.
"""
from copy import deepcopy
import json
from pathlib import Path
from healthcare_quality.ai_studio import StudioService,ExperimentStore,now,build_prompt
from healthcare_quality.ai_schema import digest
from healthcare_quality import reference
from healthcare_quality.ollama_provider import SETTINGS
ROOT=Path(__file__).resolve().parents[1]

def run():
    out=ROOT/"artifacts/v5.4";out.mkdir(exist_ok=True);destination=out/"live-correction.json"
    if destination.exists():raise RuntimeError("Preserve prior measurement; refuse overwrite")
    studio=StudioService(ExperimentStore(ROOT/".local/v54-live/ai.sqlite"))
    provider=studio.provider.status()
    if not provider["available"]:raise RuntimeError("Ollama unavailable; no provider fallback")
    previous=json.loads((ROOT/"artifacts/v5.3/live-comparison.json").read_text())
    known=[row for row in previous["results"] if not row["correction"]["literal_pass"]]
    tasks=[]
    for index,(amount,payout) in enumerate([(10002,2),(9998,0),(210002,200000),(205250,195250),(300100,200000)],1):
        case={"id":f"AI-NEW54-{index}","title":"Frozen evaluator boundary","rule_ids":["HC-007"],"rationale":"Check the written synthetic payout contract.","assumptions":[],"steps":[{"action":"evaluate","actor":"none","data":{"plan_id":"commercial_ppo","service":"medical","amount_cents":amount},"expect":{"status":200,"decision":"approved","reason":"COVERED","payout_cents":payout}}]}
        brief="Create exactly one evaluate-only case, actor none, with exactly these data fields: "+json.dumps(case["steps"][0]["data"])+". Include status, decision, reason and payout_cents. Do not add other steps."
        tasks.append({"id":f"N{index:02}","literal_case":case,"request":{"requirement":brief,"source_ids":["HC-007"],"model":"qwen2.5-coder:3b","strategy":"assertions-v2","count":1}})
    steps=[]
    for action,actor,data,status,state,revision,payment in [
        ("submit","customer-m100",{"claim_id":"NEW54-ZERO","member_id":"M100","service":"medical","amount_cents":9901},201,"submitted",1,None),
        ("transition","adjuster-demo",{"claim_id":"NEW54-ZERO","target":"approved"},200,"approved",2,None),
        ("transition","finance-demo",{"claim_id":"NEW54-ZERO","target":"paid"},200,"paid",3,0),
        ("read","customer-m100",{"claim_id":"NEW54-ZERO"},200,"paid",3,0)]:
        steps.append({"action":action,"actor":actor,"data":data,"expect":{"status":status,"claim_status":state,"revision":revision,"event_count":revision,"payout_cents":0,"payment_cents":payment}})
    case={"id":"AI-NEW54-ZERO","title":"Zero payout lifecycle","rule_ids":["HC-007","WF-001","WF-003","WF-004","WF-005"],"rationale":"A zero simulated payment is distinct from no payment.","assumptions":[],"steps":steps}
    brief="Create exactly one case with these four ordered actions, actors and data: "+json.dumps([{k:v for k,v in s.items() if k!="expect"} for s in steps])+". Include all six successful workflow observations at every step. No other steps."
    tasks.append({"id":"N06","literal_case":case,"request":{"requirement":brief,"source_ids":case["rule_ids"],"model":"qwen2.5-coder:3b","strategy":"assertions-v2","count":1}})
    for task in tasks:task["prompt_hash"]=digest(build_prompt(**{ "requirement":task["request"]["requirement"],"source_ids":task["request"]["source_ids"],"strategy":task["request"]["strategy"],"count":1}))
    record={"created_at":now(),"state":"running","provider":provider,"settings":dict(SETTINGS),"reference_fingerprint":reference.fingerprint(),"frozen_new_tasks":tasks,"known_results":[],"new_results":[],"scope":"Known V5.3 failures are reused development cases, counted separately. Six new tasks frozen before inference, not a blind held-out benchmark. Up to two explicit engineering AI attempts per correction lineage; failed/interrupted calls consume budget. Reference-assisted outcomes are separate from AI successes. Only repaired known cases are reviewed/executed by the engineering operator; new model drafts are not approved."}
    def save():destination.write_text(json.dumps(record,indent=2)+"\n")
    def snapshot(r):
        (out/("proposal-"+r["id"]+".json")).write_text(json.dumps(r,indent=2)+"\n")
    def observed(r,literal):
        proposals=r["proposals"];valid=bool(len(proposals)==1 and proposals[0]["valid"])
        result={"experiment_id":r["id"],"state":r["state"],"origin":r.get("expectation_origin","original_ai"),"structure":valid,"complete":bool(valid and proposals[0].get("assertions_complete")),"reference_match":bool(valid and proposals[0]["reference"]["status"]=="matched"),"literal_pass":False}
        if valid:
            from healthcare_quality.evaluation import signature
            case=proposals[0]["case"]
            result["literal_pass"]=signature(case)==signature(literal) and [s["expect"] for s in case["steps"]]==[s["expect"] for s in literal["steps"]]
        return result
    def confirmation(r):
        preview=studio.reference_preview(r["id"])
        body={"expected_revision":preview["expected_revision"],"reviewer_label":"Codex engineering operator (automated attestation)","review_note":"Inspected reference replacement against the frozen literal answer; this is reference-assisted, not an AI success.","reference_fingerprint":preview["reference_fingerprint"],"preview_hash":preview["preview_hash"],"reference_confirmed":True}
        return preview,body
    def request_correction(r):
        return studio.correct(r["id"],{"expected_revision":r["revision"],"reviewer_label":"Codex engineering operator (automated attestation)","review_note":"Explicit bounded live correction request against independent reference; preserve original inputs and metadata."})
    save()
    for row in known:
        current=json.loads((ROOT/f"artifacts/v5.3/proposal-{row['correction']['experiment_id']}.json").read_text())
        parent=json.loads((ROOT/f"artifacts/v5.3/proposal-{current['correction_of']}.json").read_text())
        studio.store.create(parent);studio.store.create(current)
        literal=deepcopy(current["proposals"][0]["case"])
        amount=literal["steps"][0]["data"]["amount_cents"]
        literal["steps"][0]["expect"]["payout_cents"]={10001:1,286450:200000}[amount]
        result={"task_id":row["task_id"],"amount_cents":amount,"literal_payout_cents":literal["steps"][0]["expect"]["payout_cents"],"original":observed(current,literal),"ai_attempts":[],"reference_assisted":None}
        record["known_results"].append(result);save()
        corrected=request_correction(current);snapshot(corrected);result["ai_attempts"].append(observed(corrected,literal));save()
        if not result["ai_attempts"][-1]["literal_pass"]:
            preview,body=confirmation(corrected)
            assert [s["expect"] for s in preview["cases"][0]["steps"]]==[s["expect"] for s in literal["steps"]]
            corrected=studio.apply_reference(corrected["id"],body);snapshot(corrected);result["reference_assisted"]=observed(corrected,literal)
        assert observed(corrected,literal)["literal_pass"]
        reviewed=studio.review(corrected["id"],{"expected_revision":corrected["revision"],"approved_ids":[p["case"]["id"] for p in corrected["proposals"]],"reviewer_label":"Codex engineering operator (automated attestation)","review_note":"Known failure expectations checked against authored literal results, reference and unchanged scenario. Engineering validation only, not authenticated human approval.","expectations_checked":True})
        execution=studio.execute(reviewed["id"],{"expected_revision":reviewed["revision"]});assert execution["status"]=="passed"
        final=studio.view(reviewed["id"]);snapshot(final)
        (out/("test_repaired_"+row["task_id"]+".py")).write_text(studio.export_pytest(final["id"]))
        result["final"]=observed(final,literal);result["execution"]={"run_id":execution["id"],"status":execution["status"],"passed":execution["passed"],"failed":execution["failed"]};save();print("KNOWN",row["task_id"],result["final"],flush=True)
    for task in tasks:
        current=studio.generate(task["request"]);snapshot(current)
        result={"task_id":task["id"],"original":observed(current,task["literal_case"]),"ai_attempts":[],"reference_assisted":None};record["new_results"].append(result);save()
        for _ in range(2):
            if observed(current,task["literal_case"])["literal_pass"]:break
            if not current["proposals"] or not all(p["valid"] for p in current["proposals"]):break
            current=request_correction(current);snapshot(current);result["ai_attempts"].append(observed(current,task["literal_case"]));save()
        result["final_ai"]=observed(current,task["literal_case"])
        # No fallback is counted as AI success. Preview only for unresolved new drafts.
        if not result["final_ai"]["literal_pass"]:
            try:result["reference_preview_available"]=bool(studio.reference_preview(current["id"])["changes"])
            except Exception as error:result["reference_preview_error"]=str(error)
        assert current["approval"] is None and not current["runs"]
        save();print("NEW",task["id"],result["final_ai"],flush=True)
    record["state"]="completed";record["finished_at"]=now()
    record["summary"]={"known_cases":len(record["known_results"]),"known_ai_repaired":sum(r["ai_attempts"][-1]["literal_pass"] for r in record["known_results"]),"known_reference_assisted":sum(r["reference_assisted"] is not None for r in record["known_results"]),"known_executions_passed":sum(r["execution"]["status"]=="passed" for r in record["known_results"]),"new_cases":len(tasks),"new_original_passes":sum(r["original"]["literal_pass"] for r in record["new_results"]),"new_final_ai_passes":sum(r["final_ai"]["literal_pass"] for r in record["new_results"]),"new_ai_correction_calls":sum(len(r["ai_attempts"]) for r in record["new_results"])}
    save();print(json.dumps(record["summary"]),flush=True)

if __name__=="__main__":run()
