"""Explicit read-only OSV vulnerability lookup for installed Python distributions.
Network failure is unknown, never a clean security result. No credentials are used.
"""
import argparse,json,urllib.request
from importlib.metadata import distributions
from datetime import datetime,timezone
from pathlib import Path
ENDPOINT='https://api.osv.dev/v1/querybatch'
def installed():return sorted([dict(package=dict(name=d.metadata['Name'],ecosystem='PyPI'),version=d.version) for d in distributions() if d.metadata.get('Name')],key=lambda x:x['package']['name'].lower())
def audit(queries,transport=None):
 def request(queries):
  req=urllib.request.Request(ENDPOINT,data=json.dumps(dict(queries=queries)).encode(),headers={'Content-Type':'application/json','User-Agent':'HealthcareQualityLab/8'})
  with urllib.request.urlopen(req,timeout=30) as r:
   data=r.read(2*1024*1024+1)
  if len(data)>2*1024*1024:raise ValueError('Oversized vulnerability response')
  return json.loads(data)
 try:
  result=(transport or request)(queries)
  if not isinstance(result.get('results'),list) or len(result['results'])!=len(queries):raise ValueError('Incomplete OSV results')
  rows=[dict(**q,vulnerability_ids=sorted(v['id'] for v in r.get('vulns',[]))) for q,r in zip(queries,result['results'])]
  return dict(status='findings' if any(r['vulnerability_ids'] for r in rows) else 'no_known_findings',recorded_at=datetime.now(timezone.utc).isoformat(),endpoint=ENDPOINT,packages=rows,scope='Known OSV advisories for this installed environment at lookup time; not proof of no vulnerabilities or a full security audit.')
 except Exception as e:return dict(status='unknown',error=type(e).__name__,endpoint=ENDPOINT,packages_requested=len(queries),scope='Lookup failed or incomplete; no clean result can be claimed.')
def main():
 p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 if a.output.exists():p.error('Choose fresh evidence path')
 r=audit(installed());a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(dict(status=r['status'],packages=len(r.get('packages',[])),error=r.get('error')),indent=2));return 0 if r['status']=='no_known_findings' else 1
if __name__=='__main__':raise SystemExit(main())
