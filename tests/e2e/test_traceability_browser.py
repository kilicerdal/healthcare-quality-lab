import pytest
from playwright.sync_api import expect
pytestmark=[pytest.mark.e2e,pytest.mark.regression]
def test_traceability_and_what_if_change_show_unapproved_case(page,live_url):
    page.goto(live_url+'/#research');page.get_by_role('button',name='Load an authored adjustment control').click();expect(page.locator('#advanced-summary')).to_contain_text('Independent checks passed');page.get_by_role('button',name='Refresh requirement links').click();expect(page.locator('#trace-status')).to_contain_text('1 scenarios');expect(page.locator('#trace-rows tr')).to_have_count(7);page.get_by_role('button',name='Preview cost-sharing rule impact').click();expect(page.locator('#trace-status')).to_contain_text('1 affected scenario(s)');expect(page.locator('#trace-status')).to_contain_text('No contract or approval was changed')
