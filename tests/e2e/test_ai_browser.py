import json
from pathlib import Path
import threading
import pytest
from werkzeug.serving import make_server
from playwright.sync_api import expect
from healthcare_quality.app import create_app
from tests.support.ai_fixtures import FixtureProvider
from tests.support.studio_page import StudioPage

ROOT=Path(__file__).resolve().parents[2]
pytestmark=[pytest.mark.e2e,pytest.mark.ai,pytest.mark.regression]

@pytest.fixture
def live_ai_url(tmp_path):
    app=create_app({'TESTING':True,'DATABASE':str(tmp_path/'claims.sqlite'),'AI_PROVIDER':FixtureProvider()})
    server=make_server('127.0.0.1',0,app,threaded=True)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    yield f'http://127.0.0.1:{server.server_port}'
    server.shutdown();thread.join(timeout=5);server.server_close()


@pytest.mark.smoke
def test_studio_generate_review_execute_and_export_json(page,live_ai_url):
    studio=StudioPage(page,live_ai_url).open().generate()
    expect(page.locator('#ai-execute')).to_be_disabled()
    studio.approve().execute()
    expect(page.locator('#ai-results')).to_contain_text('90000')
    with page.expect_download() as info:page.get_by_role('button',name='Export full experiment JSON').click()
    evidence=json.loads(Path(info.value.path()).read_text())
    assert evidence['raw_generation']['endpoint']=='fixture://no-live-model'
    assert evidence['runs'][0]['status']=='passed'
    assert evidence['approval']['reviewer_label']=='Automated browser fixture reviewer'


@pytest.mark.sanity
def test_editing_expected_result_invalidates_approval_in_browser(page,live_ai_url):
    studio=StudioPage(page,live_ai_url).open().generate().approve()
    page.get_by_text('Inspect or edit case JSON',exact=True).click()
    editor=page.locator('.case-json').first
    data=json.loads(editor.input_value());data['steps'][0]['expect']['payout_cents']=1
    studio.reviewer('Changing fixture oracle to demonstrate review invalidation.')
    editor.fill(json.dumps(data))
    page.get_by_role('button',name='Save correction & invalidate approval').click()
    expect(page.locator('#ai-summary')).to_contain_text('proposed · revision 3')
    expect(page.locator('#ai-execute')).to_be_disabled()
    expect(page.locator('#ai-attest')).not_to_be_checked()


def test_generation_does_not_approve_or_execute_cases(page,live_ai_url):
    StudioPage(page,live_ai_url).open().generate()
    expect(page.locator('#ai-summary')).to_contain_text('Approved cases: 0')
    expect(page.locator('#ai-summary')).to_contain_text('Recorded runs: 0')
    expect(page.locator('#ai-pytest')).to_be_disabled()
    expect(page.locator('.ai-approve-case')).not_to_be_checked()


def test_provider_status_is_explicit_and_not_live_in_this_test(page,live_ai_url):
    StudioPage(page,live_ai_url).open()
    page.get_by_role('button',name='Check Ollama').click()
    expect(page.locator('#ai-provider-status')).to_contain_text('fixture-provider; no live inference')


def test_approved_pytest_download_is_a_trusted_wrapper(page,live_ai_url):
    StudioPage(page,live_ai_url).open().generate().approve()
    with page.expect_download() as info:page.get_by_role('button',name='Export approved pytest wrapper').click()
    text=Path(info.value.path()).read_text()
    assert 'def test_reviewed_ollama_case(case)' in text
    assert '90000' in text and 'run_cases([case])' in text


def test_mobile_studio_can_generate_and_review(page,live_ai_url):
    page.set_viewport_size({'width':390,'height':844})
    StudioPage(page,live_ai_url).open().generate().approve().execute()
    assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth')


def test_reloaded_experiment_preserves_review_and_evidence(page,live_ai_url):
    StudioPage(page,live_ai_url).open().generate().approve().execute()
    page.reload()
    expect(page.locator('#ai-summary')).to_contain_text('Recorded runs: 1')
    expect(page.locator('#ai-execute')).to_be_enabled()
    expect(page.locator('#ai-results')).to_contain_text('1 passed / 0 failed')
