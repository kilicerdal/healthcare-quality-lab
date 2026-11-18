"""Start a fresh reproducible local showcase without touching interactive project state."""
from pathlib import Path
import argparse,subprocess,sys
from tools.showcase import seed
p=argparse.ArgumentParser();p.add_argument('--state-dir',type=Path,required=True);p.add_argument('--port',type=int,default=8897);a=p.parse_args();output=a.state_dir.parent/(a.state_dir.name+'-manifest.json')
seed(a.state_dir,output);raise SystemExit(subprocess.call([sys.executable,'-m','tools.serve','--state-dir',str(a.state_dir),'--port',str(a.port)]))
