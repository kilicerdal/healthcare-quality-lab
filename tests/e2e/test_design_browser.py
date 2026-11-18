import pytest
from playwright.sync_api import expect
pytestmark=[pytest.mark.e2e,pytest.mark.regression]

def test_design_modes_and_no_inference_on_navigation(page,live_url):
    calls=[];page.on('request',lambda r:calls.append(r.url) if r.method=='POST' else None);page.goto(live_url+'/#research');expect(page.get_by_role('heading',name='Design better tests before calculating answers.')).to_be_visible();expect(page.locator('#design-mode option')).to_have_count(2);assert not any('/generate' in x for x in calls)

def test_design_errors_are_visible_without_inference(page,live_url):
    page.goto(live_url+'/#research');page.get_by_role('button',name='Export checked design for separate review').click();expect(page.locator('#design-status')).to_have_text('Select a completed design')
