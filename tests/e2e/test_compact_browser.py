import pytest
from playwright.sync_api import expect
pytestmark=[pytest.mark.e2e,pytest.mark.regression]
@pytest.mark.parametrize('width',[390,1440])
def test_compact_dashboard_has_readable_explicit_controls(page,live_url,width):
 page.set_viewport_size({'width':width,'height':1000});posts=[];page.on('request',lambda r:posts.append(r.url) if r.method=='POST' else None);page.goto(live_url+'/#workbench');page.locator('#expectations-v82').scroll_into_view_if_needed();expect(page.locator('#ev82-start')).to_be_enabled();expect(page.locator('#ev82-review')).not_to_be_checked();expect(page.locator('#ev82-task option')).to_have_count(14);expect(page.locator('#ev82-faults')).to_contain_text('AST-355');expect(page.locator('#expectations-v82')).to_contain_text('different measures');assert not posts;assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')

def test_compact_failed_configuration_keeps_start_disabled(page,live_url):
 page.route('**/api/advanced/expectations-v82',lambda r:r.fulfill(status=503,json={'error':'V8.2 configuration unavailable'}));page.goto(live_url+'/#workbench');expect(page.locator('#ev82-status')).to_contain_text('configuration unavailable');expect(page.locator('#ev82-start')).to_be_disabled()

@pytest.fixture
def compact_url(tmp_path,request):
 import threading
 from werkzeug.serving import make_server
 from healthcare_quality.app import create_app
 from tests.unit.test_compact_expectations import Provider
 app=create_app({'TESTING':True,'DATABASE':str(tmp_path/'c.sqlite')});p=Provider()
 if getattr(request,'param',False):
  def fail(*a):raise TimeoutError('bounded fixture timeout')
  p.generate=fail
 lab=app.extensions['expectations_v82'];lab.provider=p;start=lab.start;lab.start=lambda body,background=False:start(body,False)
 server=make_server('127.0.0.1',0,app,threaded=True);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start();yield 'http://127.0.0.1:'+str(server.server_port);server.shutdown();thread.join(5);server.server_close()

def test_compact_fixture_journey_keeps_review_separate(page,compact_url):
 page.goto(compact_url+'/#workbench');page.locator('#ev82-model').select_option('qwen2.5-coder:3b');page.locator('#ev82-start').click();expect(page.locator('#ev82-id')).not_to_have_value('');page.locator('#ev82-poll').click();expect(page.locator('#ev82-score')).to_contain_text('1/1 correct');expect(page.locator('#ev82-rows')).to_contain_text('Correct · eligible');expect(page.locator('#ev82-rows')).to_contain_text('Not requested');page.locator('#ev82-export').click();expect(page.locator('#advanced-summary')).to_contain_text('Unapproved');page.locator('#advanced-note').fill('Offline fixture inspection, not real AI accuracy.');page.locator('#advanced-review').click();expect(page.locator('#advanced-status')).to_contain_text('approved');page.locator('#advanced-execute').click();expect(page.locator('#advanced-status')).to_contain_text('1 passed, 0 failed')

@pytest.mark.parametrize('compact_url',[True],indirect=True)
def test_compact_timeout_remains_visible_and_cannot_export(page,compact_url):
 page.goto(compact_url+'/#workbench');page.locator('#ev82-model').select_option('qwen2.5-coder:3b');page.locator('#ev82-start').click();expect(page.locator('#ev82-id')).not_to_have_value('');page.locator('#ev82-poll').click();expect(page.locator('#ev82-rows')).to_contain_text('Timeout · unavailable');expect(page.locator('#ev82-score')).to_contain_text('0/1 correct');page.locator('#ev82-export').click();expect(page.locator('#ev82-status')).to_contain_text('must independently match')
