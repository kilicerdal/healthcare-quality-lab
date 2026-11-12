"""Reusable studio interactions; the tests retain the expected outcomes."""
from playwright.sync_api import expect
class StudioPage:
    def __init__(self,page,origin):self.page,self.origin=page,origin
    def open(self):
        self.page.goto(self.origin+'/#ai')
        expect(self.page.locator('#ai-model')).to_have_value('qwen2.5-coder:3b')
        expect(self.page.locator('#ai-sources input:checked')).to_have_count(1)
        return self
    def generate(self,count='1',requirement='Test the synthetic deductible with explicit expected results.'):
        self.page.get_by_label('Requirement or testing goal').fill(requirement)
        self.page.get_by_label('Number of proposed cases').select_option(count)
        self.page.get_by_role('button',name='Generate with Ollama').click()
        expect(self.page.locator('#ai-summary')).to_contain_text('proposed')
        return self
    def reviewer(self,note='Verified the explicit payout against HC-007.'):
        self.page.get_by_label('Reviewer label',exact=False).fill('Automated browser fixture reviewer')
        self.page.get_by_label('Reason for approval or correction').fill(note)
        return self
    def approve(self):
        self.reviewer()
        self.page.locator('.ai-approve-case').first.check()
        self.page.locator('#ai-attest').check()
        self.page.get_by_role('button',name='Save review / approve selected').click()
        expect(self.page.locator('#ai-summary')).to_contain_text('approved · revision 2')
        return self
    def execute(self):
        self.page.get_by_role('button',name='Run approved snapshot').click()
        expect(self.page.locator('#ai-results')).to_contain_text('1 passed / 0 failed')
        return self
