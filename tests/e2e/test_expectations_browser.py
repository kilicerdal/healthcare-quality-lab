import pytest
from playwright.sync_api import expect
pytestmark=[pytest.mark.e2e,pytest.mark.regression]
@pytest.mark.parametrize('width',[390,1440])
def test_model_only_dashboard_is_explicit_and_distinguishes_stages(page,live_url,width):
 page.set_viewport_size({'width':width,'height':1000});posts=[];page.on('request',lambda r:posts.append(r.url) if r.method=='POST' else None);page.goto(live_url+'/#workbench');panel=page.locator('#expectations-v81');panel.scroll_into_view_if_needed();expect(page.locator('#ev81-start')).to_be_enabled();expect(page.locator('#ev81-task option')).to_have_count(14);assert not posts;expect(panel).to_contain_text('after both answers are frozen');expect(panel).to_contain_text('80%');assert page.evaluate('document.documentElement.scrollWidth<=innerWidth');expect(page.locator('#ev81-stage option')).to_have_count(2)

def test_unavailable_configuration_keeps_generation_disabled(page,live_url):
 page.route('**/api/advanced/expectations',lambda route:route.fulfill(status=503,json={'error':'configuration unavailable'}));page.goto(live_url+'/#workbench');expect(page.locator('#ev81-status')).to_contain_text('configuration unavailable');expect(page.locator('#ev81-start')).to_be_disabled()

@pytest.fixture
def expectation_url(tmp_path,request):
 import threading
 from werkzeug.serving import make_server
 from healthcare_quality.app import create_app
 from tests.unit.test_expectation_lab import Provider
 from tests.unit.test_expectation_protocol import answer_for
 from healthcare_quality.expectation_protocol import cohort
 app=create_app({'TESTING':True,'DATABASE':str(tmp_path/'browser.sqlite')});p=Provider()
 if getattr(request,'param',False):
  bad=answer_for(cohort()['tasks'][0]['plan']);bad['observations'][0]['expect']['payout_cents']+=1;p.answers=[bad,bad]
 lab=app.extensions['expectations_v81'];lab.provider=p;start=lab.start;lab.start=lambda body,background=False:start(body,False)
 server=make_server('127.0.0.1',0,app,threaded=True);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start();yield 'http://127.0.0.1:'+str(server.server_port);server.shutdown();thread.join(5);server.server_close()

def test_offline_model_flow_preserves_separate_review_and_http_execution(page,expectation_url):
 page.goto(expectation_url+'/#workbench');page.locator('#ev81-model').select_option('qwen2.5-coder:3b');page.locator('#ev81-start').click();expect(page.locator('#ev81-id')).not_to_have_value('');page.locator('#ev81-poll').click();expect(page.locator('#ev81-score')).to_contain_text('first: 1/1');expect(page.locator('#ev81-score')).to_contain_text('self_review: 1/1');page.locator('#ev81-export').click();expect(page.locator('#advanced-summary')).to_contain_text('Unapproved');expect(page.locator('#advanced-summary')).to_contain_text('v81_model_expectations_first');page.locator('#advanced-note').fill('Offline fixture engineering inspection, not actual AI generation; validated independent observations.');page.locator('#advanced-review').click();expect(page.locator('#advanced-status')).to_contain_text('approved');page.locator('#advanced-execute').click();expect(page.locator('#advanced-status')).to_contain_text('1 passed, 0 failed')

@pytest.mark.parametrize('expectation_url',[True],indirect=True)
def test_wrong_model_expectations_stay_blocked_in_browser(page,expectation_url):
 page.goto(expectation_url+'/#workbench');page.locator('#ev81-model').select_option('qwen2.5-coder:3b');page.locator('#ev81-start').click();expect(page.locator('#ev81-id')).not_to_have_value('');page.locator('#ev81-poll').click();expect(page.locator('#ev81-score')).to_contain_text('first: 0/1');page.locator('#ev81-export').click();expect(page.locator('#ev81-status')).to_contain_text('must independently match')
