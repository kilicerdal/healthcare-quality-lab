"""Versioned assertion completeness. Never executes drafts or supplies expected values."""
import hashlib,json
POLICY_VERSION="business-observations-v1"
WORKFLOW_FIELDS=("status","claim_status","revision","payout_cents","event_count","payment_cents")
POLICY={"version":POLICY_VERSION,"evaluation_200":["status","decision","payout_cents"],"denial_extra":["reason"],"workflow_success":list(WORKFLOW_FIELDS),"failure":["status","error"],"coverage_denial_extra":["reason"],"known_claim_rejected_mutation":"Successful unchanged readback before another mutation of that claim"}

def policy_fingerprint():return hashlib.sha256(json.dumps(POLICY,sort_keys=True).encode()).hexdigest()

def requirements(step):
    action,status=step["action"],step["expect"]["status"]
    if action=="evaluate" and status==200:
        return {"status","decision","payout_cents"}|({"reason"} if step["expect"].get("decision")=="denied" else set()),{"status","decision","reason","payout_cents"}
    if (action=="submit" and status==201) or (action in ("transition","read") and status==200):return set(WORKFLOW_FIELDS),set(WORKFLOW_FIELDS)
    errors={"evaluate":{400},"submit":{400,403,409,422},"transition":{400,403,404,409},"read":{403,404}}
    if status not in errors[action]:return None,set()
    fields={"status","error"}|({"reason"} if action=="submit" and status==422 else set())
    return fields,fields

def assess(case):
    issues=[];steps=[];known={};guards=[]
    for index,step in enumerate(case["steps"]):
        number=index+1;expected=step["expect"];required,allowed=requirements(step)
        missing=sorted(required-set(expected)) if required is not None else []
        unsupported=sorted(set(expected)-allowed)
        if required is None:issues.append({"step":number,"kind":"unsupported_status","message":"Expected status is not observable for this action"})
        if missing:issues.append({"step":number,"kind":"missing_assertions","fields":missing,"message":"Missing required assertions: "+", ".join(missing)})
        if unsupported:issues.append({"step":number,"kind":"unsupported_observations","fields":unsupported,"message":"Fields not returned for this outcome: "+", ".join(unsupported)})
        steps.append({"step":number,"action":step["action"],"status":expected["status"],"required_fields":sorted(required or []),"missing_fields":missing,"unsupported_fields":unsupported})
        id=step["data"].get("claim_id");success=expected["status"] in (200,201)
        if id and id in known and step["action"] in ("submit","transition") and not success:
            guard=None
            for later_index in range(index+1,len(case["steps"])):
                later=case["steps"][later_index]
                if later["data"].get("claim_id")!=id:continue
                if later["action"]=="read" and later["expect"]["status"]==200:guard=(later_index+1,later);break
                if later["action"] in ("submit","transition"):break
            guards.append({"rejected_step":number,"claim_id":id,"readback_step":guard[0] if guard else None})
            if not guard:issues.append({"step":number,"kind":"missing_readback","message":"Read the known claim successfully after this rejected mutation, before another mutation, asserting unchanged status, revision, payout, events and payment"})
            else:
                changed=[key for key in WORKFLOW_FIELDS if key!="status" and key in known[id] and key in guard[1]["expect"] and (type(known[id][key]) is not type(guard[1]["expect"][key]) or known[id][key]!=guard[1]["expect"][key])]
                if changed:issues.append({"step":guard[0],"kind":"changed_after_rejection","fields":changed,"message":"Readback contradicts the previously asserted unchanged state: "+", ".join(changed)})
        if id and success and step["action"] in ("submit","transition","read"):known[id]=expected
    return {"policy_version":POLICY_VERSION,"policy_fingerprint":policy_fingerprint(),"complete":not issues,"issues":issues,"steps":steps,"rejected_mutation_guards":guards,"scope":"Presence, response observability and declared readback consistency. Does not prove payout arithmetic, correct actors or oracle correctness."}
