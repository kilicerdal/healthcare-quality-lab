import pytest
from playwright.sync_api import expect
pytestmark=[pytest.mark.e2e,pytest.mark.regression]
def test_effectiveness_discloses_baseline_failure_and_unequal_suite_sizes(page,live_url):
 page.goto(live_url+'/#research');page.get_by_role('button',name='Read saved effectiveness experiment').click();expect(page.locator('#effect-rows')).to_contain_text('historical_ai_raw');expect(page.locator('#effect-rows')).to_contain_text('Not scored');expect(page.locator('#effect-status')).to_contain_text('not an equal-budget model comparison')
