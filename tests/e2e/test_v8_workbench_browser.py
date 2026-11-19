import pytest
from playwright.sync_api import expect
pytestmark=[pytest.mark.e2e,pytest.mark.regression]
@pytest.mark.parametrize('width',[390,1440])
def test_workbench_proposal_routing_and_evidence(page,live_url,width):
 page.set_viewport_size({'width':width,'height':900});posts=[];page.on('request',lambda r:posts.append(r.url) if r.method=='POST' else None)
 page.goto(live_url+'/#workbench');expect(page.get_by_role('heading',name='Design, review and measure healthcare tests.')).to_be_visible();expect(page.locator('#wb-packs article')).to_have_count(8);assert not posts
 assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
 page.locator('#wb-pack').select_option('medicare_d');page.locator('#wb-propose').click();expect(page.locator('#wb-status')).to_contain_text('unapproved');page.locator('#wb-assistant').click();expect(page.locator('#wb-evidence')).to_contain_text('deterministic_evidence_assistant');page.locator('#wb-route').click();expect(page.locator('#wb-evidence')).to_contain_text('local_attestation');expect(page.locator('#wb-evidence')).to_contain_text('"approval": null');expect(page.locator('#wb-reports a')).to_have_count(10)
 page.locator('#wb-open').click();expect(page.locator('#advanced-summary')).to_contain_text('Unapproved');expect(page.locator('#advanced-summary')).to_contain_text('authored_v8_coverage_pack');page.locator('[data-page="workbench"]').click();expect(page.get_by_role('heading',name='Design, review and measure healthcare tests.')).to_be_visible()

def test_workbench_initialization_blocks_writes_and_calculator_control_never_calls_model(page,live_url):
 page.route('**/api/advanced/workbench',lambda route:route.fulfill(status=503,json={'error':'temporary unavailable'}))
 page.goto(live_url+'/#workbench');expect(page.locator('#wb-status')).to_contain_text('temporary unavailable');expect(page.locator('#wb-propose')).to_be_disabled();expect(page.locator('#wb-experiment')).to_be_disabled();expect(page.locator('#wb-ai-start')).to_be_disabled()
 page.unroute('**/api/advanced/workbench');page.reload();expect(page.locator('#wb-experiment')).to_be_enabled();page.locator('#wb-experiment').click();expect(page.locator('#wb-experiment-id')).not_to_have_value('');page.locator('#wb-poll').click();expect(page.locator('#wb-evidence')).to_contain_text('calculator_control')
