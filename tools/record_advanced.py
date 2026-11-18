"""Record real authored UI actions plus separately labeled historical model evidence."""
import argparse,json,time
from pathlib import Path
from urllib.parse import urlsplit
from playwright.sync_api import sync_playwright,expect
from tools.fingerprints import source_hash

def stamp(seconds):
    ms=round(seconds*1000);return f'{ms//3600000:02}:{ms//60000%60:02}:{ms//1000%60:02}.{ms%1000:03}'

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--base-url',default='http://127.0.0.1:8899');p.add_argument('--output',type=Path,required=True);a=p.parse_args();u=urlsplit(a.base_url)
    if u.scheme!='http' or u.hostname!='127.0.0.1' or not u.port or u.path not in ('','/') or u.query or u.fragment or u.username:p.error('Use an isolated loopback HTTP application')
    if a.output.exists():p.error('Choose a new recording directory')
    a.output.mkdir(parents=True);captions=[];scenes=[]
    with sync_playwright() as pw:
        browser=pw.chromium.launch();ctx=browser.new_context(viewport={'width':1440,'height':1000},record_video_dir=str(a.output),record_video_size={'width':1440,'height':1000});page=ctx.new_page();started=time.monotonic()
        def caption(text):
            page.evaluate("""text=>{let el=document.getElementById('capture-caption');if(!el){el=document.createElement('div');el.id='capture-caption';Object.assign(el.style,{position:'fixed',bottom:'14px',left:'3%',width:'94%',padding:'16px',background:'rgba(18,51,36,.96)',color:'white',fontSize:'22px',lineHeight:'1.4',zIndex:99999,borderRadius:'8px',pointerEvents:'none'});document.body.append(el);}el.textContent=text;}""",text)
        def pause(text,seconds=7):
            at=time.monotonic()-started;caption(text);page.wait_for_timeout(seconds*1000);captions.append((at,time.monotonic()-started,text))
        page.goto(a.base_url+'/#research');expect(page.locator('#advanced-studio')).to_be_visible()
        pause('Healthcare Quality Lab: bounded AI proposals, independent financial checks and explicit review. Synthetic insurance rules only. No model is called during this recording.')
        page.get_by_role('button',name='Load an authored adjustment control').click();expect(page.locator('#advanced-summary')).to_contain_text('Independent checks passed');page.locator('#advanced-summary').scroll_into_view_if_needed()
        pause('This is an authored control, not a new AI answer. It submits, pays, adjusts and reverses a claim, checking money, ledger, history and accumulators.')
        page.locator('#advanced-note').fill('Recorded authored control: independently inspected 71200-cent payout, 31200-cent adjustment and zero reversal ledger/accumulators.');page.get_by_role('button',name='Approve inspected snapshot').click();expect(page.locator('#advanced-summary')).to_contain_text('Snapshot approved')
        pause('Approval binds the inspected case, rule contract and source hashes. A later code or scenario change invalidates the approval.')
        page.get_by_role('button',name='Execute approved case through HTTP').click();expect(page.locator('#advanced-status')).to_contain_text('Execution: 1 passed, 0 failed',timeout=15000);page.locator('#advanced-status').scroll_into_view_if_needed()
        pause('The approved case passed through actual HTTP in fresh isolated stores. It did not change the interactive claim ledger.');scenes.append(dict(scene='authored_advanced_http',passed=True))
        page.locator('#advanced-evaluation-refresh').click();page.locator('#advanced-evaluations').scroll_into_view_if_needed()
        pause('These are earlier actual local-model measurements, labeled separately. Raw eligibility and reference-assisted correction are different results; a completed job does not imply a correct model.',10)
        page.locator('#integration-scenario').select_option('lost_ack');page.get_by_role('button',name='Run isolated integration rehearsal').click();expect(page.locator('#integration-status')).to_contain_text('lost_ack: passed',timeout=15000);page.locator('#integration-status').scroll_into_view_if_needed()
        pause('The peer committed a synthetic payment but its acknowledgement timed out. Reconciliation queried the original key: one peer payment, one local ledger entry.',10);scenes.append(dict(scene='lost_ack_reconciliation',passed=True))
        page.locator('#integration-scenario').select_option('webhook_replay');page.get_by_role('button',name='Run isolated integration rehearsal').click();expect(page.locator('#integration-status')).to_contain_text('webhook_replay: passed',timeout=15000);page.locator('#integration-status').scroll_into_view_if_needed()
        pause('Duplicate and out-of-order webhooks are deduplicated or ignored. A changed payload is rejected. Webhooks signal reconciliation; they never authorize extra money.',10);scenes.append(dict(scene='webhook_replay',passed=True))
        page.goto(a.base_url+'/#showcase');expect(page.locator('#showcase-ready')).to_have_text('Ready');pause('Inspect the verified release, checksummed source archive and GitHub Actions receipts. This portfolio is a synthetic engineering lab, not a production payer or a healthcare compliance certification.',10)
        video=page.video;path=video.path();ctx.close();browser.close()
    target=a.output/'healthcare-quality-lab-v6.7.webm';Path(path).rename(target)
    (a.output/'healthcare-quality-lab-v6.7.vtt').write_text('WEBVTT\n\n'+'\n\n'.join(stamp(x)+' --> '+stamp(y)+'\n'+t for x,y,t in captions)+'\n')
    receipt=dict(source_hash=source_hash(),scenes=scenes,duration_seconds=round(captions[-1][1],2),live_model_calls=0,scope='Actual headless Chromium authored UI execution. Captions distinguish authored controls from historical live model measurements. No voice narration or new AI generation in this capture.')
    (a.output/'capture.json').write_text(json.dumps(receipt,indent=2)+'\n');print(target)
if __name__=='__main__':main()
