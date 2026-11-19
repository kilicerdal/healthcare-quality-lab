"""Read-only installation diagnostics. Never installs models or changes configuration."""
import argparse,json,platform,sys
from importlib.metadata import version,PackageNotFoundError
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def diagnose(ollama=False):
 checks=[dict(name='python',passed=(3,11)<=sys.version_info[:2]<=(3,13),detail=platform.python_version())]
 for line in (ROOT/'requirements.txt').read_text().splitlines():
  name,wanted=line.split('==')
  try:actual=version(name)
  except PackageNotFoundError:actual=None
  checks.append(dict(name=name,passed=actual==wanted,detail=actual,required=wanted))
 checks.append(dict(name='source_data',passed=all((ROOT/'healthcare_quality/data'/n).is_file() for n in ('plans.json','benefits_v60.json','actors.json')),detail='Required synthetic fixtures'))
 result=dict(ready=all(c['passed'] for c in checks),checks=checks,scope='Read-only runtime diagnostics; browser binaries and optional Ollama are separate capabilities.')
 if ollama:
  from healthcare_quality.ollama_provider import OllamaProvider
  result['optional_ollama']=OllamaProvider('advanced').status()
 return result
def main():
 p=argparse.ArgumentParser();p.add_argument('--ollama',action='store_true');a=p.parse_args();r=diagnose(a.ollama);print(json.dumps(r,indent=2));return 0 if r['ready'] else 1
if __name__=='__main__':raise SystemExit(main())
