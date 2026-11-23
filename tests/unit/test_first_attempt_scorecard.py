from copy import deepcopy
import pytest
from healthcare_quality.expectation_scorecard_v85 import scorecard,KIND
pytestmark=[pytest.mark.unit,pytest.mark.regression]
def record():
 calls=[dict(stage='first',generation={'phase':p},phase='response_frozen',response={}) for p in ('pricing','lifecycle')]
 return dict(kind=KIND,state='completed',protocol={'selection':{'strategy':'whole_case'}},rows=[dict(model='fixture',task_id='D',split='development',calls=calls,first=dict(answer={'observations':[{}]},assessment={'eligible':True,'schema_valid':True}))])
def test_only_complete_unrepeated_stage_pairs_get_first_credit():
 r=record();assert scorecard(r)['counts']=={'first_pass':1} and scorecard(r)['first_attempt_percent']==100
 for change in ('resume','retry','reuse','historical'):
  x=deepcopy(r)
  if change=='resume':x['resumed']=True
  if change=='retry':x['rows'][0]['calls'].append(deepcopy(x['rows'][0]['calls'][0]))
  if change=='reuse':x['rows'][0]['calls'][0]['response']['reused_frozen_model_response']=True
  if change=='historical':x['kind']='model_expectations_v84'
  assert scorecard(x)['counts'].get('first_pass',0)==0
 assert scorecard(x)['planned']==0

def test_wrong_values_invalid_output_timeout_and_unattempted_are_separate():
 r=record();row=r['rows'][0];row['first']['assessment']['eligible']=False;assert scorecard(r)['counts']=={'incorrect_values':1}
 row['first']['assessment']={};row['first']['error']='ValidationError';assert scorecard(r)['counts']=={'invalid_output':1}
 row['calls'][-1].update(phase='provider_error',error='TimeoutError');assert scorecard(r)['counts']=={'timeout':1}
 r['state']='interrupted';assert scorecard(r)['first_attempt_percent'] is None
 row['calls']=[];assert scorecard(r)['counts']=={'not_run':1}

def test_budget_later_in_job_does_not_relabel_an_earlier_pass():
 r=record();r.update(state='interrupted',stop_reason='time_budget');assert scorecard(r)['counts']=={'first_pass':1} and not scorecard(r)['complete']
