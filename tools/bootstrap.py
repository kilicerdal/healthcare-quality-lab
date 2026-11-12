"""Create a project-local environment; install pinned dependencies and optional Chromium.
Run from the source checkout: python3 -m tools.bootstrap --browser
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import venv
ROOT=Path(__file__).resolve().parents[1]
def plan(runtime_only=False,browser=False):
    python=ROOT/".venv"/("Scripts/python.exe" if os.name=="nt" else "bin/python")
    commands=[[str(python),"-m","pip","install","-r",str(ROOT/("requirements.txt" if runtime_only else "requirements-dev.txt"))]]
    if browser and not runtime_only:commands.append([str(python),"-m","playwright","install","chromium"])
    return python,commands

def main():
    parser=argparse.ArgumentParser();parser.add_argument("--runtime-only",action="store_true");parser.add_argument("--browser",action="store_true");parser.add_argument("--dry-run",action="store_true");args=parser.parse_args()
    if sys.version_info<(3,11):parser.error("Python 3.11 or newer is required; delivery is verified with Python 3.13")
    if args.runtime_only and args.browser:parser.error("Browser installation requires development dependencies")
    python,commands=plan(args.runtime_only,args.browser)
    print(json.dumps({"environment":str(ROOT/".venv"),"commands":commands,"browser_path":str(ROOT/".browsers"),"scope":"Only this project; no Ollama download or global package installation"},indent=2))
    if args.dry_run:return
    if not (ROOT/".venv").exists():venv.EnvBuilder(with_pip=True).create(ROOT/".venv")
    if not python.is_file():parser.error("Existing .venv has no usable Python; inspect it before replacing anything")
    env={**os.environ,"PLAYWRIGHT_BROWSERS_PATH":str(ROOT/".browsers")}
    for command in commands:subprocess.run(command,cwd=ROOT,env=env,check=True)
if __name__=="__main__":main()
