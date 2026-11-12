"""Browser tests use real HTTP requests, never a mocked claims response."""
import json
from pathlib import Path
import pytest
from playwright.sync_api import expect

ROOT = Path(__file__).resolve().parents[2]
pytestmark = [pytest.mark.e2e, pytest.mark.regression]


def open_workspace(page, live_url):
    page.goto(live_url)
    expect(page.locator("#plan-count")).to_have_text("8")


@pytest.mark.smoke
def test_evaluate_covered_claim_in_browser(page,live_url):
    open_workspace(page,live_url)
    page.get_by_label("Claim amount (cents)").fill("100000")
    page.get_by_role("button",name="Evaluate claim").click()
    expect(page.get_by_role("heading",name="Approved under this contract")).to_be_visible()
    expect(page.locator(".payout")).to_have_text("$900.00")
    expect(page.locator(".trace-row")).to_have_count(7)
    (ROOT/"artifacts").mkdir(exist_ok=True)
    page.evaluate("window.scrollTo(0, 0)")
    page.screenshot(path=str(ROOT/"artifacts/v5.7-workspace.png"),full_page=True)


@pytest.mark.sanity
def test_missing_authorization_then_correction(page,live_url):
    open_workspace(page,live_url)
    page.get_by_role("button",name="02 Authorization is missing",exact=False).click()
    page.get_by_role("button",name="Evaluate claim").click()
    expect(page.locator("#result")).to_contain_text("AUTH_REQUIRED")
    expect(page.locator(".trace-row.denied code")).to_have_text("HC-005")
    page.get_by_label("Authorization received",exact=True).check()
    page.get_by_role("button",name="Evaluate claim").click()
    expect(page.get_by_role("heading",name="Approved under this contract")).to_be_visible()


def test_uncovered_benefit_has_traceable_denial(page,live_url):
    open_workspace(page,live_url)
    page.locator('[data-example="benefit"]').click()
    page.get_by_role("button",name="Evaluate claim").click()
    expect(page.locator("#result")).to_contain_text("SERVICE_NOT_COVERED")
    expect(page.locator(".trace-row")).to_have_count(3)


def test_zero_payout_at_deductible(page,live_url):
    open_workspace(page,live_url)
    page.get_by_label("Claim amount (cents)").fill("10000")
    page.get_by_role("button",name="Evaluate claim").click()
    expect(page.get_by_role("heading",name="Approved under this contract")).to_be_visible()
    expect(page.locator(".payout")).to_have_text("$0.00")


def test_coverage_filters_rulebook_and_roadmap(page,live_url):
    open_workspace(page,live_url)
    page.locator('nav [data-page="coverage"]').click()
    page.get_by_role("button",name="Medicare",exact=True).click()
    expect(page.locator(".plan-card")).to_have_count(4)
    expect(page.get_by_role("heading",name="Medicare Advantage / Part C",exact=True)).to_be_visible()
    page.get_by_role("button",name="Commercial",exact=True).click()
    expect(page.locator(".plan-card")).to_have_count(2)
    page.locator('nav [data-page="rules"]').click()
    expect(page.locator(".rule-card")).to_have_count(13)
    page.locator('nav [data-page="roadmap"]').click()
    expect(page.locator(".roadmap-card article")).to_have_count(5)


def test_exported_json_matches_visible_result(page,live_url):
    open_workspace(page,live_url)
    page.get_by_role("button",name="Evaluate claim").click()
    expect(page.locator(".payout")).to_have_text("$900.00")
    with page.expect_download() as download_info:
        page.get_by_role("button",name="Export JSON").click()
    download = download_info.value
    data = json.loads(Path(download.path()).read_text())
    assert data["payout_cents"] == 90000
    assert data["decision"] == "approved"
    assert data["synthetic"] is True
    assert len(data["trace"]) == 7


def test_mobile_layout_and_evaluation(page,live_url):
    page.set_viewport_size({"width":390,"height":844})
    open_workspace(page,live_url)
    page.get_by_role("button",name="Evaluate claim").click()
    expect(page.locator(".payout")).to_have_text("$900.00")
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    (ROOT/"artifacts").mkdir(exist_ok=True)
    page.evaluate("window.scrollTo(0, 0)")
    page.screenshot(path=str(ROOT/"artifacts/v5.7-mobile.png"),full_page=True)


def test_report_link_opens_the_local_engineering_report(page,live_url):
    open_workspace(page,live_url)
    with page.expect_popup() as popup_info:
        page.get_by_role("link",name="Engineering report",exact=False).click()
    report=popup_info.value
    expect(report).to_have_title("Healthcare Quality Lab V5.7 Engineering Report")
    expect(report.get_by_role("heading",level=1)).to_have_text("Healthcare Quality Lab V5.7 Engineering Report")
