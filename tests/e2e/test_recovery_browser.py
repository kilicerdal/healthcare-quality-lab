import threading
from pathlib import Path
import pytest
from playwright.sync_api import expect
from werkzeug.serving import make_server
from healthcare_quality.app import create_app
from tests.support.ai_fixtures import FixtureProvider,generation_request,review_request
pytestmark=[pytest.mark.e2e,pytest.mark.ai,pytest.mark.regression]
ROOT=Path(__file__).resolve().parents[2]

@pytest.fixture
def recovery_server(tmp_path):
    app=create_app({'TESTING':True,'DATABASE':str(tmp_path/'claims.sqlite'),'AI_PROVIDER':FixtureProvider()})
    server=make_server('127.0.0.1',0,app,threaded=True);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    yield f'http://127.0.0.1:{server.server_port}',app.extensions['studio']
    server.shutdown();thread.join(timeout=5);server.server_close()

def seed(studio,state):
    record=studio.generate(generation_request())
    if state=='running':record=studio.review(record['id'],review_request(record))
    with studio.store.transaction() as db:record['state']=state;studio.store.save(db,record)
    return record


def test_browser_can_retry_interrupted_generation_without_approving_it(page,recovery_server):
    url,studio=recovery_server;parent=seed(studio,'generating')
    page.goto(url+'/#ai');expect(page.locator('#ai-recovery-note')).to_contain_text('Interrupted generation preserved')
    expect(page.locator('#ai-retry')).to_be_visible();expect(page.locator('#ai-execute')).to_be_disabled()
    page.locator('#ai-reviewer').fill('Browser recovery operator');page.locator('#ai-review-note').fill('Explicitly retry interrupted generation')
    page.locator('#ai-retry').click();expect(page.locator('#ai-message')).to_contain_text('Explicit retry saved as a new experiment')
    child_id=page.locator('#ai-experiment').input_value();assert child_id!=parent['id']
    child=page.request.get(url+'/api/ai/experiments/'+child_id).json()
    assert child['retry_of']==parent['id'] and child['approval'] is None and child['runs']==[]
    expect(page.locator('#ai-retry')).to_be_hidden();expect(page.locator('#ai-execute')).to_be_disabled()
    assert studio.store.get(parent['id'])['state']=='interrupted'


def test_browser_requires_fresh_review_after_interrupted_execution(page,recovery_server):
    url,studio=recovery_server;record=seed(studio,'running')
    page.goto(url+'/#ai');expect(page.locator('#ai-recovery-note')).to_contain_text('Prior approval was invalidated')
    expect(page.locator('#ai-execute')).to_be_disabled();expect(page.locator('#ai-retry')).to_be_hidden()
    page.locator('.ai-approve-case').check();page.locator('#ai-reviewer').fill('Browser recovery operator');page.locator('#ai-review-note').fill('Reviewed preserved expectations again after interruption');page.locator('#ai-attest').check();page.locator('#ai-save-review').click()
    expect(page.locator('#ai-execute')).to_be_enabled();page.locator('#ai-execute').click()
    expect(page.locator('#ai-message')).to_contain_text('Run passed')
    page.screenshot(path=str(ROOT/'artifacts/v6.7/recovered-execution-browser.png'),full_page=True)
    assert studio.store.get(record['id'])['runs'][-1]['status']=='passed'


def test_browser_exact_rule_id_does_not_show_unrelated_sources(page,recovery_server):
    url,_=recovery_server;page.goto(url+'/#evaluation');page.locator('#retrieval-query').fill('HC-007');page.get_by_role('button',name='Retrieve rules',exact=True).click()
    expect(page.locator('#retrieval-results details')).to_have_count(1);expect(page.locator('#retrieval-results summary')).to_contain_text('HC-007')
    page.locator('#retrieval-query').fill('HC-999');page.get_by_role('button',name='Retrieve rules',exact=True).click();expect(page.locator('#retrieval-results')).to_contain_text('Insufficient matching evidence')
