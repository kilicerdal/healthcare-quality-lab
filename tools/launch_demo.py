"""One-command fresh-checkout demo: local runtime bootstrap, labeled replay and loopback serve."""
import argparse,json,os,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def commands(state,port):
    if not 1024<=port<=65535:raise ValueError('Choose a loopback port between 1024 and 65535')
    state=Path(state).resolve()
    if state.exists() and any(state.iterdir()):raise ValueError('Choose fresh demo state; existing data is never overwritten')
    python=ROOT/'.venv'/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
    return [[sys.executable,'-m','tools.bootstrap','--runtime-only'],[str(python),'-m','tools.fresh_demo','--state-dir',str(state),'--port',str(port)]]
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--state-dir',type=Path,required=True);p.add_argument('--port',type=int,default=8897);p.add_argument('--dry-run',action='store_true');a=p.parse_args()
    try:plan=commands(a.state_dir,a.port)
    except ValueError as e:p.error(str(e))
    if a.dry_run:print(json.dumps(plan,indent=2))
    else:
        for command in plan:subprocess.run(command,cwd=ROOT,check=True)
