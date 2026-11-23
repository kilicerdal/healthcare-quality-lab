"""One-command saved showcase; inference is never implicit."""
import argparse,json,subprocess,sys
from pathlib import Path
from tools.showcase_server import start,stop
from healthcare_quality import __version__
from tools.reliability_study import save
ROOT=Path(__file__).resolve().parents[1]
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--build',type=Path,help='Explicitly score saved study and run disposable HTTP journeys; zero inference');ap.add_argument('--fault-demo',action='store_true',help='Explicit known fault in an isolated subprocess');a=ap.parse_args()
 if a.build:
  from healthcare_quality.reliability_evidence import build,seal
  result=seal(build(a.build));save(ROOT/'artifacts/v8.7/dashboard.json',result);print('Saved integrity-sealed dashboard; zero model calls.');return 0
 if a.fault_demo:
  target=ROOT/'artifacts/v8.7/known-fault-demo.json'
  result=subprocess.run([sys.executable,'-m','tools.investigate','--output',str(target)],cwd=ROOT,timeout=60)
  return result.returncode
 result=start(ROOT/'.local/demo-v830',8902)
 if result.get('version')!=__version__:
  stop(ROOT/'.local/demo-v830',8902);result=start(ROOT/'.local/demo-v830',8902)
 result['url']='http://127.0.0.1:8902/reliability';result['live_model_calls']=0;print(json.dumps(result,indent=2));return 0
if __name__=='__main__':raise SystemExit(main())
