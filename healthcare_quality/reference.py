"""Independent synthetic reference model. Imports no application service/runner/DB.
Shared facts are the authored JSON fixtures; algorithms and state are separate.
"""
from pathlib import Path
from copy import deepcopy
import hashlib,json,re
ROOT=Path(__file__).resolve().parent
VERSION="independent-reference-v1"
FILES=("plans.json","rules.json","members.json","actors.json","workflow_rules.json")
FACTS={name:json.loads((ROOT/"data"/name).read_text()) for name in FILES}
PLANS={p["id"]:p for p in FACTS["plans.json"]}
MEMBERS={m["id"]:m for m in FACTS["members.json"]}
ACTORS={a["id"]:a for a in FACTS["actors.json"]}
SERVICES={s for p in PLANS.values() for s in p["services"]}

def fingerprint():
    payload={"version":VERSION,"facts":FACTS,"implementation_sha256":hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    return hashlib.sha256(json.dumps(payload,sort_keys=True).encode()).hexdigest()

def shape(cases):
    result=deepcopy(cases)
    for case in result:
        for step in case["steps"]:step.pop("expect",None)
    return result

def evaluate(data):
    required={"plan_id","service","amount_cents"};flags={"active","in_network","authorized","formulary"}
    invalid=not isinstance(data,dict) or not required<=data.keys() or bool(set(data)-required-flags)
    if not invalid:
        invalid=not isinstance(data["plan_id"],str) or data["plan_id"] not in PLANS or not isinstance(data["service"],str) or data["service"] not in SERVICES or type(data["amount_cents"]) is not int or not 1<=data["amount_cents"]<=100000000 or any(type(data[k]) is not bool for k in flags if k in data)
    if invalid:return {"status":400,"error":"INVALID_REQUEST"},"HC-001: invalid synthetic request; no financial result"
    plan=PLANS[data["plan_id"]];service=data["service"]
    if not data.get("active",True):reason="INACTIVE_POLICY"
    elif service not in plan["services"]:reason="SERVICE_NOT_COVERED"
    elif plan["network_required"] and not data.get("in_network",True):reason="OUT_OF_NETWORK"
    elif service in plan["authorization_services"] and not data.get("authorized",True):reason="AUTH_REQUIRED"
    elif service=="prescription" and not data.get("formulary",True):reason="NON_FORMULARY"
    else:reason=None
    if reason:return {"status":200,"decision":"denied","reason":reason,"payout_cents":0},"Ordered written denial rules: "+reason+"; payout 0"
    amount,deductible,cap=data["amount_cents"],plan["deductible_cents"],plan["limit_cents"]
    if amount<=deductible:payout=0;explanation=f"{amount} <= deductible {deductible}; payout = 0"
    elif amount>=deductible+cap:payout=cap;explanation=f"{amount} >= deductible {deductible} + payout cap {cap}; payout = {cap}"
    else:payout=amount-deductible;explanation=f"{amount} - deductible {deductible} = {payout}; below payout cap {cap}"
    return {"status":200,"decision":"approved","reason":"COVERED","payout_cents":payout},explanation

class Unsupported(ValueError):pass

class Model:
    def __init__(self):self.claims={}
    def project(self,claim,status=200):return {"status":status,"claim_status":claim["state"],"revision":claim["revision"],"payout_cents":claim["payout"],"event_count":claim["events"],"payment_cents":claim["payment"]}
    def step(self,step):
        action,data,actor_id=step["action"],step["data"],step["actor"]
        if action=="evaluate":return evaluate(data)
        if action not in ("submit","transition","read"):raise Unsupported("Action outside reference model")
        actor=ACTORS.get(actor_id)
        def error(status,code):return {"status":status,"error":code},f"Written workflow contract: {code}; no successful mutation"
        if actor is None:return error(403,"FORBIDDEN")
        if action=="submit":
            if actor["role"]!="customer":return error(403,"FORBIDDEN")
            required={"claim_id","member_id","service","amount_cents"};optional={"in_network","authorized","formulary"}
            if not required<=data.keys() or set(data)-required-optional:return error(400,"INVALID_REQUEST")
            id=data["claim_id"]
            if not isinstance(id,str) or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{2,47}",id) is None:return error(400,"INVALID_REQUEST")
            if data["member_id"]!=actor["member_id"]:return error(403,"FORBIDDEN")
            member=MEMBERS.get(data["member_id"])
            if member is None:return error(400,"INVALID_REQUEST")
            inp={"plan_id":member["plan_id"],"active":member["active"],"service":data["service"],"amount_cents":data["amount_cents"],**{k:data[k] for k in optional if k in data}}
            calculated,why=evaluate(inp)
            if calculated["status"]==400:return error(400,"INVALID_REQUEST")
            if id in self.claims:return error(409,"DUPLICATE_CLAIM")
            if calculated["decision"]=="denied":return {"status":422,"error":"COVERAGE_DENIED","reason":calculated["reason"]},why
            claim={"member":member["id"],"state":"submitted","revision":1,"events":1,"payout":calculated["payout_cents"],"payment":None};self.claims[id]=claim
            return self.project(claim,201),why+"; submission creates revision/event 1; no payment yet"
        id=data.get("claim_id")
        if action=="transition":
            if set(data)!={"claim_id","target"} or data["target"] not in ("approved","paid"):return error(400,"INVALID_REQUEST")
            target=data["target"];role="adjuster" if target=="approved" else "finance"
            if actor["role"]!=role:return error(403,"FORBIDDEN")
            if id not in self.claims:return error(404,"NOT_FOUND")
            claim=self.claims[id]
            preceding="submitted" if target=="approved" else "approved"
            if claim["state"]!=preceding:return error(409,"INVALID_TRANSITION")
            claim["state"]=target;claim["revision"]+=1;claim["events"]+=1
            if target=="paid":claim["payment"]=claim["payout"]
            return self.project(claim),"One successful transition adds one revision and event; payment equals stored reference payout only when paid"
        if id not in self.claims:return error(404,"NOT_FOUND")
        claim=self.claims[id]
        if actor["role"]=="customer" and actor["member_id"]!=claim["member"]:return error(403,"FORBIDDEN")
        return self.project(claim),"Read-only reference state; no revision, event or ledger changes"

def check(case):
    model=Model();steps=[];mismatches=[]
    try:
        for index,step in enumerate(case["steps"],1):
            expected,why=model.step(step)
            differences=[]
            for field,proposed in step["expect"].items():
                if field not in expected or type(proposed) is not type(expected[field]) or proposed!=expected[field]:
                    item={"step":index,"field":field,"proposed":proposed,"reference":expected.get(field),"observable":field in expected,"explanation":why};mismatches.append(item);differences.append(item)
            steps.append({"step":index,"expected":expected,"derivation":why,"mismatches":differences})
        status="matched" if not mismatches else "mismatch"
        return {"status":status,"reference_version":VERSION,"reference_fingerprint":fingerprint(),"steps":steps,"mismatches":mismatches,"scope":"Compares declared expectations against an independently implemented synthetic reference; shared fixture mistakes remain possible. Completeness and reviewer approval are separate."}
    except (Unsupported,KeyError,TypeError,ValueError) as error:
        return {"status":"unsupported","reference_version":VERSION,"reference_fingerprint":fingerprint(),"steps":steps,"mismatches":mismatches,"reason":str(error)[:300]}
