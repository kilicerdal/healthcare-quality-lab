import threading,json
import pytest
from werkzeug.serving import make_server
from playwright.sync_api import expect
from healthcare_quality.app import create_app
from tests.support.ai_fixtures import FixtureProvider
pytestmark=[pytest.mark.e2e,pytest.mark.regression]
@pytest.fixture
def research_url(tmp_path):
    provider=FixtureProvider();app=create_app(dict(TESTING=True,DATABASE=str(tmp_path/'claims.sqlite'),AI_PROVIDER=provider));server=make_server('127.0.0.1',0,app,threaded=True);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    yield f'http://127.0.0.1:{server.server_port}',provider
    server.shutdown();thread.join(5);server.server_close()

def test_research_readonly_accessible_and_mobile(page,research_url):
    url,provider=research_url;errors=[];page.on('pageerror',lambda e:errors.append(str(e)));page.set_viewport_size(dict(width=390,height=844));page.goto(url+'/#research');expect(page.get_by_role('heading',name='Engineering evidence hub.')).to_be_visible();expect(page.locator('#research-tasks input')).to_have_count(8)
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    assert page.locator('#page-research input:visible, #page-research select:visible, #page-research textarea:visible').evaluate_all('(els)=>els.every(e=>e.labels.length>0 || e.hasAttribute("aria-label"))')
    page.get_by_role('button',name='Refresh engineering evidence').focus();expect(page.get_by_role('button',name='Refresh engineering evidence')).to_be_focused();assert not provider.calls and not errors

def test_advanced_benefits_browser_payment_adjustment_reversal(page,research_url):
    url,provider=research_url;page.goto(url+'/#research');page.get_by_role('button',name='Adjudicate synthetic lines').click();expect(page.locator('#benefit-result')).to_contain_text('71200')
    page.locator('#benefit-actor').select_option('finance-demo');page.get_by_role('button',name='Perform explicit lifecycle operation').click();expect(page.locator('#benefit-result')).to_contain_text('"state": "paid"')
    page.locator('#benefit-actor').select_option('adjuster-demo');page.locator('#benefit-action').select_option('adjust');page.locator('#benefit-operation').fill(json.dumps(dict(expected_revision=2,note='Correct synthetic allowed amount',lines=[dict(id='L1',service='medical',allowed_cents=50000)])));page.get_by_role('button',name='Perform explicit lifecycle operation').click();expect(page.locator('#benefit-result')).to_contain_text('31200')
    page.locator('#benefit-actor').select_option('finance-demo');page.locator('#benefit-action').select_option('reverse');page.locator('#benefit-operation').fill(json.dumps(dict(expected_revision=3,note='Reverse corrected payment')));page.get_by_role('button',name='Perform explicit lifecycle operation').click();expect(page.locator('#benefit-result')).to_contain_text('"state": "reversed"');assert not provider.calls

def test_changed_rule_followup_is_unapproved(page,research_url):
    url,provider=research_url;page.goto(url+'/#research');page.get_by_role('button',name='Inspect linked tests').click();expect(page.locator('#research-impact-result')).to_contain_text('HC-007');page.get_by_role('button',name='Ask Ollama for an unapproved follow-up test').click();expect(page.locator('#ai-summary')).to_contain_text('Approved cases: 0');expect(page.locator('#ai-execute')).to_be_disabled();assert len(provider.calls)==1


@pytest.mark.parametrize('layout',['desktop','mobile'])
def test_selected_visual_layout_contracts(page,research_url,layout):
    from pathlib import Path
    contract=json.loads((Path(__file__).resolve().parents[1]/'data/layout_v62.json').read_text())[layout];url,_=research_url;page.set_viewport_size(dict(width=contract['width'],height=contract['height']));page.goto(url+'/#research');heading=page.get_by_role('heading',name='Engineering evidence hub.');expect(heading).to_be_visible();box=heading.bounding_box()
    assert contract['heading_x'][0]<=box['x']<=contract['heading_x'][1]
    assert contract['heading_width'][0]<=box['width']<=contract['heading_width'][1]
    if 'heading_y' in contract:assert contract['heading_y'][0]<=box['y']<=contract['heading_y'][1]
    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
    page.screenshot(path=str(Path(__file__).resolve().parents[2]/('artifacts/v6.7/layout-'+layout+'.png')),animations='disabled')

def test_reviewed_snapshot_can_use_real_http_from_studio(page,research_url):
    from tests.support.studio_page import StudioPage
    url,_=research_url;studio=StudioPage(page,url).open().generate().approve();page.locator('#ai-transport').select_option('http');studio.execute();expect(page.locator('#ai-results')).to_contain_text('loopback HTTP listener')
