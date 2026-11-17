"""Record actual authored UI execution in a separately started local demo. No inference."""
import argparse
import json
from pathlib import Path
import time
from playwright.sync_api import sync_playwright, expect

SCENES=[('A plausible AI expectation is blocked','An authored expectation ignores the deductible. The independent check blocks it; a corrected control detects the seeded defect.'),
        ('Two payment requests, one ledger entry','Two actual concurrent HTTP requests return 200 and 409. One payment and three committed events remain.'),
        ('Worker interruption rolls back partial payment','An actual worker exits before commit. Uncommitted changes roll back; retry pays once and replay is rejected.'),
        ('A requirement change invalidates reviewed evidence','An isolated requirement change makes the review stale. The real Studio execution guard blocks it.')]

def stamp(seconds):
    millis=round(seconds*1000);return f'{millis//3600000:02}:{millis//60000%60:02}:{millis//1000%60:02}.{millis%1000:03}'

def main():
    p=argparse.ArgumentParser();p.add_argument('--base-url',default='http://127.0.0.1:8895');p.add_argument('--output',type=Path,required=True);args=p.parse_args()
    from urllib.parse import urlsplit
    u=urlsplit(args.base_url)
    if u.scheme!='http' or u.hostname!='127.0.0.1' or u.path not in ('','/') or u.query or u.fragment:p.error('Use a loopback HTTP base URL only')
    if args.output.exists():p.error('Use a new capture directory')
    args.output.mkdir(parents=True)
    captions=[]
    with sync_playwright() as pw:
        browser=pw.chromium.launch();ctx=browser.new_context(viewport={'width':1440,'height':1000},record_video_dir=str(args.output),record_video_size={'width':1440,'height':1000})
        page=ctx.new_page();page.goto(args.base_url+'/#proof')
        def caption(text):
            page.evaluate("""text=>{let el=document.getElementById('recording-caption');if(!el){el=document.createElement('div');el.id='recording-caption';Object.assign(el.style,{position:'fixed',bottom:'16px',left:'4%',width:'92%',padding:'14px',background:'rgba(0,0,0,.88)',color:'white',fontSize:'20px',lineHeight:'1.4',zIndex:'99999',borderRadius:'8px',boxSizing:'border-box',pointerEvents:'none'});document.body.append(el);}el.textContent=text;}""",text)
        caption('Synthetic healthcare quality engineering: authored controls, real local execution and independently checked expectations. No model is called in this recording.')
        started=time.monotonic();page.wait_for_timeout(6000)
        captions.append((0,time.monotonic()-started,'Synthetic healthcare quality engineering: authored controls, real local execution and independently checked expectations. No model is called in this recording.'))
        evidence=[]
        for title,caption_text in SCENES:
            at=time.monotonic()-started;caption(caption_text);page.get_by_role('button',name=title,exact=True).click();expect(page.locator('#proof-status')).to_contain_text('passed',timeout=20000);page.wait_for_timeout(10000)
            page.locator('#proof-investigation').scroll_into_view_if_needed();page.wait_for_timeout(10000)
            captions.append((at,time.monotonic()-started,caption_text));evidence.append({'scenario':title,'status':page.locator('#proof-status').inner_text()})
            page.locator('#proof-scenarios').scroll_into_view_if_needed()
        at=time.monotonic()-started;caption('Provider results are separately recorded live experiments. Inspect failures, repeatability and costs. Eligible proposals are not human-approved.');page.locator('#proof-comparison').scroll_into_view_if_needed();page.wait_for_timeout(12000);captions.append((at,time.monotonic()-started,'Provider results are separately recorded live experiments. Inspect failures, repeatability and costs. Eligible proposals are not human-approved. Small cohorts do not establish general accuracy.'))
        video=page.video;await_path=video.path();ctx.close();browser.close()
    target=args.output/'healthcare-showcase.webm';Path(await_path).rename(target)
    (args.output/'healthcare-showcase.vtt').write_text('WEBVTT\n\n'+'\n\n'.join(stamp(a)+' --> '+stamp(b)+'\n'+text for a,b,text in captions)+'\n')
    (args.output/'capture.json').write_text(json.dumps({'scenes':evidence,'live_model_calls':0,'scope':'Actual authored UI execution; captions describe observed scenes, no narration. Provider measurements are retained separately.'},indent=2)+'\n')
    print(target)

if __name__=='__main__':main()
