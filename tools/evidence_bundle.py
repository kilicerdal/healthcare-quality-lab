"""Portable evidence packages with member hashes and implementation provenance."""
import argparse,json,hashlib,zipfile
from pathlib import Path,PurePosixPath
from healthcare_quality import __version__
from tools.fingerprints import ROOT,source_hash

def sha(data):return hashlib.sha256(data).hexdigest()
def build(paths,output):
 output=Path(output)
 if output.exists():raise ValueError('Evidence packages are immutable; choose a new path')
 files={}
 for p in paths:
  if Path(p).is_symlink():raise ValueError('Symlink evidence is not accepted')
  p=Path(p).resolve()
  if not p.is_file() or p.is_symlink() or not p.is_relative_to(ROOT) or p.suffix not in ('.json','.md','.html','.xml','.txt','.png','.webm','.vtt'):raise ValueError('Select explicit project evidence files')
  name=str(p.relative_to(ROOT))
  if name.split('/')[0] not in ('artifacts','docs'):raise ValueError('Only public artifacts/docs evidence is permitted')
  if name in files:raise ValueError('Duplicate evidence member')
  files[name]=p.read_bytes()
 if not files:raise ValueError('An evidence bundle cannot be empty')
 manifest=dict(version=__version__,source_hash=source_hash(),files={n:sha(b) for n,b in files.items()},scope='Selected evidence integrity only; individual receipts retain their own source fingerprints. Not a signature or automatic release approval.')
 output.parent.mkdir(parents=True,exist_ok=True)
 with zipfile.ZipFile(output,'x',zipfile.ZIP_DEFLATED) as z:
  for n,b in sorted(files.items()):z.writestr(n,b)
  z.writestr('evidence-manifest.json',json.dumps(manifest,indent=2))
 verify(output);return manifest

def verify(path):
 with zipfile.ZipFile(path) as z:
  members=z.infolist()
  if len(members)>1000 or sum(m.file_size for m in members)>128*1024*1024:raise ValueError('Evidence budget exceeded')
  names=[m.filename for m in members]
  if len(set(names))!=len(names):raise ValueError('Duplicate package members')
  for n in names:
   p=PurePosixPath(n)
   if '\\' in n or p.is_absolute() or any(x in ('','..','.') for x in n.split('/')):raise ValueError('Unsafe evidence member')
  manifest=json.loads(z.read('evidence-manifest.json'))
  if set(names)!=set(manifest['files'])|{'evidence-manifest.json'}:raise ValueError('Manifest member mismatch')
  for n,h in manifest['files'].items():
   if sha(z.read(n))!=h:raise ValueError('Evidence digest mismatch: '+n)
 return manifest

def compare(old,new):
 a=verify(old);b=verify(new);return dict(old_source=a['source_hash'],new_source=b['source_hash'],added=sorted(set(b['files'])-set(a['files'])),removed=sorted(set(a['files'])-set(b['files'])),changed=sorted(n for n in a['files'].keys()&b['files'].keys() if a['files'][n]!=b['files'][n]),scope='File-level evidence comparison; does not claim comparable model performance or equal test budgets.')
def main():
 p=argparse.ArgumentParser();sub=p.add_subparsers(dest='action',required=True);b=sub.add_parser('build');b.add_argument('--output',type=Path,required=True);b.add_argument('paths',nargs='+',type=Path);v=sub.add_parser('verify');v.add_argument('path',type=Path);c=sub.add_parser('compare');c.add_argument('old',type=Path);c.add_argument('new',type=Path);a=p.parse_args();r=build(a.paths,a.output) if a.action=='build' else verify(a.path) if a.action=='verify' else compare(a.old,a.new);print(json.dumps(r,indent=2))
if __name__=='__main__':main()
