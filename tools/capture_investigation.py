"""Capture an actual synthetic investigation UI with an inspectable Playwright trace."""
import argparse,json
from pathlib import Path
from urllib.parse import urlsplit
from playwright.sync_api import sync_playwright,expect
from tools.fingerprints import source_hash
def main():
 p=argparse.ArgumentParser();p.add_argument('--base-url',required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();u=urlsplit(a.base_url)
 if u.scheme!='http' or u.hostname!='127.0.0.1' or not u.port or u.path not in ('','/') or u.query or u.fragment or u.username or a.output.exists():p.error('Use a fresh output and isolated loopback URL')
 a.output.mkdir(parents=True)
 with sync_playwright() as pw:
  b=pw.chromium.launch();c=b.new_context(viewport={'width':1440,'height':1000});c.tracing.start(screenshots=True,snapshots=True,sources=False);page=c.new_page();page.goto(a.base_url+'/#research');page.get_by_role('button',name='Run known-defect investigation').click();expect(page.locator('#evidence-status')).to_contain_text('Restored healthy execution: passed',timeout=20000);page.locator('#evidence-lab').scroll_into_view_if_needed();page.screenshot(path=str(a.output/'investigation.png'));c.tracing.stop(path=str(a.output/'playwright-trace.zip'));c.close();b.close()
 (a.output/'capture.json').write_text(json.dumps(dict(source_hash=source_hash(),passed=True,live_model_calls=0,scope='Actual isolated synthetic known-defect UI, including request/response browser trace; no new model inference'),indent=2)+'\n')
if __name__=='__main__':main()
