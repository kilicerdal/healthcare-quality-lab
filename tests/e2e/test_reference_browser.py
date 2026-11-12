import threading
import pytest
from werkzeug.serving import make_server
from playwright.sync_api import expect
from healthcare_quality.app import create_app
from tests.support.ai_fixtures import FixtureProvider,sample_case
from tests.support.studio_page import StudioPage
pytestmark=[pytest.mark.e2e,pytest.mark.ai,pytest.mark.regression]
def test_wrong_payout_correction_and_fresh_review_in_browser(page,tmp_path):
    provider=FixtureProvider({'cases':[sample_case(payout=1)]})
    app=create_app({'TESTING':True,'DATABASE':str(tmp_path/'app.sqlite'),'AI_PROVIDER':provider})
    server=make_server('127.0.0.1',0,app,threaded=True);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    try:
        studio=StudioPage(page,f'http://127.0.0.1:{server.server_port}').open().generate()
        expect(page.locator('#ai-cases')).to_contain_text('Independent reference: mismatch')
        expect(page.locator('.ai-approve-case')).to_be_disabled()
        expect(page.locator('#ai-cases')).to_contain_text('reference 90000')
        studio.reviewer('Correct wrong payout using frozen scenario and independent reference.')
        provider.output={'cases':[sample_case()]}
        page.get_by_role('button',name='Correct expectations with Ollama').click()
        expect(page.locator('#ai-cases')).to_contain_text('Independent reference: matched')
        expect(page.locator('#ai-execute')).to_be_disabled()
        expect(page.locator('.ai-approve-case')).not_to_be_checked()
        studio.approve().execute()
        expect(page.locator('#ai-results')).to_contain_text('90000')
        assert len(provider.calls)==2
    finally:server.shutdown();thread.join(timeout=5);server.server_close()
