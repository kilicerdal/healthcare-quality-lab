"""Record actual V8 interactions in disposable state; never uses the user's editor."""
import argparse,json,time,threading
from pathlib import Path
from tempfile import TemporaryDirectory
from werkzeug.serving import make_server
from playwright.sync_api import sync_playwright,expect
from healthcare_quality.app import create_app
from tools.fingerprints import source_hash,ROOT

def record(output):
 output=Path(output)
 if output.exists():raise ValueError('Choose a fresh recording directory')
 output.mkdir(parents=True);started=time.monotonic();captions=[]
 def mark(text):captions.append(dict(at=round(time.monotonic()-started,3),text=text))
 with TemporaryDirectory(prefix='hql-v8-record-') as temp:
  app=create_app({'TESTING':True,'DATABASE':str(Path(temp)/'claims.sqlite')});server=make_server('127.0.0.1',0,app,threaded=True);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
  try:
   with sync_playwright() as p:
    browser=p.chromium.launch();context=browser.new_context(viewport={'width':1440,'height':1000},record_video_dir=str(output/'raw'),record_video_size={'width':1440,'height':1000});context.tracing.start(screenshots=True,snapshots=True,sources=True);page=context.new_page()
    page.goto('http://127.0.0.1:'+str(server.server_port)+'/#workbench');expect(page.locator('#wb-packs article')).to_have_count(8);mark('Eight versioned synthetic coverage packs. No inference on page load.');page.screenshot(path=str(output/'workbench-desktop.png'),full_page=True)
    page.locator('#wb-pack').select_option('medicare_advantage');page.locator('#wb-propose').click();expect(page.locator('#wb-status')).to_contain_text('unapproved');mark('Create an authored Medicare Advantage proposal with independently calculated expectations. It remains unapproved.')
    page.locator('#wb-assistant').click();expect(page.locator('#wb-evidence')).to_contain_text('deterministic_evidence_assistant');page.locator('#wb-evidence').scroll_into_view_if_needed();mark('The evidence assistant cites saved facts. It cannot approve or execute.')
    page.locator('#wb-decision').select_option('ready_for_review');page.locator('#wb-route').click();expect(page.locator('#wb-status')).to_contain_text('Routing saved');mark('Assign an owner and route for review. Routing is distinct from approval.')
    page.locator('#wb-open').click();expect(page.locator('#advanced-summary')).to_contain_text('Unapproved');page.locator('#advanced-reviewer').fill('Codex engineering recording');page.locator('#advanced-note').fill('Automated engineering inspection of synthetic rule, independent payout, ledger, history and account expectations; not a human review.');page.locator('#advanced-review').click();expect(page.locator('#advanced-status')).to_contain_text('approved');mark('Explicit engineering inspection approves the current snapshot. No automatic or human review is claimed.')
    page.locator('#advanced-execute').click();expect(page.locator('#advanced-status')).to_contain_text('1 passed, 0 failed');mark('Run the approved case through actual HTTP with fresh disposable state. Full observations match.');page.locator('#advanced-studio').screenshot(path=str(output/'reviewed-http.png'))
    page.locator('[data-page="workbench"]').click();page.locator('#wb-experiment').click();expect(page.locator('#wb-experiment-id')).not_to_have_value('');page.locator('#wb-poll').click();expect(page.locator('#wb-evidence')).to_contain_text('calculator_control');mark('A frozen calculator control makes zero model calls. Raw local AI requires its own explicit selection.');page.locator('#wb-evidence').scroll_into_view_if_needed()
    page.set_viewport_size({'width':390,'height':900});page.screenshot(path=str(output/'workbench-mobile.png'),full_page=True);mark('The same workbench is available on a phone-width layout.');context.tracing.stop(path=str(output/'trace.zip'));video=page.video;context.close();video.save_as(str(output/'healthcare-quality-lab-v8.webm'));browser.close()
  finally:server.shutdown();thread.join(5);server.server_close()
 def stamp(t):
  ms=int(t*1000);return f'{ms//3600000:02}:{ms//60000%60:02}:{ms//1000%60:02}.{ms%1000:03}'
 lines=['WEBVTT','']
 for i,c in enumerate(captions):lines.extend([str(i+1),stamp(c['at'])+' --> '+stamp(captions[i+1]['at'] if i+1<len(captions) else time.monotonic()-started),c['text'],''])
 (output/'healthcare-quality-lab-v8.vtt').write_text('\n'.join(lines));receipt=dict(source_hash=source_hash(),kind='actual_browser_recording',steps=captions,model_calls=0,scope='Actual Chromium interactions in disposable synthetic state; engineering inspection is explicitly labeled, not a human review.');(output/'capture.json').write_text(json.dumps(receipt,indent=2)+'\n');return receipt
if __name__=='__main__':
 import os
 os.environ.setdefault('PLAYWRIGHT_BROWSERS_PATH',str(ROOT/'.browsers'))
 p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args();print(json.dumps(record(a.output),indent=2))
