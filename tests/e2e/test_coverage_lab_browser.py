import json,threading
from pathlib import Path
import pytest
from werkzeug.serving import make_server
from playwright.sync_api import expect
from healthcare_quality.app import create_app
from tests.support.ai_fixtures import FixtureProvider,sample_case
from tests.unit.test_coverage_lab import approved,body,suggestions
pytestmark=[pytest.mark.e2e,pytest.mark.ai,pytest.mark.regression]
@pytest.fixture
def coverage_url(tmp_path):
    provider=FixtureProvider(suggestions());app=create_app({'TESTING':True,'DATABASE':str(tmp_path/'app.sqlite'),'AI_PROVIDER':provider});lab=app.extensions['coverage_lab'];record=approved(lab,sample_case());lab.studio.provider=provider
    server=make_server('127.0.0.1',0,app,threaded=True);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    yield f'http://127.0.0.1:{server.server_port}',provider
    server.shutdown();thread.join(timeout=5);server.server_close()

def test_dashboard_scores_reviewed_cases_and_exports_evidence(page,coverage_url):
    url,provider=coverage_url;page.goto(url+'/#test-coverage')
    expect(page.get_by_role('heading',name='Coverage backed by evidence.')).to_be_visible()
    expect(page.locator('#coverage-rules')).to_contain_text('WF-006')
    page.locator('#coverage-selections input').first.check();page.get_by_role('button',name='Measure defect detection').click()
    expect(page.locator('#coverage-score-result')).to_contain_text('scored · 1/7')
    with page.expect_download() as info:page.get_by_role('button',name='Export coverage evidence JSON').click()
    r=json.loads(Path(info.value.path()).read_text());assert r['coverage_kind']=='defect_score' and r['baselines'][0]['result']['failed']==0
    assert not provider.calls
    page.screenshot(path=str(Path(__file__).resolve().parents[2]/'artifacts/v5.6/coverage-dashboard.png'),full_page=True)

def test_gap_analysis_explicit_generation_enters_unapproved_studio(page,coverage_url):
    url,provider=coverage_url;page.goto(url+'/#test-coverage');page.get_by_role('button',name='Analyze gaps with Ollama').click()
    expect(page.locator('#coverage-suggestions')).to_contain_text('invalid-zero')
    provider.output={'cases':[sample_case('AI-NEW-GAP')]}
    page.get_by_role('button',name='Generate unapproved gap proposal').click()
    expect(page.locator('#ai-summary')).to_contain_text('Approved cases: 0')
    expect(page.locator('#ai-execute')).to_be_disabled()
    expect(page.locator('#ai-summary')).to_contain_text('Recorded runs: 0')
    assert len(provider.calls)==2


def test_mobile_coverage_dashboard_has_no_page_overflow(page,coverage_url):
    url,provider=coverage_url;page.set_viewport_size({'width':390,'height':844});page.goto(url+'/#test-coverage')
    expect(page.locator('#coverage-counts .card')).to_have_count(4)
    expect(page.locator('#coverage-rules')).to_contain_text('HC-007')
    assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth')
    assert not provider.calls


def test_malformed_saved_draft_does_not_break_browser_inventory(page,coverage_url):
    from tests.support.ai_fixtures import generation_request
    url,provider=coverage_url;provider.output={'cases':[{'id':'AI-BAD','rule_ids':None,'steps':None}]}
    response=page.request.post(url+'/api/ai/experiments',data=generation_request());assert response.status==201
    errors=[];page.on('pageerror',lambda error:errors.append(str(error)));page.goto(url+'/#test-coverage')
    expect(page.locator('#coverage-rules')).to_contain_text('HC-007')
    expect(page.locator('#coverage-counts')).to_contain_text('34')
    assert not errors
