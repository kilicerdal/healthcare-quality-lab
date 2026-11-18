from playwright.sync_api import expect
import pytest
pytestmark=[pytest.mark.e2e,pytest.mark.regression]

def test_wrong_expectation_and_observed_defect_are_inspectable(page,live_url):
    page.goto(live_url+'/#proof')
    expect(page.get_by_role('heading',name='One payment. Even when things go wrong.')).to_be_visible()
    page.get_by_role('button',name='A plausible AI expectation is blocked',exact=True).click()
    expect(page.locator('#proof-status')).to_contain_text('passed')
    expect(page.locator('#proof-checks')).to_contain_text('Seeded deductible defect')
    expect(page.locator('#proof-investigation')).to_contain_text('102345')
    expect(page.locator('#proof-investigation')).to_contain_text('Not approved')
    with page.expect_download() as download:page.get_by_role('button',name='Download this run').click()
    assert download.value.suggested_filename=='healthcare-oracle.json'

def test_concurrent_http_results_and_trace_ids_are_visible(page,live_url):
    page.goto(live_url+'/#proof')
    page.get_by_role('button',name='Two payment requests, one ledger entry',exact=True).click()
    expect(page.locator('#proof-status')).to_contain_text('passed')
    expect(page.locator('#proof-investigation')).to_contain_text('request_id')
    expect(page.locator('#proof-investigation')).to_contain_text('409')
    expect(page.locator('#proof-investigation')).to_contain_text('90000')

def test_interrupted_worker_proof_on_mobile_without_overflow(page,live_url):
    page.set_viewport_size({'width':390,'height':844});page.goto(live_url+'/#proof')
    page.get_by_role('button',name='Worker interruption rolls back partial payment',exact=True).click()
    expect(page.locator('#proof-status')).to_contain_text('passed')
    expect(page.locator('#proof-investigation')).to_contain_text('after_interruption')
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')

def test_demo_error_clears_previous_success(page,live_url):
    page.goto(live_url+'/#proof')
    page.get_by_role('button',name='A plausible AI expectation is blocked',exact=True).click()
    expect(page.locator('#proof-status')).to_contain_text('passed')
    page.route('**/api/showcase-lab/run',lambda route:route.fulfill(status=503,json={'error':'unavailable'}))
    page.get_by_role('button',name='Two payment requests, one ledger entry',exact=True).click()
    expect(page.locator('#proof-status')).to_contain_text('did not complete')
    expect(page.locator('#proof-checks')).to_have_text('No successful evidence available.')
    expect(page.get_by_role('button',name='Download this run')).to_be_disabled()
