from copy import deepcopy
import json
import pytest
from healthcare_quality.expectation_protocol import cohort,inputs,context,prompt,parse,assemble
from healthcare_quality.expectation_evaluator import evaluate,worksheets,states
from healthcare_quality.test_design import compile_plan
from healthcare_quality.advanced_schema import semantic_key
pytestmark=[pytest.mark.unit,pytest.mark.regression]

def answer_for(plan):
 case=compile_plan(plan)
 return dict(observations=[dict(step_id=f'S{i:02}',expect=s['expect'],calculation=dict(state=states(plan)[i-1],lines=lines,accounting_note='Offline test double, never actual model evidence')) for i,(s,lines) in enumerate(zip(case['steps'],worksheets(plan)),1)])

@pytest.mark.parametrize('task',cohort()['tasks'],ids=lambda t:t['id'])
def test_independent_worksheet_and_observations_support_each_input(task):
 a=answer_for(task['plan']);r=evaluate(task['plan'],a);assert r['eligible'];assert semantic_key(r['cases'][0])==semantic_key(task['plan']['case'])

def test_prompt_construction_never_calls_oracle_or_production(monkeypatch):
 from healthcare_quality import advanced_reference,test_design,benefits
 def forbidden(*args,**kwargs):raise AssertionError('Calculator invoked during prompt construction')
 monkeypatch.setattr(advanced_reference.Oracle,'step',forbidden);monkeypatch.setattr(test_design,'compile_plan',forbidden);monkeypatch.setattr(benefits,'calculate',forbidden)
 p=cohort()['tasks'][0]['plan'];text=prompt(p);assert 'IMMUTABLE INPUTS' in text and '"expect"' not in text and 'REF_SECRET' not in text;assert context(p)['policies']

def test_model_cannot_rewrite_inputs_or_omit_or_duplicate_step_ids():
 p=cohort()['tasks'][0]['plan'];a=answer_for(p);original=deepcopy(p);assemble(p,a);assert p==original
 for mutation in ('extra','duplicate','missing','money'):
  b=deepcopy(a)
  if mutation=='extra':b['case']={'steps':[]}
  if mutation=='duplicate':b['observations'][1]['step_id']='S01'
  if mutation=='missing':b['observations'].pop()
  if mutation=='money':b['observations'][0]['expect']['payout_cents']=True
  assert not evaluate(p,b)['eligible']

def test_wrong_worksheet_blocks_even_correct_observations():
 p=cohort()['tasks'][0]['plan'];a=answer_for(p);a['observations'][0]['calculation']['lines'][0]['payer_before_caps_cents']+=1;r=evaluate(p,a);assert r['observations_correct'] and not r['calculations_correct'] and not r['eligible']

def test_literal_development_arithmetic_and_oop_clipping():
 p=cohort()['tasks'][0]['plan'];a=answer_for(p);v=a['observations'][0];assert v['expect']['payout_cents']==58653 and v['expect']['member_cents']==25664
 p=cohort()['tasks'][3]['plan'];v=answer_for(p)['observations'][0];assert v['expect']['member_cents']==30000 and v['expect']['payout_cents']==86437;assert v['calculation']['lines'][0]['payer_before_caps_cents']==84349

def test_inputs_are_new_and_have_no_expected_values():
 tasks=cohort()['tasks'];assert len(tasks)==14 and sum(t['split']=='development' for t in tasks)==4;assert '"expect"' not in json.dumps(tasks);assert len({semantic_key(t['plan']['case']) for t in tasks})==14
 from healthcare_quality.evaluation_v8 import cohort as older
 assert not {semantic_key(t['plan']['case']) for t in tasks}&{semantic_key(t['plan']['case']) for t in older()['tasks']}

def test_strict_json_rejects_duplicate_keys_and_nonfinite():
 with pytest.raises(ValueError):parse('{"observations":[],"observations":[]}')
 with pytest.raises(ValueError):parse('{"observations":NaN}')


def test_portable_generation_schema_has_no_boolean_item_schema():
 from healthcare_quality.expectation_protocol import answer_schema
 from jsonschema import Draft202012Validator
 plan=cohort()['tasks'][0]['plan'];schema=answer_schema(plan);Draft202012Validator.check_schema(schema);Draft202012Validator(schema).validate(answer_for(plan));assert isinstance(schema['properties']['observations']['items'],dict);assert list(schema['properties']['observations']['items']['properties'])==['step_id','calculation','expect']
