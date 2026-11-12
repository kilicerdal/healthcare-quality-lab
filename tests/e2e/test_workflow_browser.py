import json
from pathlib import Path
import pytest
from playwright.sync_api import expect
from tests.support.workflow_page import WorkflowPage

ROOT=Path(__file__).resolve().parents[2]
pytestmark=[pytest.mark.e2e,pytest.mark.regression]


@pytest.mark.smoke
def test_browser_customer_adjuster_finance_complete_workflow(page,live_url):
    desk=WorkflowPage(page,live_url).open().submit()
    expect(desk.detail).to_contain_text('submitted / 1')
    expect(page.get_by_role('button',name='Approve as adjuster',exact=True)).to_be_disabled()
    desk.actor('adjuster-demo')
    expect(page.get_by_role('button',name='Approve as adjuster',exact=True)).to_be_enabled()
    desk.approve()
    expect(desk.detail).to_contain_text('approved / 2')
    desk.actor('finance-demo')
    expect(page.get_by_role('button',name='Record simulated payment',exact=True)).to_be_enabled()
    desk.pay()
    expect(desk.detail).to_contain_text('paid / 3')
    expect(desk.detail).to_contain_text('Simulated payment recorded: $900.00')
    expect(page.locator('.event-row')).to_have_count(3)
    expect(page.get_by_role('button',name='Record simulated payment',exact=True)).to_be_disabled()
    page.evaluate('window.scrollTo(0,0)')
    page.screenshot(path=str(ROOT/'artifacts/v5.3-workflow.png'),full_page=True)


@pytest.mark.sanity
def test_browser_duplicate_error_preserves_original_record(page,live_url):
    desk=WorkflowPage(page,live_url).open().submit()
    expect(desk.detail).to_contain_text('submitted / 1')
    desk.submit()
    expect(desk.message).to_contain_text('DUPLICATE_CLAIM')
    expect(page.locator('.claim-row')).to_have_count(1)
    expect(desk.detail).to_contain_text('submitted / 1')


def test_browser_denial_then_corrected_submission_reuses_id(page,live_url):
    desk=WorkflowPage(page,live_url).open().submit(service='dental')
    expect(desk.message).to_contain_text('SERVICE_NOT_COVERED')
    expect(page.locator('.claim-row')).to_have_count(0)
    desk.submit(service='medical')
    expect(desk.detail).to_contain_text('submitted / 1')


def test_browser_other_customer_sees_no_claim_and_no_old_details(page,live_url):
    desk=WorkflowPage(page,live_url).open().submit()
    expect(desk.detail).to_contain_text('E2E-100')
    desk.actor('customer-m200')
    expect(page.locator('#claim-list')).to_contain_text('No claims')
    expect(desk.detail).not_to_contain_text('E2E-100')
    expect(page.get_by_role('button',name='Export workflow JSON')).to_be_disabled()


def test_browser_authorization_denial_can_be_corrected(page,live_url):
    desk=WorkflowPage(page,live_url).open().actor('customer-m200')
    desk.submit(id='ADV-100',service='hospital',authorized=False)
    expect(desk.message).to_contain_text('AUTH_REQUIRED')
    desk.submit(id='ADV-100',service='hospital',authorized=True)
    expect(desk.detail).to_contain_text('submitted / 1')


def test_browser_reload_preserves_claim_and_auditor_cannot_transition(page,live_url):
    desk=WorkflowPage(page,live_url).open().submit()
    expect(desk.detail).to_contain_text('E2E-100')
    page.reload()
    expect(desk.detail).to_contain_text('E2E-100')
    desk.actor('auditor-demo')
    expect(page.locator('#actor-permissions')).to_contain_text('Read-only')
    expect(desk.detail).to_contain_text('submitted / 1')
    expect(page.get_by_role('button',name='Submit claim',exact=False)).to_be_disabled()
    expect(page.get_by_role('button',name='Approve as adjuster',exact=True)).to_be_disabled()


def test_workflow_export_contains_stored_provenance_and_ordered_history(page,live_url):
    desk=WorkflowPage(page,live_url).open().submit()
    expect(desk.detail).to_contain_text('submitted / 1')
    with page.expect_download() as info:page.get_by_role('button',name='Export workflow JSON').click()
    record=json.loads(Path(info.value.path()).read_text())
    assert record['claim']['claim_id']=='E2E-100'
    assert record['claim']['evaluation']['payout_cents']==90000
    assert record['events'][0]['rule_id']=='WF-002'
    assert record['payment'] is None
    assert len(record['workflow_contract_hash'])==64


def test_mobile_workflow_submission_and_permissions(page,live_url):
    page.set_viewport_size({'width':390,'height':844})
    desk=WorkflowPage(page,live_url).open().submit(id='MOBILE-100')
    expect(desk.detail).to_contain_text('submitted / 1')
    assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth')
    page.evaluate('window.scrollTo(0,0)')
    page.screenshot(path=str(ROOT/'artifacts/v5.3-workflow-mobile.png'),full_page=True)
