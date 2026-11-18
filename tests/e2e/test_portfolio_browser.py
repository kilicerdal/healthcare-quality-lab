import pytest
from playwright.sync_api import expect
pytestmark=[pytest.mark.e2e,pytest.mark.regression]
def test_guided_control_requires_separate_review(page,live_url):
 page.goto(live_url+'/#journey');expect(page.get_by_role('heading',name='Inspect the complete AI quality workflow.')).to_be_visible();page.get_by_role('button',name='Load the authored review control').click();expect(page.locator('#advanced-summary')).to_contain_text('Unapproved');expect(page.locator('#advanced-summary')).to_contain_text('authored_v7_showcase_control');page.get_by_role('button',name='Execute approved case through HTTP').click();expect(page.locator('#advanced-status')).to_contain_text('Current snapshot-bound review required')
@pytest.mark.parametrize('width',[390,1440])
def test_guided_showcase_has_labels_and_no_horizontal_page_overflow(page,live_url,width):
 page.set_viewport_size({'width':width,'height':900});page.goto(live_url+'/#journey');expect(page.locator('#journey-reports a')).to_have_count(6);assert page.evaluate('document.documentElement.scrollWidth<=innerWidth');page.get_by_role('button',name='Inspect frozen comparisons').click();expect(page.locator('#xp-lab')).to_be_visible()
