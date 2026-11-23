"""Oracle-backed offline fixtures, never actual AI performance evidence."""
from copy import deepcopy
import json
from tests.unit.test_compact_expectations import wire as old_wire,Provider as OldProvider
from healthcare_quality.deductible_evaluator import worksheets
from healthcare_quality import deductible_expectations as protocol

def wire(plan):
 raw=old_wire(plan);expected=worksheets(plan);quotes={q['quote_id']:q for q in raw['quotes']}
 for i,o in enumerate(raw['observations']):
  if expected[i]:
   q=quotes[o['quote_id']]
   for line,extras in zip(q['calculation'],expected[i]):line.update(extras)
 return raw

class Provider(OldProvider):
 def generate(self,model,prompt,schema):
  self.prompts.append(prompt);answer=self.answers.pop(0) if self.answers else wire(protocol.cohort()['tasks'][0]['plan'])
  keys=set(schema['properties'])
  if keys=={'quotes'}:answer={'quotes':answer['quotes']}
  elif keys=={'observations'} and 'quotes' in answer:answer={'observations':answer['observations']}
  return dict(text=json.dumps(answer),latency_ms=1,input_tokens=1,output_tokens=1)
