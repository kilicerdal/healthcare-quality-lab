import pytest
from playwright.sync_api import expect
pytestmark=[pytest.mark.e2e,pytest.mark.regression]
def test_zero_call_calculator_control_is_not_labeled_ai_reasoning(page,live_url):
    page.goto(live_url+'/#research');expect(page.locator('#xp-start')).to_be_enabled();page.locator('#xp-modes').select_option(['calculator_control']);page.get_by_role('button',name='Run bounded local comparison').click();expect(page.locator('#xp-status')).to_contain_text('completed',timeout=15000);expect(page.locator('#xp-rows')).to_contain_text('calculator_control');expect(page.locator('#xp-rows')).to_contain_text('No call');expect(page.locator('#xp-status')).to_contain_text('No corrections, approvals or application execution')
