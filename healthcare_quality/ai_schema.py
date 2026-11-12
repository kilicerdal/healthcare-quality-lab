"""V3 declarative test language. Validation is not an oracle-correctness check."""
from copy import deepcopy
from collections import Counter
import hashlib
import json
import math
from jsonschema import Draft202012Validator
from healthcare_quality.assertion_quality import assess
from healthcare_quality.catalog import RULES,CONTRACT_HASH
from healthcare_quality.workflow import WORKFLOW_RULES,WORKFLOW_HASH

DSL_VERSION="1.0"
MAX_CASES,MAX_STEPS=4,8
MODELS=("qwen2.5-coder:3b","qwen2.5:3b","qwen3.5:27b")
STR={"type":"string","maxLength":80}
SCALAR={"type":["string","integer","number","boolean","null"],"maxLength":80,"minimum":-100000000,"maximum":100000000}
DATA_PROPERTIES={key:deepcopy(STR) for key in ("plan_id","service","claim_id","member_id","target")}
DATA_PROPERTIES["amount_cents"]={"type":"integer","minimum":-100000000,"maximum":100000000}
for _flag in ("active","in_network","authorized","formulary"):DATA_PROPERTIES[_flag]={"type":"boolean"}
EXPECT_PROPERTIES={
    "status":{"type":"integer","enum":[200,201,400,403,404,409,422]},
    "decision":{"enum":["approved","denied"]},
    "reason":{"enum":["COVERED","INACTIVE_POLICY","SERVICE_NOT_COVERED","OUT_OF_NETWORK","AUTH_REQUIRED","NON_FORMULARY"]},
    "error":{"enum":["INVALID_REQUEST","FORBIDDEN","NOT_FOUND","DUPLICATE_CLAIM","INVALID_TRANSITION","COVERAGE_DENIED"]},
    "claim_status":{"enum":["submitted","approved","paid"]},
    "revision":{"type":"integer","minimum":1,"maximum":9},
    "payout_cents":{"type":"integer","minimum":0,"maximum":100000000},
    "event_count":{"type":"integer","minimum":0,"maximum":9},
    "payment_cents":{"type":["integer","null"],"minimum":0,"maximum":100000000},
}
CASE_SCHEMA={
    "type":"object","additionalProperties":False,
    "required":["id","title","rule_ids","rationale","assumptions","steps"],
    "properties":{
        "id":{"type":"string","pattern":"^AI-[A-Za-z0-9-]{1,30}$"},
        "title":{"type":"string","minLength":3,"maxLength":180},
        "rule_ids":{"type":"array","minItems":1,"maxItems":6,"uniqueItems":True,"items":{"type":"string","pattern":"^(HC|WF)-[0-9]{3}$"}},
        "rationale":{"type":"string","minLength":5,"maxLength":1000},
        "assumptions":{"type":"array","maxItems":4,"items":{"type":"string","minLength":1,"maxLength":300}},
        "steps":{"type":"array","minItems":1,"maxItems":MAX_STEPS,"items":{
            "type":"object","additionalProperties":False,"required":["action","actor","data","expect"],
            "properties":{
                "action":{"enum":["evaluate","submit","transition","read"]},
                "actor":{"type":"string","minLength":1,"maxLength":80},
                "data":{"type":"object","additionalProperties":False,"properties":DATA_PROPERTIES},
                "expect":{"type":"object","minProperties":2,"additionalProperties":False,"required":["status"],"properties":EXPECT_PROPERTIES},
            },
        }},
    },
}
# The provider receives action-specific alternatives, not one union of all observations.
_GENERIC_STEP=deepcopy(CASE_SCHEMA["properties"]["steps"]["items"])
_FIELDS={"evaluate":({"plan_id","service","amount_cents"},{"active","in_network","authorized","formulary"}),
         "submit":({"claim_id","member_id","service","amount_cents"},{"in_network","authorized","formulary"}),
         "transition":({"claim_id","target"},set()),"read":({"claim_id"},set())}
_VARIANTS=[]
for _action,(_required,_optional) in _FIELDS.items():
    _step=deepcopy(_GENERIC_STEP)
    _step["properties"]["action"]={"const":_action}
    _step["properties"]["data"]["properties"]={k:deepcopy(DATA_PROPERTIES[k]) for k in sorted(_required|_optional)}
    _step["properties"]["data"]["required"]=sorted(_required)
    _observable=({"status","decision","reason","error","payout_cents"} if _action=="evaluate" else set(EXPECT_PROPERTIES)-{"decision"})
    _step["properties"]["expect"]["properties"]={k:deepcopy(EXPECT_PROPERTIES[k]) for k in sorted(_observable)}
    if _action=="evaluate":_step["properties"]["actor"]={"const":"none"}
    _VARIANTS.append(_step)
CASE_SCHEMA["properties"]["steps"]["items"]={"oneOf":_VARIANTS}

SUITE_SCHEMA={"type":"object","additionalProperties":False,"required":["cases"],"properties":{"cases":{"type":"array","minItems":1,"maxItems":MAX_CASES,"items":CASE_SCHEMA}}}
Draft202012Validator.check_schema(SUITE_SCHEMA)
VALIDATOR=Draft202012Validator(CASE_SCHEMA)
ALL_RULES={r["id"]:r for r in RULES+WORKFLOW_RULES}
ACTION_FIELDS={
    "evaluate":({"plan_id","service","amount_cents"},{"active","in_network","authorized","formulary"}),
    "submit":({"claim_id","member_id","service","amount_cents"},{"in_network","authorized","formulary"}),
    "transition":({"claim_id","target"},set()),
    "read":({"claim_id"},set()),
}
OBSERVABLES={"evaluate":{"status","decision","reason","error","payout_cents"},
             **{action:set(EXPECT_PROPERTIES) for action in ("submit","transition","read")}}


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,allow_nan=False).encode()).hexdigest()


def contract_fingerprint():
    return digest({"evaluation":CONTRACT_HASH,"workflow":WORKFLOW_HASH,"dsl":DSL_VERSION,"schema":SUITE_SCHEMA})


def suite_schema(count,source_ids=None):
    schema=deepcopy(SUITE_SCHEMA)
    schema["properties"]["cases"]["minItems"]=count
    schema["properties"]["cases"]["maxItems"]=count
    if source_ids is not None and not any(id.startswith("WF-") for id in source_ids):
        schema["properties"]["cases"]["items"]["properties"]["steps"]["items"]={"oneOf":[deepcopy(_VARIANTS[0])]}
    return schema


def json_loads(text):
    def invalid(value):raise ValueError("Non-finite JSON number is not supported")
    return json.loads(text,parse_constant=invalid)


def validate_cases(cases,source_ids):
    if not isinstance(cases,list) or not 1<=len(cases)<=MAX_CASES:
        raise ValueError("Expected 1–4 test cases")
    id_counts=Counter(c.get("id") for c in cases if isinstance(c,dict) and isinstance(c.get("id"),str))
    seen_ids,seen_actions=set(),set()
    checked=[]
    for index,case in enumerate(cases):
        issues=[]
        for error in VALIDATOR.iter_errors(case):
            path=".".join(str(p) for p in error.path) or "case"
            issues.append(f"{path}: {error.message}"[:500])
        if not issues and any(isinstance(value,float) and not math.isfinite(value) for step in case["steps"] for value in step["data"].values()):
            issues.append("Non-finite input")
        if not issues:
            if not set(case["rule_ids"])<=set(source_ids):issues.append("Cited source was not selected for generation")
            if not set(case["rule_ids"])<=set(ALL_RULES):issues.append("Unknown source rule")
            if id_counts[case["id"]]>1:issues.append("Duplicate case ID")
            seen_ids.add(case["id"])
            signature=digest(case["steps"])
            if signature in seen_actions:issues.append("Duplicate action sequence and expected results")
            seen_actions.add(signature)
            for number,step in enumerate(case["steps"],1):
                numeric={"status","revision","payout_cents","event_count","payment_cents"}
                if any(k in numeric and value is not None and type(value) is not int for k,value in step["expect"].items()):issues.append(f"Step {number}: expected numeric observations must be built-in integers")
                if step["action"]=="evaluate" and not any(id.startswith("HC-") for id in case["rule_ids"]):issues.append("Evaluation needs an HC source rule")
                if step["action"]!="evaluate" and not any(id.startswith("WF-") for id in case["rule_ids"]):issues.append("Workflow action needs a WF source rule")
                required,optional=ACTION_FIELDS[step["action"]]
                if not required<=step["data"].keys() or step["data"].keys()-required-optional:
                    issues.append(f"Step {number}: fields outside the {step['action']} action contract")
                if set(step["expect"])-OBSERVABLES[step["action"]]:issues.append(f"Step {number}: expectation is not observable for this action")
                if any(isinstance(v,float) and not math.isfinite(v) for v in step["data"].values()):issues.append("Non-finite input")
        candidate={"case":deepcopy(case),"valid":not issues,"issues":issues[:16],"warnings":[],"hash":None}
        if not issues:
            candidate["hash"]=digest(case)
            candidate["warnings"]=["Expected results require independent reviewer verification; source-ID validity does not establish correctness."]
            if case["assumptions"]:candidate["warnings"].append("Proposed assumptions require explicit inspection.")
            asserted={key for step in case["steps"] for key in step["expect"]}
            if "HC-007" in case["rule_ids"] and "payout_cents" not in asserted:candidate["warnings"].append("HC-007 is cited but the case has no payout assertion.")
            if "WF-004" in case["rule_ids"] and "payment_cents" not in asserted:candidate["warnings"].append("WF-004 is cited but the case has no simulated-payment amount assertion.")
            if "WF-005" in case["rule_ids"] and "event_count" not in asserted:candidate["warnings"].append("WF-005 is cited but the case has no event-count assertion.")
        candidate["quality"]=assess(case) if not issues else None
        candidate["review_ready"]=not issues and candidate["quality"]["complete"]
        checked.append(candidate)
    return checked


GENERATION_SCHEMA_VERSION="complete-outcomes-v1"
def generation_schema(count,source_ids=None):
    """Stronger provider contract; the historical structural DSL is unchanged."""
    schema=suite_schema(count,source_ids)
    variants=schema["properties"]["cases"]["items"]["properties"]["steps"]["items"]["oneOf"]
    def expected(statuses,fields):
        result={"type":"object","additionalProperties":False,"required":list(fields),"properties":{key:deepcopy(EXPECT_PROPERTIES[key]) for key in fields}}
        result["properties"]["status"]={"type":"integer","enum":list(statuses)}
        return result
    for step in variants:
        action=step["properties"]["action"]["const"]
        if action=="evaluate":
            options=[expected([200],["status","decision","reason","payout_cents"]),expected([400],["status","error"])]
        elif action=="submit":
            options=[expected([201],["status","claim_status","revision","payout_cents","event_count","payment_cents"]),expected([400,403,409],["status","error"]),expected([422],["status","error","reason"])]
        else:
            options=[expected([200],["status","claim_status","revision","payout_cents","event_count","payment_cents"]),expected([400,403,404,409] if action=="transition" else [403,404],["status","error"])]
        step["properties"]["expect"]={"oneOf":options}
    Draft202012Validator.check_schema(schema)
    return schema
