"""Page object: reusable UI vocabulary; expectations remain in the tests."""
from playwright.sync_api import expect

class WorkflowPage:
    def __init__(self,page,origin):self.page,self.origin=page,origin
    def open(self):
        self.page.goto(self.origin+'/#workflow')
        expect(self.page.locator('#workflow-actor')).to_have_value('customer-m100')
        expect(self.page.locator('#visible-count')).to_contain_text('records')
        return self
    def actor(self,actor):
        self.page.get_by_label('Demo identity (not authentication)').select_option(actor)
        return self
    def submit(self,id='E2E-100',service='medical',amount='100000',authorized=True):
        self.page.get_by_label('Unique claim ID').fill(id)
        self.page.get_by_label('Claim service',exact=True).select_option(service)
        self.page.get_by_label('Requested amount (cents)').fill(amount)
        self.page.get_by_label('Prior authorization received',exact=True).set_checked(authorized)
        self.page.get_by_role('button',name='Submit claim',exact=False).click()
        return self
    def open_claim(self,id):
        self.page.get_by_role('button',name='Open claim '+id,exact=True).click()
        return self
    def approve(self):self.page.get_by_role('button',name='Approve as adjuster',exact=True).click();return self
    def pay(self):self.page.get_by_role('button',name='Record simulated payment',exact=True).click();return self
    @property
    def detail(self):return self.page.locator('#claim-detail')
    @property
    def message(self):return self.page.locator('#workflow-message')
