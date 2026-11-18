"""Create local hashed shared-lab accounts interactively; never put passwords in commands."""
import argparse,getpass,json,os,tempfile
from pathlib import Path
from werkzeug.security import generate_password_hash
p=argparse.ArgumentParser();p.add_argument('--file',type=Path,required=True);p.add_argument('--username',required=True);p.add_argument('--roles',nargs='+',choices=['analyst','reviewer','auditor','admin','customer','finance','adjuster'],required=True);p.add_argument('--actor',required=True);a=p.parse_args()
from healthcare_quality.workflow import ACTORS
if a.actor not in {x['id'] for x in ACTORS}:p.error('Unknown teaching actor')
users=json.loads(a.file.read_text()) if a.file.exists() else {}
if a.username in users:p.error('Account already exists; never overwrite silently')
password=getpass.getpass('New password (at least 12 characters): ')
if len(password)<12 or password!=getpass.getpass('Repeat password: '):p.error('Password confirmation failed')
users[a.username]=dict(password_hash=generate_password_hash(password),roles=a.roles,actor_id=a.actor);a.file.parent.mkdir(parents=True,exist_ok=True)
fd,name=tempfile.mkstemp(dir=a.file.parent)
try:
 os.fchmod(fd,0o600)
 with os.fdopen(fd,'w') as f:json.dump(users,f,indent=2)
 os.replace(name,a.file)
finally:
 if os.path.exists(name):os.unlink(name)
print('Hashed account saved; no password printed.')
