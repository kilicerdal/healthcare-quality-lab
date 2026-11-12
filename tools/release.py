"""Local checksummed releases with verified staging, atomic pointers and rollback.
No publishing, shell command generation or database migration occurs here.
"""
import argparse
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path,PurePosixPath
import re
import shutil
import stat
import subprocess
import sys
from tempfile import TemporaryDirectory
from uuid import uuid4
import zipfile
from healthcare_quality import __version__
from tools.fingerprints import ROOT,source_hash

PREFIX="Healthcare Quality Lab/"
EXCLUDED={".git",".venv",".browsers",".local",".pytest_cache","__pycache__","test-results","releases"}
MAX_BYTES=256*1024*1024
class ReleaseError(ValueError):pass

def sha(data):return hashlib.sha256(data).hexdigest()
def sidecar(path):
    path=Path(path)
    if not path.name.endswith("-source.zip"):raise ReleaseError("Archive must end in -source.zip")
    return path.with_name(path.name.replace("-source.zip","-manifest.json"))

def safe_name(name):
    path=PurePosixPath(name)
    if not name or "\\" in name or path.is_absolute() or any(p in (".","..","") for p in name.split("/")) or any(p in EXCLUDED or p.startswith(".env") for p in path.parts) or name=="release-manifest.json":raise ReleaseError("Unsafe or excluded release member")
    return name

def inspect(archive):
    archive=Path(archive)
    if archive.stat().st_size>MAX_BYTES:raise ReleaseError("Compressed archive budget exceeded")
    try:manifest=json.loads(sidecar(archive).read_text())
    except (ValueError,OSError) as error:raise ReleaseError("Missing or malformed sidecar manifest") from error
    if not isinstance(manifest,dict) or not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+",str(manifest.get("version",""))) or not isinstance(manifest.get("files"),dict) or not manifest["files"]:raise ReleaseError("Invalid manifest structure")
    if manifest.get("sha256")!=sha(archive.read_bytes()):raise ReleaseError("Archive checksum mismatch")
    for name,value in manifest["files"].items():
        safe_name(name)
        if not isinstance(value,str) or not re.fullmatch(r"[a-f0-9]{64}",value):raise ReleaseError("Invalid member digest")
    try:
        with zipfile.ZipFile(archive) as z:
            members=z.infolist()
            if len(members)>10000 or sum(m.file_size for m in members)>MAX_BYTES:raise ReleaseError("Expanded archive budget exceeded")
            if len({m.filename for m in members})!=len(members):raise ReleaseError("Duplicate archive members")
            names=set()
            for member in members:
                if not member.filename.startswith(PREFIX) or member.is_dir() or stat.S_ISLNK(member.external_attr>>16):raise ReleaseError("Invalid member root or type")
                name=safe_name(member.filename[len(PREFIX):]);names.add(name)
                if manifest["files"].get(name)!=sha(z.read(member)):raise ReleaseError("Member digest mismatch: "+name)
            if names!=set(manifest["files"]):raise ReleaseError("Archive and manifest member sets differ")
    except (zipfile.BadZipFile,RuntimeError) as error:raise ReleaseError("Invalid ZIP container") from error
    return manifest

def build(output):
    verification=json.loads((ROOT/"artifacts/verification.json").read_text())
    fingerprint=source_hash()
    if verification.get("status")!="passed" or verification.get("source_hash")!=fingerprint or verification.get("version")!=__version__:raise ReleaseError("Fresh passing verification for the current version is required")
    output=Path(output).resolve();output.mkdir(parents=True,exist_ok=True)
    archive=output/("v"+__version__+"-source.zip");manifest_path=sidecar(archive)
    if archive.exists() or manifest_path.exists():raise ReleaseError("Refusing to overwrite an existing release")
    files={};temporary=output/("."+uuid4().hex+".zip")
    try:
        with zipfile.ZipFile(temporary,"w",zipfile.ZIP_DEFLATED) as z:
            for path in sorted(ROOT.rglob("*")):
                rel=path.relative_to(ROOT)
                if not path.is_file() or path.is_symlink() or set(rel.parts)&EXCLUDED or path.name==".DS_Store" or any(p.startswith(".env") for p in rel.parts) or path.resolve().is_relative_to(output):continue
                name=safe_name(str(rel));content=path.read_bytes();files[name]=sha(content);z.writestr(PREFIX+name,content)
        if source_hash()!=fingerprint:raise ReleaseError("Implementation changed during packaging")
        manifest={"version":__version__,"created_at":datetime.now(timezone.utc).isoformat(),"archive":archive.name,"sha256":sha(temporary.read_bytes()),"source_hash":fingerprint,"files":files,"verification":{"tests_passed":verification["tests_passed"],"categories":verification["categories"]},"scope":"Source and synthetic evidence. Local runtime dependencies installed separately. Checksums are integrity evidence, not a signed publisher identity."}
        temporary.rename(archive);manifest_path.write_text(json.dumps(manifest,indent=2)+"\n")
        inspect(archive);return {"archive":str(archive),"manifest":str(manifest_path),"sha256":manifest["sha256"],"files":len(files)}
    finally:
        if temporary.exists():temporary.unlink()

def verify_tree(directory):
    directory=Path(directory)
    try:manifest=json.loads((directory/"release-manifest.json").read_text())
    except (OSError,ValueError) as error:raise ReleaseError("Staged manifest is missing or malformed") from error
    if not isinstance(manifest,dict) or not isinstance(manifest.get("files"),dict) or not manifest["files"]:raise ReleaseError("Invalid staged manifest")
    for name in manifest["files"]:safe_name(name)
    actual=set()
    for path in directory.rglob("*"):
        if path.is_symlink():raise ReleaseError("Staged symlink rejected")
        if not path.is_file() or "__pycache__" in path.parts:continue
        rel=str(path.relative_to(directory))
        if rel=="release-manifest.json":continue
        actual.add(rel)
        if manifest["files"].get(rel)!=sha(path.read_bytes()):raise ReleaseError("Staged file changed: "+rel)
    if actual!=set(manifest["files"]):raise ReleaseError("Staged file set changed")
    return manifest

def release_id(manifest):return "v"+manifest["version"]+"-"+manifest["sha256"][:12]
def resolve_release(target,id):
    if not isinstance(id,str) or not re.fullmatch(r"v[0-9]+\.[0-9]+\.[0-9]+-[a-f0-9]{12}",id):raise ReleaseError("Invalid release ID")
    directory=Path(target)/"releases"/id
    if directory.is_symlink():raise ReleaseError("Release directory cannot be a symlink")
    manifest=verify_tree(directory)
    if release_id(manifest)!=id:raise ReleaseError("Release identity mismatch")
    return directory,manifest

def stage(archive,target):
    manifest=inspect(archive);id=release_id(manifest)
    base=Path(target).resolve()/"releases";base.mkdir(parents=True,exist_ok=True)
    final=base/id
    if final.exists():resolve_release(target,id);return {"release_id":id,"reused":True}
    with TemporaryDirectory(prefix=".stage-",dir=base) as temporary:
        tree=Path(temporary)/"payload";tree.mkdir()
        with zipfile.ZipFile(archive) as z:
            for member in z.infolist():
                if not member.filename.startswith(PREFIX) or member.is_dir() or stat.S_ISLNK(member.external_attr>>16):raise ReleaseError("Archive changed during staging")
                name=safe_name(member.filename[len(PREFIX):]);content=z.read(member)
                if manifest["files"].get(name)!=sha(content):raise ReleaseError("Archive changed during staging")
                path=tree/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(content)
        (tree/"release-manifest.json").write_text(json.dumps(manifest,indent=2)+"\n")
        verify_tree(tree);tree.rename(final)
    return {"release_id":id,"reused":False}

def pointer(target):
    path=Path(target)/"current.json"
    if not path.exists():return {"current":None,"previous":None}
    try:record=json.loads(path.read_text())
    except (OSError,ValueError) as error:raise ReleaseError("Malformed activation pointer") from error
    if not isinstance(record,dict) or not {"current","previous"}<=set(record):raise ReleaseError("Invalid activation pointer")
    return record

def activate(target,id):
    resolve_release(target,id);old=pointer(target)
    if old["current"]==id:return old
    if old["current"]:resolve_release(target,old["current"])
    record={"current":id,"previous":old["current"],"activated_at":datetime.now(timezone.utc).isoformat(),"state_policy":"Separate persistent synthetic database directory per release ID"}
    temporary=Path(target)/(".pointer-"+uuid4().hex+".json")
    try:temporary.write_text(json.dumps(record,indent=2)+"\n");os.replace(temporary,Path(target)/"current.json")
    finally:
        if temporary.exists():temporary.unlink()
    return record

def rollback(target):
    old=pointer(target)
    if not old["previous"]:raise ReleaseError("No previous release available")
    return activate(target,old["previous"])

def serve(target,port):
    if type(port) is not int or not 1024<=port<=65535:raise ReleaseError("Port must be between 1024 and 65535")
    id=pointer(target)["current"]
    directory,manifest=resolve_release(target,id)
    state=(Path(target).resolve()/"state"/id);state.mkdir(parents=True,exist_ok=True)
    # Fixed trusted launcher works with the archived V4 app as well as V5.
    launcher="from pathlib import Path; import os; from waitress import serve; from healthcare_quality.app import create_app; p=Path(os.environ['HQL_STATE_DIR']); app=create_app({'DATABASE':str(p/'claims.sqlite'),'AI_DATABASE':str(p/'ai.sqlite')}); serve(app,host='127.0.0.1',port=int(os.environ['HQL_PORT']),threads=8)"
    env={**os.environ,"PYTHONDONTWRITEBYTECODE":"1","HQL_STATE_DIR":str(state),"HQL_PORT":str(port),"HQL_RELEASE_ID":id}
    os.chdir(directory)
    os.execvpe(sys.executable,[sys.executable,"-c",launcher],env)

def main():
    parser=argparse.ArgumentParser(description=__doc__);commands=parser.add_subparsers(dest="command",required=True)
    p=commands.add_parser("build");p.add_argument("--output",default=str(ROOT/"releases"))
    p=commands.add_parser("inspect");p.add_argument("archive")
    for command in ("stage","activate","rollback","status","serve"):
        p=commands.add_parser(command);p.add_argument("--target",default=str(ROOT/".local/deployments"))
        if command=="stage":p.add_argument("archive")
        if command=="activate":p.add_argument("release_id")
        if command=="serve":p.add_argument("--port",type=int,default=8895)
    args=parser.parse_args()
    try:
        if args.command=="build":result=build(args.output)
        elif args.command=="inspect":
            m=inspect(args.archive);result={"version":m["version"],"sha256":m["sha256"],"files":len(m["files"]),"status":"verified"}
        elif args.command=="stage":result=stage(args.archive,args.target)
        elif args.command=="activate":result=activate(args.target,args.release_id)
        elif args.command=="rollback":result=rollback(args.target)
        elif args.command=="status":result=pointer(args.target)
        else:return serve(args.target,args.port)
        print(json.dumps(result,indent=2));return 0
    except (ReleaseError,OSError,ValueError) as error:print("Release operation failed: "+str(error),file=sys.stderr);return 1
if __name__=="__main__":raise SystemExit(main())
