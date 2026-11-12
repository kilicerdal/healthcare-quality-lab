import json,threading
from pathlib import Path
import pytest
from playwright.sync_api import expect
from werkzeug.serving import make_server
from healthcare_quality.app import create_app
from tests.support.ai_fixtures import FixtureProvider,sample_case
pytestmark=[pytest.mark.e2e,pytest.mark.ai,pytest.mark.regression]
ROOT=Path(__file__).resolve().parents[2]

@pytest.fixture
def incomplete_url(tmp_path):
    case=sample_case();del case['steps'][0]['expect']['payout_cents']
    app=create_app({'TESTING':True,'DATABASE':str(tmp_path/'claims.sqlite'),'AI_PROVIDER':FixtureProvider({'cases':[case]})})
    server=make_server('127.0.0.1',0,app,threaded=True);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    yield f'http://127.0.0.1:{server.server_port}'
    server.shutdown();thread.join(timeout=5);server.server_close()


def test_browser_identifies_missing_payout_and_requires_explicit_correction_review(page,incomplete_url):
    page.goto(incomplete_url+'/#ai');page.locator('#ai-count').select_option('1');page.locator('#ai-generate').click()
    expect(page.locator('#ai-cases')).to_contain_text('Approval blocked')
    expect(page.locator('#ai-cases')).to_contain_text('payout_cents')
    expect(page.locator('.ai-approve-case')).to_be_disabled();expect(page.locator('#ai-execute')).to_be_disabled()
    page.locator('#ai-reviewer').fill('Browser assertion reviewer');page.locator('#ai-review-note').fill('Computed payout from the written synthetic deductible')
    page.get_by_text('Inspect or edit case JSON',exact=True).click();editor=page.locator('.case-json');case=json.loads(editor.input_value());case['steps'][0]['expect']['payout_cents']=90000;editor.fill(json.dumps(case))
    page.get_by_role('button',name='Save correction & invalidate approval').click();expect(page.locator('.ai-approve-case')).to_be_enabled()
    page.locator('.ai-approve-case').check();page.locator('#ai-attest').check();page.locator('#ai-save-review').click();expect(page.locator('#ai-execute')).to_be_enabled();page.locator('#ai-execute').click()
    expect(page.locator('#ai-message')).to_contain_text('Run passed');page.screenshot(path=str(ROOT/'artifacts/v5.6/assertion-checklist-browser.png'),full_page=True)
