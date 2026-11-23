import pytest
from playwright.sync_api import expect
pytestmark=[pytest.mark.e2e,pytest.mark.regression]
@pytest.mark.parametrize('width',[390,1280])
def test_saved_dashboard_has_no_inference_requests_and_safe_text(page,live_url,width):
 payload=dict(matches_current_source=True,study=dict(fresh_passed=1,fresh_planned=12,actual_calls=2,repeat_pairs=[],provider_seconds_median=72.3,fresh_complete=False,scope='Incomplete, no final accuracy claim.'),rule_review=dict(vectors=[dict(passed=True)]),coverage=[dict(task='R87-03',scenario='<script>unsafe</script>',actions=['submit','pay','read'],outcomes=['incorrect_values'])],defect_detection=[dict(label='ai_original_first_attempt',case_count=1,scored=True,detected=8,total=27)],investigations=[dict(task='R87-03',eligible=False,facts=[dict(id='F1',detail='wrong payout')])],provenance=[],scope='Synthetic evidence')
 page.route('**/api/advanced/reliability-study',lambda route:route.fulfill(json=payload));posts=[]
 page.on('request',lambda request:posts.append(request.url) if request.method=='POST' else None)
 page.set_viewport_size(dict(width=width,height=850));page.goto(live_url+'/reliability')
 expect(page.locator('#metrics')).to_contain_text('1/12');expect(page.locator('#coverage')).to_contain_text('<script>unsafe</script>');expect(page.locator('#boundaries')).to_contain_text('Assessment incomplete')
 assert page.locator('#coverage script').count()==0 and not posts
 assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth')
