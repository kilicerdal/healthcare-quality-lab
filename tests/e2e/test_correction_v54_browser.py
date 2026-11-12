import threading
import pytest
from werkzeug.serving import make_server
from playwright.sync_api import expect
from healthcare_quality.app import create_app
from tests.support.ai_fixtures import FixtureProvider,sample_case
from tests.support.studio_page import StudioPage
pytestmark=[pytest.mark.e2e,pytest.mark.ai,pytest.mark.regression]
def test_two_wrong_ai_attempts_then_confirmed_reference_repair(page,tmp_path):
    provider=FixtureProvider({'cases':[sample_case(amount=10001,payout=9001)]})
    app=create_app({'TESTING':True,'DATABASE':str(tmp_path/'browser.sqlite'),'AI_PROVIDER':provider});server=make_server('127.0.0.1',0,app,threaded=True);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    try:
        studio=StudioPage(page,f'http://127.0.0.1:{server.server_port}').open().generate()
        studio.reviewer('Explicit correction attempts against the synthetic reference.')
        for attempt in (1,2):
            page.get_by_role('button',name='Correct expectations with Ollama').click()
            expect(page.locator('#ai-summary')).to_contain_text(f'AI correction attempts: {attempt}/2')
            expect(page.locator('.ai-approve-case')).to_be_disabled()
        expect(page.locator('#ai-correct')).to_be_disabled()
        page.get_by_role('button',name='Preview reference replacements').click()
        expect(page.locator('#ai-reference-changes')).to_contain_text('10001 - deductible 10000 = 1')
        expect(page.locator('#ai-reference-apply')).to_be_disabled()
        page.locator('#ai-reference-confirm').check()
        page.get_by_role('button',name='Save reference-assisted draft').click()
        expect(page.locator('#ai-summary')).to_contain_text('reviewer_confirmed_reference')
        expect(page.locator('#ai-summary')).to_contain_text('AI correction attempts: 2/2')
        expect(page.locator('#ai-cases')).to_contain_text('Independent reference: matched')
        expect(page.locator('#ai-execute')).to_be_disabled()
        studio.approve().execute();assert len(provider.calls)==3
    finally:server.shutdown();thread.join(timeout=5);server.server_close()
