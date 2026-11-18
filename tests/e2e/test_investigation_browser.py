import pytest
from playwright.sync_api import expect
pytestmark=[pytest.mark.e2e,pytest.mark.regression]
def test_known_payment_fault_and_restored_result_are_visible(page,live_url):
    page.goto(live_url+'/#research');page.get_by_role('button',name='Run known-defect investigation').click();expect(page.locator('#evidence-status')).to_contain_text('Restored healthy execution: passed',timeout=20000);expect(page.locator('#evidence-facts')).to_contain_text('expected 71200; observed 71201');expect(page.locator('#evidence-status')).to_contain_text('No AI explanation requested')
