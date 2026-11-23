import pytest
from playwright.sync_api import expect
pytestmark=[pytest.mark.e2e,pytest.mark.regression]
@pytest.mark.parametrize('width',[390,1440])
def test_compact_dashboard_has_readable_explicit_controls(page,live_url,width):
 page.set_viewport_size({'width':width,'height':1000});posts=[];page.on('request',lambda r:posts.append(r.url) if r.method=='POST' else None);page.goto(live_url+'/#workbench');page.locator('#expectations-v82').scroll_into_view_if_needed();expect(page.locator('#ev82-start')).to_be_disabled();expect(page.locator('#ev82-review')).not_to_be_checked();expect(page.locator('#ev82-task option')).to_have_count(23);expect(page.locator('#ev82-faults')).to_contain_text('AST-355');expect(page.locator('#expectations-v82')).to_contain_text('different measures');assert not posts;assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')

def test_compact_failed_configuration_keeps_start_disabled(page,live_url):
 page.route('**/api/advanced/expectations-v86',lambda r:r.fulfill(status=503,json={'error':'V8.2 configuration unavailable'}));page.goto(live_url+'/#workbench');expect(page.locator('#ev82-status')).to_contain_text('configuration unavailable');expect(page.locator('#ev82-start')).to_be_disabled()

@pytest.fixture
def compact_url(tmp_path,request):
 import threading
 from werkzeug.serving import make_server
 from healthcare_quality.app import create_app
 from tests.support.v86_model_fixtures import Provider
 app=create_app({'TESTING':True,'DATABASE':str(tmp_path/'c.sqlite')});p=Provider()
 if getattr(request,'param',False):
  def fail(*a):raise TimeoutError('bounded fixture timeout')
  p.generate=fail
 lab=app.extensions['expectations_v86'];lab.provider=p;start=lab.start;lab.start=lambda body,background=False,**kwargs:start(body,False,**kwargs)
 server=make_server('127.0.0.1',0,app,threaded=True);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start();yield 'http://127.0.0.1:'+str(server.server_port);server.shutdown();thread.join(5);server.server_close()

def test_compact_fixture_journey_keeps_review_separate(page,compact_url):
 page.goto(compact_url+'/#workbench');page.locator('#ev83-live summary').click();page.locator('#ev82-model').select_option('qwen2.5-coder:3b');page.locator('#ev83-budget').fill('180');page.locator('#ev83-estimate').click();expect(page.locator('#ev82-start')).to_be_enabled();page.locator('#ev82-start').click();expect(page.locator('#ev82-id')).not_to_have_value('');page.locator('#ev82-poll').click();expect(page.locator('#ev82-score')).to_contain_text('1/1 correct');expect(page.locator('#ev82-rows')).to_contain_text('Correct · eligible');expect(page.locator('#ev82-rows')).to_contain_text('Not requested');page.locator('#ev82-export').click();expect(page.locator('#advanced-summary')).to_contain_text('Unapproved');page.locator('#advanced-note').fill('Offline fixture inspection, not real AI accuracy.');page.locator('#advanced-review').click();expect(page.locator('#advanced-status')).to_contain_text('approved');page.locator('#advanced-execute').click();expect(page.locator('#advanced-status')).to_contain_text('1 passed, 0 failed')

@pytest.mark.parametrize('compact_url',[True],indirect=True)
def test_compact_timeout_remains_visible_and_cannot_export(page,compact_url):
 page.goto(compact_url+'/#workbench');page.locator('#ev83-live summary').click();page.locator('#ev82-model').select_option('qwen2.5-coder:3b');page.locator('#ev83-budget').fill('180');page.locator('#ev83-estimate').click();expect(page.locator('#ev82-start')).to_be_enabled();page.locator('#ev82-start').click();expect(page.locator('#ev82-id')).not_to_have_value('');page.locator('#ev82-poll').click();expect(page.locator('#ev82-rows')).to_contain_text('Timeout · unavailable');expect(page.locator('#ev82-score')).to_contain_text('0/1 correct');page.locator('#ev82-export').click();expect(page.locator('#ev82-status')).to_contain_text('must independently match')

@pytest.fixture
def recorded_url(tmp_path):
 import json,threading
 from pathlib import Path
 from werkzeug.serving import make_server
 from healthcare_quality.app import create_app
 app=create_app({'TESTING':True,'DATABASE':str(tmp_path/'replay.sqlite')});r=json.loads((Path(__file__).resolve().parents[2]/'artifacts/v8.2/heldout.json').read_text());app.extensions['expectations_v86'].store.create(r)
 server=make_server('127.0.0.1',0,app,threaded=True);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start();yield 'http://127.0.0.1:'+str(server.server_port);server.shutdown();thread.join(5);server.server_close()

@pytest.mark.parametrize('width',[390,1440])
def test_recorded_incomplete_run_is_honest_and_makes_zero_post_requests(page,recorded_url,width):
 page.set_viewport_size({'width':width,'height':1000});posts=[];page.on('request',lambda r:posts.append(r.url) if r.method=='POST' else None);page.goto(recorded_url+'/#workbench');panel=page.locator('#expectations-v82');panel.scroll_into_view_if_needed();expect(page.locator('#ev82-status')).to_contain_text('recorded replay');expect(page.locator('#ev82-score')).to_contain_text('7 assessed / 20 planned');expect(page.locator('#ev82-score')).to_contain_text('7 correct API expectations');expect(page.locator('#ev82-score')).to_contain_text('4 fully valid');expect(page.locator('#ev82-score')).to_contain_text('3 worksheet mismatches');expect(page.locator('#ev82-score')).to_contain_text('13 not assessed');expect(page.locator('#ev82-score')).to_contain_text('INCOMPLETE');expect(page.locator('#ev82-score')).not_to_contain_text('%');expect(page.locator('#ev82-rows')).to_contain_text('Interrupted · outcome unknown');expect(page.locator('#ev82-rows')).to_contain_text('Not run · experiment stopped');assert page.locator('#ev83-live').get_attribute('open') is None;assert not posts;assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')

def test_preflight_estimate_is_visible_and_changes_invalidate_it(page,recorded_url):
 page.goto(recorded_url+'/#workbench');page.locator('#ev83-live summary').click();expect(page.locator('#ev82-start')).to_be_disabled();page.locator('#ev83-budget').fill('180');page.locator('#ev83-estimate').click();expect(page.locator('#ev83-estimate-text')).to_contain_text('Estimated ~');expect(page.locator('#ev83-estimate-text')).to_contain_text('180s');expect(page.locator('#ev82-start')).to_be_enabled();page.locator('#ev83-budget').fill('1');expect(page.locator('#ev82-start')).to_be_disabled()


def test_estimation_cannot_race_delayed_configuration(page,compact_url):
 held=[];page.route('**/api/advanced/expectations-v86',lambda route:held.append(route));page.goto(compact_url+'/#workbench',wait_until='domcontentloaded');page.locator('#ev83-live summary').click();expect(page.locator('#ev83-estimate')).to_be_disabled();expect(page.locator('#ev82-start')).to_be_disabled();assert held;held[0].fulfill(response=held[0].fetch());expect(page.locator('#ev83-estimate')).to_be_enabled();page.locator('#ev82-model').select_option('qwen2.5-coder:3b');page.locator('#ev83-budget').fill('180');page.locator('#ev83-estimate').click();expect(page.locator('#ev82-start')).to_be_enabled()


def test_inflight_estimate_cannot_enable_changed_budget(page,recorded_url):
 page.goto(recorded_url+'/#workbench');page.locator('#ev83-live summary').click();expect(page.locator('#ev83-estimate')).to_be_enabled();held=[];page.route('**/api/advanced/expectations-v86/estimate',lambda route:held.append(route));page.locator('#ev83-budget').fill('180');page.locator('#ev83-estimate').click();assert held;page.locator('#ev83-budget').fill('1');held[0].fulfill(status=200,json={'estimated_seconds':90,'request_budget':1,'max_seconds':180,'estimate_fits_budget':True});expect(page.locator('#ev82-start')).to_be_disabled();expect(page.locator('#ev83-estimate-text')).to_contain_text('Estimate before enabling')

def test_v85_requires_explicit_budget_before_estimate(page,recorded_url):
 page.goto(recorded_url+'/#workbench');page.locator('#ev83-live summary').click();expect(page.locator('#ev83-budget')).to_have_value('');expect(page.locator('#ev83-estimate')).to_be_enabled();page.locator('#ev83-estimate').click();expect(page.locator('#ev82-status')).to_contain_text('Choose a total job budget');expect(page.locator('#ev82-start')).to_be_disabled();expect(page.locator('#ev85-first-score')).to_contain_text('no V8.6 first attempts')
