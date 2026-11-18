"""One trusted owner-dispatched job in an ephemeral container. No host file mounts.
Requires an existing isolated Docker context whose VM can reach local Ollama.
Registration tokens stay in memory/container environment and are never printed.
"""
import argparse,json,os,re,subprocess,time
from pathlib import Path
from uuid import uuid4

REPO='kilicerdal/healthcare-quality-lab'
WORKFLOW='live-advanced-ai.yml'
TASKS={'development':['ADV-01','ADV-02'],'reserved-smoke':['ADV-05','ADV-06'],'reserved-full':['ADV-03','ADV-04','ADV-05','ADV-06','ADV-07','ADV-08']}

def command(args,**kwargs):return subprocess.run(args,check=True,text=True,capture_output=True,**kwargs).stdout

def plan(model,cohort,repeats,correct):
    from healthcare_quality.ai_schema import MODELS
    if model not in MODELS or cohort not in TASKS or type(repeats) is not int or not 1<=repeats<=3 or type(correct) is not bool:raise ValueError('Unknown bounded evaluation option')
    requests=len(TASKS[cohort])*repeats*(2 if correct else 1)
    if requests>24:raise ValueError('At most 24 local model requests, including corrections')
    return dict(model=model,cohort=cohort,repeats=repeats,correct=correct,maximum_requests=requests)

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--context',required=True);p.add_argument('--model',default='qwen2.5-coder:3b');p.add_argument('--cohort',choices=TASKS,default='reserved-smoke');p.add_argument('--repeats',type=int,default=1);p.add_argument('--correct',action='store_true');p.add_argument('--output',type=Path,required=True);a=p.parse_args();configuration=plan(a.model,a.cohort,a.repeats,a.correct)
    if a.output.exists():p.error('Use a fresh receipt output')
    if not re.fullmatch(r'colima-hql-[A-Za-z0-9_-]+',a.context):p.error('Use a dedicated colima-hql-* context')
    owner=json.loads(command(['gh','api','user']))['login']
    if owner!=REPO.split('/')[0]:p.error('Only the trusted repository owner can dispatch this runner')
    head=command(['git','rev-parse','HEAD']).strip();remote=json.loads(command(['gh','api','repos/'+REPO+'/commits/main']))['sha']
    if head!=remote:p.error('Push and review current source before registering an ephemeral runner')
    dirty=command(['git','diff','--name-only']).splitlines()+command(['git','ls-files','--others','--exclude-standard']).splitlines()
    if any(x.startswith(('healthcare_quality/','tests/','tools/','.github/','requirements')) for x in dirty):p.error('Commit source changes before dispatch; unrelated documentation drafts may remain local')
    from healthcare_quality.ollama_provider import OllamaProvider
    status=OllamaProvider('advanced').status()
    if a.model not in {m['name'] for m in status['models']}:p.error('The selected local model is not installed/running')
    docker=['docker','--context',a.context];command(docker+['info','--format','{{.Architecture}}'])
    # Lima's host bridge is verified from this isolated VM before registration.
    bridge='192.168.5.2'
    probe=command(docker+['run','--rm','--entrypoint','python','python:3.13-slim-bookworm','-c',"import urllib.request,json;print(json.load(urllib.request.urlopen('http://192.168.5.2:11434/api/tags',timeout=5))['models'][0]['name'])"])
    nonce=uuid4().hex;name='hql-ollama-'+nonce;label=name;a.output.parent.mkdir(parents=True,exist_ok=True);log=Path('.local/runner-logs')/(name+'.log');log.parent.mkdir(parents=True,exist_ok=True,mode=0o700);run_id=None;runner_process=None
    try:
        with log.open('w') as out:
            log.chmod(0o600)
            subprocess.run(docker+['build','-t','hql-ollama-runner:2.338.2','.github/runner'],stdout=out,stderr=subprocess.STDOUT,check=True,timeout=600)
        before={r['databaseId'] for r in json.loads(command(['gh','run','list','--repo',REPO,'--workflow',WORKFLOW,'--limit','20','--json','databaseId']))}
        command(['gh','workflow','run',WORKFLOW,'--repo',REPO,'--ref','main','-f','runner_label='+label,'-f','model='+a.model,'-f','cohort='+a.cohort,'-f','repeats='+str(a.repeats),'-f','correct='+str(a.correct).lower()])
        for _ in range(30):
            runs=json.loads(command(['gh','run','list','--repo',REPO,'--workflow',WORKFLOW,'--limit','20','--json','databaseId,headSha,event']))
            candidates=[r for r in runs if r['databaseId'] not in before and r['headSha']==head and r['event']=='workflow_dispatch']
            for candidate in candidates:
                jobs=json.loads(command(['gh','api','repos/'+REPO+'/actions/runs/'+str(candidate['databaseId'])+'/jobs']))['jobs']
                if any(label in j['labels'] for j in jobs):run_id=candidate['databaseId'];break
            if run_id:break
            time.sleep(2)
        if not run_id:raise RuntimeError('Dispatched job could not be matched to the unique runner label')
        print(json.dumps(dict(run_id=run_id,url=f'https://github.com/{REPO}/actions/runs/{run_id}',configuration=configuration)),flush=True)
        token=json.loads(command(['gh','api','--method','POST','repos/'+REPO+'/actions/runners/registration-token']))['token']
        env={**os.environ,'HQL_RUNNER_TOKEN':token,'HQL_RUNNER_LABEL':label,'HQL_RUNNER_NAME':name,'HQL_OLLAMA_HOST':bridge}
        with log.open('a') as out:
            runner_process=subprocess.run(docker+['run','--rm','--name',name,'--cap-drop','ALL','--security-opt','no-new-privileges','--env','HQL_RUNNER_TOKEN','--env','HQL_RUNNER_LABEL','--env','HQL_RUNNER_NAME','--env','HQL_OLLAMA_HOST','hql-ollama-runner:2.338.2'],env=env,stdout=out,stderr=subprocess.STDOUT,timeout=1200)
        token=None;env.pop('HQL_RUNNER_TOKEN',None)
        for _ in range(20):
            run=json.loads(command(['gh','run','view',str(run_id),'--repo',REPO,'--json','status,conclusion,headSha,url']))
            if run['status']=='completed':break
            time.sleep(2)
        if run['status']!='completed' or run['conclusion']!='success' or run['headSha']!=head:raise RuntimeError('Live evaluation job did not complete successfully; inspect its GitHub run')
        receipt=dict(status='passed',configuration=configuration,run=run,runner_name=name,container_isolation='Non-root, no host mounts or Docker socket, dropped capabilities, one ephemeral job, unique label, owner/main-only workflow',installed_models=status['models'],runner_process_returncode=runner_process.returncode)
    finally:
        subprocess.run(docker+['rm','--force',name],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        runners=json.loads(command(['gh','api','repos/'+REPO+'/actions/runners']))['runners']
        for r in runners:
            if r['name']==name:command(['gh','api','--method','DELETE','repos/'+REPO+'/actions/runners/'+str(r['id'])])
        if run_id and runner_process is None:subprocess.run(['gh','run','cancel',str(run_id),'--repo',REPO],capture_output=True)
    receipt['runner_removed']=not any(r['name']==name for r in json.loads(command(['gh','api','repos/'+REPO+'/actions/runners']))['runners'])
    a.output.write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(dict(status=receipt['status'],runner_removed=receipt['runner_removed'],url=receipt['run']['url'])))
if __name__=='__main__':main()
