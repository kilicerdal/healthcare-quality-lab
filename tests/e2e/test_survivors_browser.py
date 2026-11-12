import threading
import pytest
from playwright.sync_api import expect
from werkzeug.serving import make_server
from healthcare_quality.app import create_app
from tests.unit.test_coverage_lab import approved,body
from tests.unit.test_survivors import baseline
from tests.support.ai_fixtures import FixtureProvider
from tests.support.survivor_fixtures import case
pytestmark=[pytest.mark.e2e,pytest.mark.ai,pytest.mark.regression]
@pytest.fixture
def survivor_url(tmp_path):
    app=create_app({'TESTING':True,'DATABASE':str(tmp_path/'app.sqlite'),'AI_PROVIDER':FixtureProvider()});lab=app.extensions['coverage_lab'];before=baseline(lab);provider=FixtureProvider({'cases':[case()]});lab.studio.provider=provider
    server=make_server('127.0.0.1',0,app,threaded=True);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    yield f'http://127.0.0.1:{server.server_port}',lab,before,provider
    server.shutdown();thread.join(timeout=5);server.server_close()

def test_showcase_targets_survivors_without_automatic_approval(page,survivor_url):
    url,lab,before,provider=survivor_url;errors=[];page.on('pageerror',lambda e:errors.append(str(e)));page.goto(url+'/#test-coverage')
    expect(page.locator('#coverage-score-headline')).to_contain_text('2/12')
    expect(page.locator('#coverage-fault-pills')).to_contain_text('eval-eligibility · survived')
    expect(page.locator('#coverage-counts')).to_contain_text('Equivalent inputs and identical expectations counted once')
    page.get_by_role('button',name='Plan tests for surviving faults').click();expect(page.locator('#coverage-survivor-plans')).to_contain_text('evaluator · 7 planned steps')
    assert not provider.calls
    page.get_by_role('button',name='Generate evaluator survivor proposal').click()
    expect(page.locator('#ai-summary')).to_contain_text('Planned sequence and source citations match')
    expect(page.locator('#ai-summary')).to_contain_text('Approved cases: 0');expect(page.locator('#ai-execute')).to_be_disabled()
    assert len(provider.calls)==1 and not errors

def test_before_after_comparison_and_mobile_layout(page,survivor_url):
    url,lab,before,provider=survivor_url;after=lab.score(body(approved(lab,case()),approved(lab,case('workflow'))));page.goto(url+'/#test-coverage')
    expect(page.locator('#coverage-score-headline')).to_contain_text('12/12')
    page.locator('#coverage-before').select_option(before['id']);page.locator('#coverage-after').select_option(after['id']);page.get_by_role('button',name='Compare reviewed scores').click()
    expect(page.locator('#coverage-comparison')).to_contain_text('2/12 → 12/12')
    expect(page.locator('#coverage-comparison')).to_contain_text('10 newly detected · 0 regressed')
    page.set_viewport_size({'width':390,'height':844});assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
