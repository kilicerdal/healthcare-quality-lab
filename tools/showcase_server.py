"""Owned loopback showcase start/status/stop. Recorded replay; zero inference."""
from pathlib import Path
import argparse,hashlib,hmac,json,os,secrets,subprocess,sys,threading,time,urllib.request
from urllib.error import URLError,HTTPError
ROOT=Path(__file__).resolve().parents[1]

def config(state,port):
 if type(port) is not int or not 1024<=port<=65535:raise ValueError('Choose port1024–65535')
 state=Path(state).resolve();return state,port

def fetch(port,path,token=None,timeout=2):
 req=urllib.request.Request(f'http://127.0.0.1:{port}'+path,data=b'{}' if token else None,headers={'X-Showcase-Key':token} if token else {})
 with urllib.request.urlopen(req,timeout=timeout) as response:return json.loads(response.read(65536))

def status(state,port):
 state,port=config(state,port);marker=state/'showcase-server.json'
 try:
  record=json.loads(marker.read_text());remote=fetch(port,'/_showcase/status')
  owned=record['port']==port and hmac.compare_digest(remote['owner_hash'],hashlib.sha256(record['token'].encode()).hexdigest())
  if not owned:return dict(running=False,owned=False,port=port,reason='Port belongs to a different server; no action taken')
  try:ready=fetch(port,'/api/ready').get('status')=='ready'
  except (OSError,ValueError,URLError,TimeoutError):ready=False
  return dict(running=True,owned=True,ready=ready,pid=remote['pid'],version=remote['version'],port=port,url=f'http://127.0.0.1:{port}/#workbench')
 except (OSError,ValueError,KeyError,URLError,TimeoutError):return dict(running=False,owned=False,port=port,reason='No verified showcase server; start to resume preserved state')

def start(state,port):
 state,port=config(state,port);current=status(state,port)
 if current['running']:
  if not current.get('ready'):raise RuntimeError('Owned server is running but not ready; inspect its log or stop it first')
  return current
 state.mkdir(parents=True,exist_ok=True);token=secrets.token_hex(24)
 with (state/'showcase-server.log').open('ab') as log:
  process=subprocess.Popen([sys.executable,'-m','tools.showcase_server','_serve','--state-dir',str(state),'--port',str(port),'--token',token],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
 deadline=time.monotonic()+12
 while time.monotonic()<deadline:
  if process.poll() is not None:raise RuntimeError('Showcase failed to start; see '+str(state/'showcase-server.log'))
  result=status(state,port)
  if result['running'] and result.get('ready'):return result
  time.sleep(.1)
 # Only our just-created child may be terminated; never a PID read from disk.
 process.terminate();process.wait(timeout=5);raise TimeoutError('Showcase readiness timed out; state preserved')

def stop(state,port):
 state,port=config(state,port);current=status(state,port)
 if not current.get('owned'):return current
 record=json.loads((state/'showcase-server.json').read_text());fetch(port,'/_showcase/stop',record['token'])
 deadline=time.monotonic()+8
 while time.monotonic()<deadline:
  if not status(state,port)['running']:return dict(running=False,owned=True,port=port,stopped=True,state_preserved=True)
  time.sleep(.1)
 raise TimeoutError('Shutdown requested; no arbitrary PID was killed. Inspect server log.')

def serve(state,port,token):
 from flask import request,jsonify
 from waitress import create_server
 from healthcare_quality.app import create_app
 from healthcare_quality import __version__
 from healthcare_quality.ai_studio import StudioError
 state,port=config(state,port);state.mkdir(parents=True,exist_ok=True);settings={'DATABASE':str(state/'claims-v2.sqlite')}
 if os.environ.get('HQL_IDENTITIES_FILE'):settings.update(AUTH_MODE='shared',SECRET_KEY=os.environ.get('HQL_SESSION_SECRET'),IDENTITIES=json.loads(Path(os.environ['HQL_IDENTITIES_FILE']).read_text()))
 app=create_app(settings);event=threading.Event()
 # Seed only the original interrupted experiment, with no approvals or new calls.
 artifact=ROOT/'artifacts/v8.2/heldout.json'
 if artifact.is_file():
  record=json.loads(artifact.read_text());lab=app.extensions['expectations_v86']
  try:lab.store.get(record['id'])
  except StudioError as error:
   if error.code!='NOT_FOUND':raise
   record['replay_label']='Recorded interrupted V8.2 evaluation; incomplete; no new inference or approvals';lab.store.create(record)
 @app.get('/_showcase/status')
 def owned_status():return jsonify(pid=os.getpid(),version=__version__,owner_hash=hashlib.sha256(token.encode()).hexdigest())
 @app.post('/_showcase/stop')
 def owned_stop():
  if not hmac.compare_digest(request.headers.get('X-Showcase-Key',''),token):return jsonify(error='FORBIDDEN'),403
  timer=threading.Timer(.15,event.set);timer.daemon=True;timer.start();return jsonify(stopping=True)
 server=create_server(app,host='127.0.0.1',port=port,threads=8)
 marker=state/'showcase-server.json';temp=state/('showcase-'+token+'.tmp');temp.write_text(json.dumps(dict(pid=os.getpid(),port=port,token=token)));os.chmod(temp,0o600);os.replace(temp,marker)
 worker=threading.Thread(target=server.run,daemon=True);worker.start()
 try:
  while not event.wait(.2):
   if not worker.is_alive():break
 finally:server.close();worker.join(3)

def main():
 p=argparse.ArgumentParser();p.add_argument('action',choices=['start','status','stop','_serve']);p.add_argument('--state-dir',type=Path,default=ROOT/'.local/demo-v830');p.add_argument('--port',type=int,default=8902);p.add_argument('--token',help=argparse.SUPPRESS);a=p.parse_args()
 try:
  if a.action=='_serve':
   if not a.token:raise ValueError('Internal ownership token required')
   serve(a.state_dir,a.port,a.token);return 0
  result={'start':start,'status':status,'stop':stop}[a.action](a.state_dir,a.port);print(json.dumps(result,indent=2));return 0
 except (ValueError,OSError,RuntimeError,TimeoutError) as e:p.exit(1,str(e)+'\n')
if __name__=='__main__':raise SystemExit(main())
