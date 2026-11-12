import threading
import pytest
from werkzeug.serving import make_server
from healthcare_quality.app import create_app
from tests.support.ai_fixtures import FixtureProvider
pytestmark=[pytest.mark.e2e,pytest.mark.ai,pytest.mark.regression]

@pytest.fixture
def quality_url(tmp_path):
    app=create_app({'TESTING':True,'DATABASE':str(tmp_path/'browser.sqlite'),'AI_PROVIDER':FixtureProvider()})
    server=make_server('127.0.0.1',0,app,threaded=True);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    yield f'http://127.0.0.1:{server.server_port}'
    server.shutdown();thread.join(timeout=5);server.server_close()

def test_comparison_progress_results_and_export(page,quality_url):
    from playwright.sync_api import expect
    page.goto(quality_url+'/#evaluation')
    expect(page.get_by_role('heading',name='Passing tests need a trustworthy oracle.')).to_be_visible()
    page.get_by_role('button',name='Compare with local Ollama').click()
    expect(page.locator('#quality-result')).to_contain_text('comparison · completed',timeout=15000)
    expect(page.locator('#quality-result')).to_contain_text('8/8 requests recorded')
    expect(page.locator('#quality-result')).to_contain_text('Strict pass 0/4')
    with page.expect_download() as download:page.get_by_role('button',name='Export complete JSON').click()
    assert download.value.suggested_filename.startswith('quality-')

def test_rule_retrieval_and_empty_evidence(page,quality_url):
    from playwright.sync_api import expect
    page.goto(quality_url+'/#evaluation');page.get_by_role('button',name='Retrieve rules',exact=True).click()
    expect(page.locator('#retrieval-results')).to_contain_text('WF-004')
    page.locator('#retrieval-query').fill('xyzzyquux');page.get_by_role('button',name='Retrieve rules',exact=True).click()
    expect(page.locator('#retrieval-results')).to_contain_text('Insufficient matching evidence')


@pytest.fixture
def investigation_url(tmp_path):
    from tests.support.ai_fixtures import sample_case,generation_request,review_request
    provider=FixtureProvider(output={"cases":[sample_case(payout=91000)]})
    app=create_app({'TESTING':True,'DATABASE':str(tmp_path/'investigation.sqlite'),'AI_PROVIDER':provider})
    from tests.support.ai_fixtures import historical_failed_experiment
    historical_failed_experiment(app.extensions['studio'].store)
    provider.output={'summary':'Check expected payout','insufficient_evidence':False,'hypotheses':[{'description':'<img src=x onerror=alert(1)> Oracle may be wrong','evidence_ids':['E1'],'rule_ids':['HC-007'],'confidence':'low','next_check':'Recalculate deductible'}]}
    server=make_server('127.0.0.1',0,app,threaded=True);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    yield f'http://127.0.0.1:{server.server_port}'
    server.shutdown();thread.join(timeout=5);server.server_close()


def test_investigation_separates_facts_and_escapes_model_text(page,investigation_url):
    from playwright.sync_api import expect
    page.goto(investigation_url+'/#evaluation')
    expect(page.locator('#investigation-run option')).to_have_count(1)
    page.get_by_role('button',name='Ask local Ollama to investigate').click()
    expect(page.locator('#quality-result')).to_contain_text('investigation · explained')
    expect(page.locator('#quality-result')).to_contain_text('91000')
    expect(page.locator('#quality-result')).to_contain_text('90000')
    expect(page.locator('#quality-result')).to_contain_text('<img src=x onerror=alert(1)>')
    expect(page.locator('#quality-result img')).to_have_count(0)


def test_quality_lab_mobile_view_has_no_page_overflow(page,quality_url):
    from playwright.sync_api import expect
    page.set_viewport_size({'width':390,'height':844});page.goto(quality_url+'/#evaluation')
    expect(page.locator('#quality-form')).to_be_visible()
    assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth')
