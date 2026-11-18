"""Rehearse archived releases through actual loopback HTTP. No model inference."""
import argparse
from contextlib import contextmanager
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
import urllib.request
from urllib.error import HTTPError,URLError
from uuid import uuid4
from tools.release import ROOT,stage,activate,rollback,pointer,resolve_release

def request(base,path,body=None,actor=None):
    headers={"Content-Type":"application/json"}
    if actor:headers["X-Demo-Actor"]=actor
    req=urllib.request.Request(base+path,data=json.dumps(body).encode() if body is not None else None,headers=headers)
    try:response=urllib.request.urlopen(req,timeout=5)
    except HTTPError as error:response=error
    with response:return response.status,json.loads(response.read()),{key.lower():value for key,value in response.headers.items()}

@contextmanager
def running(target):
    with socket.socket() as sock:sock.bind(("127.0.0.1",0));port=sock.getsockname()[1]
    base=f"http://127.0.0.1:{port}"
    target=Path(target);log=target/("runtime-"+uuid4().hex[:8]+".log")
    with log.open("w") as output:
        process=subprocess.Popen([sys.executable,"-m","tools.release","serve","--target",str(target),"--port",str(port)],cwd=ROOT,stdout=output,stderr=subprocess.STDOUT,env={**os.environ,"PYTHONDONTWRITEBYTECODE":"1"})
        try:
            deadline=time.monotonic()+15
            while time.monotonic()<deadline:
                if process.poll() is not None:raise RuntimeError("Staged runtime exited: "+log.read_text()[-1000:])
                try:
                    if request(base,"/api/health")[0]==200:break
                except (OSError,URLError,TimeoutError):pass
                time.sleep(.1)
            else:raise TimeoutError("Staged runtime did not become healthy")
            yield base
        finally:
            process.terminate()
            try:process.wait(timeout=5)
            except subprocess.TimeoutExpired:process.kill();process.wait(timeout=5)

def journey(base):
    claim_id="REL-"+uuid4().hex[:12]
    status,health,headers=request(base,"/api/health");assert status==200
    if int(health["version"].split(".")[0])>=5:
        assert request(base,"/api/ready")[1]["status"]=="ready"
        assert len(headers["x-request-id"])==32
    status,result,_=request(base,"/api/evaluate",{"plan_id":"commercial_ppo","service":"medical","amount_cents":100000});assert status==200 and result["payout_cents"]==90000
    payload={"claim_id":claim_id,"member_id":"M100","service":"medical","amount_cents":100000}
    assert request(base,"/api/claims",payload,"customer-m100")[0]==201
    assert request(base,"/api/claims",payload,"customer-m100")[0]==409
    assert request(base,"/api/claims/"+claim_id,None,"customer-m200")[0]==403
    assert request(base,"/api/claims/"+claim_id+"/transitions",{"target":"paid"},"finance-demo")[0]==409
    assert request(base,"/api/claims/"+claim_id+"/transitions",{"target":"approved"},"adjuster-demo")[0]==200
    assert request(base,"/api/claims/"+claim_id+"/transitions",{"target":"paid"},"finance-demo")[0]==200
    status,evidence,_=request(base,"/api/claims/"+claim_id,None,"customer-m100")
    assert status==200 and evidence["claim"]["status"]=="paid" and evidence["claim"]["revision"]==3 and len(evidence["events"])==3 and evidence["payment"]["amount_cents"]==90000
    assert request(base,"/api/ai/experiments",{})[0]==400
    return {"version":health["version"],"claim_id":claim_id,"payout_cents":90000,"payment_cents":90000,"events":3,"revision":3,"checks":["health","payout","submit","duplicate_rejected","ownership_rejected","skip_approval_rejected","approve","pay","ledger_and_history","invalid_generation_rejected_without_inference"]}

def rehearse(archive,target,baseline=None):
    target=Path(target).resolve();phases=[];baseline_claim=None
    if baseline:
        prior=stage(baseline,target);activate(target,prior["release_id"])
        with running(target) as base:baseline_claim=journey(base);phases.append({"phase":"baseline",**baseline_claim})
    current=stage(archive,target);activate(target,current["release_id"])
    with running(target) as base:current_claim=journey(base);phases.append({"phase":"new_release",**current_claim})
    if baseline:
        rollback(target)
        with running(target) as base:
            status,evidence,_=request(base,"/api/claims/"+baseline_claim["claim_id"],None,"customer-m100")
            assert status==200 and evidence["payment"]["amount_cents"]==90000
            assert request(base,"/api/claims/"+current_claim["claim_id"],None,"customer-m100")[0]==404
            phases.append({"phase":"rollback","version":request(base,"/api/health")[1]["version"],"previous_state_preserved":True,"new_release_state_isolated":True})
        activate(target,current["release_id"])
        with running(target) as base:
            status,evidence,_=request(base,"/api/claims/"+current_claim["claim_id"],None,"customer-m100")
            assert status==200 and evidence["payment"]["amount_cents"]==90000
            phases.append({"phase":"reactivation","version":request(base,"/api/health")[1]["version"],"new_release_state_preserved":True})
    return {"status":"passed","recorded_at":datetime.now(timezone.utc).isoformat(),"archive":str(Path(archive).resolve()),"active_release":pointer(target)["current"],"rollback_verified":bool(baseline),"phases":phases,"live_model_calls":0,"scope":"Actual staged archives and loopback Waitress HTTP, with separate per-release synthetic state. Pointer changes take effect on next server start; no hot swap or database migration."}

def main():
    parser=argparse.ArgumentParser();parser.add_argument("archive");parser.add_argument("--baseline");parser.add_argument("--target",default=str(ROOT/".local/rehearsal"));parser.add_argument("--output",default=str(ROOT/"artifacts/v5/deployment-rehearsal.json"));args=parser.parse_args()
    record=rehearse(args.archive,args.target,args.baseline);output=Path(args.output);output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(record,indent=2)+"\n");print(json.dumps(record,indent=2))
if __name__=="__main__":main()
