from playwright.sync_api import expect
import pytest
pytestmark=[pytest.mark.e2e,pytest.mark.regression]

def test_authored_advanced_control_review_and_http_execution(page,live_url):
    page.goto(live_url+'/#research')
    page.get_by_role('button',name='Load an authored adjustment control').click()
    expect(page.locator('#advanced-summary')).to_contain_text('Independent checks passed')
    page.locator('#advanced-note').fill('Inspected independent payout, history, ledger and accumulator restoration')
    page.get_by_role('button',name='Approve inspected snapshot').click()
    expect(page.locator('#advanced-summary')).to_contain_text('Snapshot approved')
    page.get_by_role('button',name='Execute approved case through HTTP').click()
    expect(page.locator('#advanced-status')).to_contain_text('Execution: 1 passed, 0 failed',timeout=15000)

def test_advanced_mobile_form_remains_inside_viewport(page,live_url):
    page.set_viewport_size({'width':390,'height':844});page.goto(live_url+'/#research')
    expect(page.locator('#advanced-studio')).to_be_visible()
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')


def test_actual_lost_ack_peer_rehearsal(page,live_url):
    page.goto(live_url+'/#research')
    page.locator('#integration-scenario').select_option('lost_ack')
    page.get_by_role('button',name='Run isolated integration rehearsal').click()
    expect(page.locator('#integration-status')).to_contain_text('lost_ack: passed',timeout=15000)
    expect(page.locator('#integration-status')).to_contain_text('1 external synthetic payment(s)')
