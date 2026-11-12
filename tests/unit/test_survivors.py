from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
import pytest
from healthcare_quality.ai_studio import StudioError,StudioService
from healthcare_quality.coverage_lab import PROFILES
from healthcare_quality.survivors import generation_groups,group_match,compare
from tests.unit.test_coverage_lab import make,approved,body
from tests.support.ai_fixtures import FixtureProvider,generation_request,review_request
from tests.support.survivor_fixtures import case,baseline_cases
pytestmark=[pytest.mark.unit,pytest.mark.ai,pytest.mark.regression]
IDS=[p['id'] for p in PROFILES]
def baseline(lab):return lab.score(body(*(approved(lab,c) for c in baseline_cases())))

@pytest.mark.parametrize('variant',[False,True])
def test_literal_plans_pass_reference_and_detect_all_twelve_seeds(tmp_path,variant):
    lab=make(tmp_path);records=[approved(lab,case(group,variant)) for group in ('evaluator','workflow')];result=lab.score(body(*records))
    assert result['state']=='scored' and result['detected']==12 and result['applicable']==12 and result['errors']==0
    assert all(b['result']['failed']==0 for b in result['baselines'])
    for group in generation_groups(IDS,variant):assert group_match(group,case(group['id'],variant))

def test_plan_uses_survivors_and_keeps_control_scenarios(tmp_path):
    lab=make(tmp_path);score=baseline(lab);assert score['detected']==2
    plan=lab.survivor_plan(score['id']);assert len(plan['survivor_ids'])==10
    assert [len(g['steps']) for g in plan['groups']]==[7,8]
    assert sorted(sum([g['target_fault_ids'] for g in plan['groups']],[]))==sorted(plan['survivor_ids'])
    assert not generation_groups([])

def test_explicit_generation_keeps_target_provenance_and_is_unapproved(tmp_path):
    lab=make(tmp_path);score=baseline(lab);plan=lab.survivor_plan(score['id']);lab.studio.provider=FixtureProvider({'cases':[case()]})
    result=lab.generate_survivors(score['id'],{'group_id':'evaluator','plan_hash':plan['plan_hash'],'variant':False,'model':'qwen2.5-coder:3b'})
    assert result['survivor_sequence_matches'] and result['approval'] is None and not result['runs']
    assert result['survivor_source']['plan_hash']==plan['plan_hash']
    assert len(lab.studio.provider.calls)==1

@pytest.mark.parametrize('change',['input','order','citations'])
def test_drifted_proposal_cannot_claim_plan_match(tmp_path,change):
    lab=make(tmp_path);score=baseline(lab);plan=lab.survivor_plan(score['id']);c=case()
    if change=='input':c['steps'][0]['data']['amount_cents']=112346
    elif change=='order':c['steps'][0],c['steps'][1]=c['steps'][1],c['steps'][0]
    else:c['rule_ids']=['HC-007']
    lab.studio.provider=FixtureProvider({'cases':[c]})
    result=lab.generate_survivors(score['id'],{'group_id':'evaluator','plan_hash':plan['plan_hash'],'variant':False,'model':'qwen2.5-coder:3b'})
    assert not result['survivor_sequence_matches'] and result['approval'] is None

@pytest.mark.parametrize('field,value,code',[('plan_hash','changed','STALE_PLAN'),('group_id','shell','INVALID_TARGET'),('variant','true','INVALID_REQUEST'),('model','cloud','INVALID_REQUEST')])
def test_bad_generation_request_makes_no_model_call(tmp_path,field,value,code):
    lab=make(tmp_path);score=baseline(lab);plan=lab.survivor_plan(score['id']);lab.studio.provider=FixtureProvider();request={'group_id':'evaluator','plan_hash':plan['plan_hash'],'variant':False,'model':'qwen2.5-coder:3b'};request[field]=value
    with pytest.raises(StudioError) as error:lab.generate_survivors(score['id'],request)
    assert error.value.code==code and not lab.studio.provider.calls

def test_edited_approval_invalidates_target_plan(tmp_path):
    lab=make(tmp_path);score=baseline(lab);snapshot=score['snapshots'][0];record=lab.studio.view(snapshot['id']);c=deepcopy(record['proposals'][0]['case']);c['title']='Edited after scoring'
    lab.studio.edit(record['id'],c['id'],{'expected_revision':record['revision'],'case':c,'reviewer_label':'Fixture reviewer','review_note':'Invalidate the old score snapshot.'})
    with pytest.raises(StudioError) as error:lab.survivor_plan(score['id'])
    assert error.value.code=='STALE_SCORE'

def test_compare_records_ten_new_detections_without_changing_denominator(tmp_path):
    lab=make(tmp_path);before=baseline(lab);after=lab.score(body(approved(lab,case()),approved(lab,case('workflow'))));result=lab.compare({'before_id':before['id'],'after_id':after['id']})
    assert result['before_detected']==2 and result['after_detected']==12 and len(result['newly_detected'])==10 and not result['regressed'] and not result['still_survived']
    assert lab.record(result['id'])['approval_snapshots_current']

@pytest.mark.parametrize('change',['source','denominator','error'])
def test_incompatible_comparisons_are_rejected(tmp_path,change):
    lab=make(tmp_path);a=baseline(lab);b=deepcopy(a)
    if change=='source':b['source_hash']='changed'
    elif change=='denominator':b['faults'][0]['status']='not_applicable'
    else:b['state']='incomplete';b['errors']=1
    with pytest.raises(StudioError):compare(a,b)

def test_comparison_exposes_regressions(tmp_path):
    lab=make(tmp_path);low=baseline(lab);high=lab.score(body(approved(lab,case()),approved(lab,case('workflow'))));result=compare(high,low)
    assert len(result['regressed'])==10 and result['after_detected']==2

def test_survivor_context_survives_interruption_retry_and_correction(tmp_path):
    from tests.unit.test_operation_recovery import BlockingProvider,expire,raw_record
    lab=make(tmp_path);score=baseline(lab);plan=lab.survivor_plan(score['id']);blocker=BlockingProvider();blocker.output={'cases':[case()]};lab.studio.provider=blocker
    request={'group_id':'evaluator','plan_hash':plan['plan_hash'],'variant':False,'model':'qwen2.5-coder:3b'}
    with ThreadPoolExecutor(max_workers=1) as pool:
        future=pool.submit(lab.generate_survivors,score['id'],request);assert blocker.entered.wait(3)
        record=raw_record(lab.studio);assert record['survivor_source']['score_id']==score['id'];expire(lab.studio,record['id']);lab.studio.recover_interrupted();blocker.release.set()
        with pytest.raises(StudioError):future.result(timeout=5)
    interrupted=lab.studio.view(record['id']);lab.studio.provider=FixtureProvider({'cases':[case()]})
    review={'expected_revision':interrupted['revision'],'reviewer_label':'Fixture reviewer','review_note':'Explicit retry with target context.'}
    retried=lab.studio.retry(record['id'],review);assert retried['survivor_source']['score_id']==score['id']
    corrected=lab.studio.correct(retried['id'],{**review,'expected_revision':retried['revision']});assert corrected['survivor_source']['score_id']==score['id']

def test_manual_edit_is_not_labeled_as_ai_expectation_output(tmp_path):
    lab=make(tmp_path);record=approved(lab,case());c=deepcopy(record['proposals'][0]['case']);c['title']='Explicit reviewer edit'
    edited=lab.studio.edit(record['id'],c['id'],{'expected_revision':record['revision'],'case':c,'reviewer_label':'Fixture reviewer','review_note':'Preserve manual edit provenance.'})
    assert edited['expectation_origin']=='reviewer_edit' and edited['history'][-1]['previous_expectation_origin']=='original_ai'

@pytest.mark.parametrize('id',[None,{},3])
def test_invalid_case_identifiers_do_not_break_inventory(tmp_path,id):
    lab=make(tmp_path,FixtureProvider({'cases':[{'id':id,'rule_ids':None,'steps':None}]}));lab.studio.generate(generation_request());assert lab.dashboard()['counts']['eligible']==32


def test_invalid_claim_id_cannot_match_a_valid_survivor_plan():
    group=next(g for g in generation_groups(IDS) if g['id']=='workflow');c=case('workflow')
    for step in c['steps']:step['data']['claim_id']='x'
    assert not group_match(group,c)

def test_all_detected_score_has_no_generation_groups(tmp_path):
    lab=make(tmp_path);score=lab.score(body(approved(lab,case()),approved(lab,case('workflow'))));plan=lab.survivor_plan(score['id'])
    assert plan['survivor_ids']==[] and plan['groups']==[]

def test_current_source_change_makes_generation_plan_stale(tmp_path,monkeypatch):
    lab=make(tmp_path);score=baseline(lab)
    from healthcare_quality.coverage_lab import fingerprints
    original=fingerprints();monkeypatch.setattr('healthcare_quality.coverage_lab.fingerprints',lambda:{**original,'source_hash':'changed'})
    with pytest.raises(StudioError) as error:lab.survivor_plan(score['id'])
    assert error.value.code=='STALE_SCORE'


def test_provider_schema_freezes_planned_inputs_but_not_expectations(tmp_path):
    lab=make(tmp_path);score=baseline(lab);plan=lab.survivor_plan(score['id']);lab.studio.provider=FixtureProvider({'cases':[case()]})
    r=lab.generate_survivors(score['id'],{'group_id':'evaluator','plan_hash':plan['plan_hash'],'variant':False,'model':'qwen2.5-coder:3b'})
    schema=lab.studio.provider.calls[0]['schema']['properties']['cases']['items'];steps=schema['properties']['steps']
    assert steps['minItems']==7 and steps['maxItems']==7
    assert steps['items']['anyOf'][0]['properties']['data']['const']==plan['groups'][0]['steps'][0]['data']
    assert 'const' not in steps['items']['anyOf'][0]['properties']['expect']
    assert r['generation_schema_version']=='survivor-inputs-v2'


def test_engineering_repair_helper_reloads_state_and_respects_two_attempt_budget(tmp_path):
    from tools.v56_live import repair_candidate
    lab=make(tmp_path);score=baseline(lab);plan=lab.survivor_plan(score['id']);wrong=case();wrong['steps'][-1]['expect']['payout_cents']=1;lab.studio.provider=FixtureProvider({'cases':[wrong]})
    initial=lab.generate_survivors(score['id'],{'group_id':'evaluator','plan_hash':plan['plan_hash'],'model':'qwen2.5-coder:3b','variant':False});snapshots=[]
    final,actions=repair_candidate(lab.studio,initial,{'reviewer_label':'Fixture engineering operator','review_note':'Explicit bounded fixture repair and inspected reference replacement.'},lambda r:snapshots.append(r['id']))
    assert len(actions['correction_ids'])==2 and actions['reference_assisted']
    assert final['expectation_origin']=='reviewer_confirmed_reference' and final['proposals'][0]['review_ready']
    assert final['approval'] is None and not final['runs'] and final['correction_budget']['used']==2
    assert len(lab.studio.provider.calls)==3 and len(snapshots)==3
    reference_case=lab.studio.review(final['id'],review_request(final));candidate=lab.score(body(reference_case,approved(lab,case('workflow'))));comparison=lab.compare({'before_id':score['id'],'after_id':candidate['id']})
    assert comparison['after_origins']=={'original_ai':1,'reviewer_confirmed_reference':1}
    assert lab.dashboard()['latest_score']['origins']==comparison['after_origins']


def test_generation_prompt_resets_stateless_flags_and_explains_rejection_precedence(tmp_path):
    lab=make(tmp_path);score=baseline(lab);plan=lab.survivor_plan(score['id']);lab.studio.provider=FixtureProvider({'cases':[case('workflow')]})
    lab.generate_survivors(score['id'],{'group_id':'workflow','plan_hash':plan['plan_hash'],'variant':False,'model':'qwen2.5-coder:3b'})
    prompt=lab.studio.provider.calls[0]['prompt']
    assert 'EVERY evaluate action is a separate stateless request' in prompt
    assert '409 INVALID_TRANSITION, not 403' in prompt and 'no state/money fields' in prompt
