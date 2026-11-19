import json,threading
from copy import deepcopy
import pytest
from healthcare_quality.experiment_lab import ExperimentLab
from healthcare_quality.evaluation_v8 import cohort
from healthcare_quality.test_design import compile_plan
pytestmark=[pytest.mark.unit,pytest.mark.regression]
class Provider:
 settings={'seed':7}
 def __init__(self):self.calls=0
 def status(self):return {'models':[{'name':'qwen2.5-coder:3b','digest':'offline-test-double'}]}
 def generate(self,model,prompt,schema):self.calls+=1;raise TimeoutError('offline failure')

def test_new_cohort_calculator_rows_make_no_model_calls_and_persist_exposure(tmp_path):
 provider=Provider();lab=ExperimentLab(tmp_path/'eval.sqlite',provider,threading.Lock(),cohort());selection=dict(models=['qwen2.5-coder:3b'],prompts=['focused-v68'],tasks=['EV8-13'],repeats=2,modes=['calculator_control'])
 r=lab.start(selection);assert r['state']=='completed' and provider.calls==0;assert r['summary'][0]['eligible']==2;assert not r['summary'][0]['ai_reasoning_metric'];assert not r['previously_exposed_tasks']
 r=ExperimentLab(lab.store.path,provider,threading.Lock(),cohort()).start(selection);assert r['previously_exposed_tasks']==['EV8-13'];assert provider.calls==0

def test_raw_failures_retained_without_correction_or_cloud_fallback(tmp_path):
 provider=Provider();lab=ExperimentLab(tmp_path/'eval.sqlite',provider,threading.Lock(),cohort());r=lab.start(dict(models=['qwen2.5-coder:3b'],prompts=['focused-v68'],tasks=['EV8-01'],repeats=2,modes=['ai_expectations']))
 assert r['state']=='completed' and provider.calls==2;assert r['summary'][0]['provider_errors']==2 and r['summary'][0]['eligible']==0 and r['summary'][0]['reference_assisted_corrections']==0
