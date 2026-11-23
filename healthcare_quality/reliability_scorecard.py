"""Reuse the V8.6 strict two-stage definition without relabeling original records."""
from copy import deepcopy
from healthcare_quality.expectation_scorecard_v86 import scorecard as previous

def scorecard(record):
 if record.get('kind')!='model_expectations_v87':raise ValueError('Only V8.7 study records accepted')
 projection=deepcopy(record);projection['kind']='model_expectations_v86'
 result=previous(projection);result['protocol_kind']=record['kind'];return result
