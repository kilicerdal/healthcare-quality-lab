from playwright.sync_api import expect
import pytest
pytestmark=[pytest.mark.e2e,pytest.mark.regression]

def test_showcase_journey_and_evidence_download(page,live_url):
    page.goto(live_url+'/#showcase')
    expect(page.get_by_role('heading',name='From a written rule to a verified release.')).to_be_visible()
    expect(page.locator('[data-milestone]')).to_have_count(5)
    expect(page.locator('#showcase-ready')).to_have_text('Ready')
    with page.expect_download() as info:page.get_by_role('link',name='V4 reserved prompt comparison').click()
    assert info.value.suggested_filename=='reserved.json'
    page.get_by_role('button',name='Start the claim journey').click()
    expect(page.get_by_role('heading',name='Every transition leaves evidence.')).to_be_visible()


def test_showcase_mobile_has_no_page_overflow(page,live_url):
    page.set_viewport_size({'width':390,'height':844});page.goto(live_url+'/#showcase')
    expect(page.locator('[data-milestone]')).to_have_count(5)
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
