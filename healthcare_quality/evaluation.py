"""Reference comparison of unexecuted drafts. No generated action is run here."""
from copy import deepcopy
import json
from pathlib import Path
import re
from healthcare_quality.ai_schema import ALL_RULES,digest

DATASET=Path(__file__).with_name("data")/"evaluation_v4.json"
def dataset(): return json.loads(DATASET.read_text())

def signature(case):
    ids={}; result=[]
    for step in case.get("steps",[]):
        data=deepcopy(step["data"])
        if "claim_id" in data:
            value=data["claim_id"]
            if value not in ids:ids[value]=f"CLAIM-{len(ids)+1}"
            data["claim_id"]=ids[value]
        if step["action"] in ("evaluate","submit"):
            for flag in ("in_network","authorized","formulary"):data.setdefault(flag,True)
            if step["action"]=="evaluate":data.setdefault("active",True)
        result.append({"action":step["action"],"actor":step["actor"],"data":data})
    return result

def score(task,record):
    required=sum(len(fields) for fields in task["required_assertions"])
    result={"task_id":task["id"],"generation_ok":record["state"]!="generation_failed",
            "schema_valid":False,"policy_complete":False,"input_match":False,"required_total":required,"required_present":0,
            "required_correct":0,"comparable_total":0,"comparable_correct":0,"strict_pass":False,"differences":[]}
    proposals=record.get("proposals",[])
    if len(proposals)!=1 or not proposals[0]["valid"]:return result
    result["schema_valid"]=True
    result["policy_complete"]=bool(proposals[0].get("review_ready"))
    case=proposals[0]["case"]; reference=task["reference_case"]
    if signature(case)!=signature(reference):return result
    result["input_match"]=True
    for index,(step,ref,fields) in enumerate(zip(case["steps"],reference["steps"],task["required_assertions"]),1):
        for key,value in step["expect"].items():
            if key not in ref["expect"]:result["differences"].append({"step":index,"field":key,"unscored_extra":True})
            if key in ref["expect"]:
                correct=type(value) is type(ref["expect"][key]) and value==ref["expect"][key]
                result["comparable_total"]+=1;result["comparable_correct"]+=int(correct)
                if not correct:result["differences"].append({"step":index,"field":key,"proposed":value,"reference":ref["expect"][key]})
        for key in fields:
            if key in step["expect"]:
                result["required_present"]+=1
                result["required_correct"]+=int(type(step["expect"][key]) is type(ref["expect"][key]) and step["expect"][key]==ref["expect"][key])
            else:result["differences"].append({"step":index,"field":key,"missing":True})
    result["strict_pass"]=result["required_correct"]==required and not result["differences"]
    return result

def summarize(rows):
    keys=("generation_ok","schema_valid","policy_complete","input_match","strict_pass","required_total","required_present","required_correct","comparable_total","comparable_correct")
    return {"requests":len(rows),**{key:sum(int(row.get(key,0)) for row in rows) for key in keys}}

RULE_ID_PATTERN=re.compile(r"(?<![A-Za-z0-9_-])(?:HC|WF)-[0-9]+(?![A-Za-z0-9_-])",re.IGNORECASE)
RETRIEVAL_VERSION="exact-ids-lexical-v2"

def retrieve(query,limit=3):
    if not isinstance(query,str) or not 1<=len(query.strip())<=1000:raise ValueError("Query must contain 1–1000 characters")
    if type(limit) is not int or not 1<=limit<=len(ALL_RULES):raise ValueError("Limit must be between 1 and the number of rules")
    explicit=list(dict.fromkeys(match.upper() for match in RULE_ID_PATTERN.findall(query)))
    if explicit:
        # An explicit source selection is authoritative, including unknown IDs.
        return [{"rule_id":id,"score":100,"matched_terms":[id],"match_method":"exact_rule_id","retrieval_version":RETRIEVAL_VERSION,"rule":ALL_RULES[id]}
                for id in explicit if id in ALL_RULES][:limit]
    stop={"the","a","an","and","of","to","in","for","is","it","with","this","test","claim","claims","hc","wf"}
    def words(text):return set(re.findall(r"[a-z]+",RULE_ID_PATTERN.sub(" ",text).lower()))-stop
    terms=words(query);matches=[]
    for id,rule in ALL_RULES.items():
        common=sorted(terms&words(json.dumps({key:value for key,value in rule.items() if key!="id"})))
        if common:matches.append({"rule_id":id,"score":len(common),"matched_terms":common,"match_method":"lexical_overlap","retrieval_version":RETRIEVAL_VERSION,"rule":rule})
    return sorted(matches,key=lambda r:(-r["score"],r["rule_id"]))[:limit]
