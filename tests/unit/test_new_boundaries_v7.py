from pathlib import Path
from html.parser import HTMLParser
from collections import Counter
import json,threading
import pytest
from healthcare_quality.evidence_investigator import explain,inspect,seal
from healthcare_quality.advanced_runner import run
from tests.unit.test_advanced_cases import CASES
pytestmark=[pytest.mark.unit,pytest.mark.regression]
def test_all_ui_ids_are_unique_across_preserved_and_new_panels():
 class P(HTMLParser):
  def __init__(self):super().__init__();self.ids=[]
  def handle_starttag(self,tag,attrs):self.ids.extend(v for k,v in attrs if k=='id')
 p=P();p.feed((Path(__file__).resolve().parents[2]/'healthcare_quality/templates/index.html').read_text());assert all(n==1 for n in Counter(p.ids).values())
def test_invalid_ai_explanation_retains_raw_without_acceptance():
 class Bad:
  def generate(self,*args):return {'text':'not valid JSON','model':'offline test fixture'}
 analysis=inspect(seal(CASES[:1],run(CASES[:1])));r=explain(Bad(),'qwen2.5-coder:3b',analysis);assert not r['accepted'] and r['raw']['text']=='not valid JSON' and r['answer'] is None
