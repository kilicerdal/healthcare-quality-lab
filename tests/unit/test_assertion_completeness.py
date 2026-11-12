from copy import deepcopy
import pytest
from healthcare_quality.ai_schema import validate_cases
from healthcare_quality.ai_studio import StudioService,ExperimentStore,StudioError
from tests.support.ai_fixtures import sample_case,FixtureProvider,generation_request,review_request
pytestmark=[pytest.mark.unit,pytest.mark.ai,pytest.mark.regression]

def success(status=201,state='submitted',revision=1,events=1,payment=None):
    return {'status':status,'claim_status':state,'revision':revision,'payout_cents':90000,'event_count':events,'payment_cents':payment}
def workflow_case():
    return {'id':'AI-COMPLETE-WORKFLOW','title':'Review a complete claim lifecycle','rule_ids':['WF-002','WF-003','WF-004','WF-005'],'rationale':'Assert status, payout, ledger and ordered history.','assumptions':[],
        'steps':[{'action':'submit','actor':'customer-m100','data':{'claim_id':'COMPLETE-1','member_id':'M100','service':'medical','amount_cents':100000},'expect':success()},
                 {'action':'transition','actor':'adjuster-demo','data':{'claim_id':'COMPLETE-1','target':'approved'},'expect':success(200,'approved',2,2)},
                 {'action':'transition','actor':'finance-demo','data':{'claim_id':'COMPLETE-1','target':'paid'},'expect':success(200,'paid',3,3,90000)}]}

def test_missing_payout_cannot_be_approved_despite_valid_structure(tmp_path):
    case=sample_case();del case['steps'][0]['expect']['payout_cents']
    studio=StudioService(ExperimentStore(tmp_path/'ai.sqlite'),FixtureProvider({'cases':[case]}));record=studio.generate(generation_request())
    assert record['proposals'][0]['valid']
    with pytest.raises(StudioError) as error:studio.review(record['id'],review_request(record))
    assert error.value.code=='INCOMPLETE_ASSERTIONS'

@pytest.mark.parametrize('step_index,field',[(0,'payout_cents'),(0,'event_count'),(1,'payment_cents'),(2,'payment_cents'),(2,'event_count'),(2,'payout_cents')])
def test_missing_workflow_observation_blocks_review(tmp_path,step_index,field):
    case=workflow_case();del case['steps'][step_index]['expect'][field]
    studio=StudioService(ExperimentStore(tmp_path/'ai.sqlite'),FixtureProvider({'cases':[case]}));request={**generation_request(),'source_ids':case['rule_ids']};record=studio.generate(request)
    assert record['proposals'][0]['valid']
    with pytest.raises(StudioError) as error:studio.review(record['id'],review_request(record))
    assert error.value.code=='INCOMPLETE_ASSERTIONS'


def test_rejected_payment_requires_unchanged_readback(tmp_path):
    case=workflow_case();case['steps']=case['steps'][:1]+[{'action':'transition','actor':'finance-demo','data':{'claim_id':'COMPLETE-1','target':'paid'},'expect':{'status':409,'error':'INVALID_TRANSITION'}}]
    studio=StudioService(ExperimentStore(tmp_path/'ai.sqlite'),FixtureProvider({'cases':[case]}));record=studio.generate({**generation_request(),'source_ids':case['rule_ids']})
    with pytest.raises(StudioError) as error:studio.review(record['id'],review_request(record))
    assert error.value.code=='INCOMPLETE_ASSERTIONS'


from healthcare_quality.assertion_quality import assess,policy_fingerprint
from healthcare_quality.ai_schema import generation_schema,digest
from jsonschema import Draft202012Validator


def test_complete_workflow_can_be_approved_and_detects_ledger_and_history_faults(tmp_path):
    from healthcare_quality.ai_runner import run_cases
    case=workflow_case();studio=StudioService(ExperimentStore(tmp_path/'ai.sqlite'),FixtureProvider({'cases':[case]}));record=studio.generate({**generation_request(),'source_ids':case['rule_ids']});record=studio.review(record['id'],review_request(record))
    assert studio.execute(record['id'],{'expected_revision':record['revision']})['status']=='passed'
    for defect in ('ledger_amount','history_skip'):assert run_cases([case],workflow_defect=defect)['failed']==1


def guarded_case():
    case=workflow_case();case['steps']=case['steps'][:1]+[{'action':'transition','actor':'finance-demo','data':{'claim_id':'COMPLETE-1','target':'paid'},'expect':{'status':409,'error':'INVALID_TRANSITION'}},{'action':'read','actor':'customer-m100','data':{'claim_id':'COMPLETE-1'},'expect':success(200)}];return case


def test_unchanged_readback_is_complete_and_rejection_does_not_require_nonexistent_fields():
    case=guarded_case();assert assess(case)['complete']
    assert assess(case)['steps'][1]['required_fields']==['error','status']

@pytest.mark.parametrize('field,value',[('event_count',2),('payment_cents',0),('revision',2),('payout_cents',1),('claim_status','paid')])
def test_rejection_readback_must_not_contradict_the_previous_declared_state(field,value):
    case=guarded_case();case['steps'][-1]['expect'][field]=value
    assert not assess(case)['complete']
    assert any(i['kind']=='changed_after_rejection' for i in assess(case)['issues'])


def test_reading_another_claim_does_not_guard_rejected_mutation():
    case=guarded_case();case['steps'][-1]['data']['claim_id']='ANOTHER-1';assert not assess(case)['complete']


def test_later_read_after_another_mutation_is_not_a_rejection_guard():
    case=guarded_case();case['steps'].insert(2,workflow_case()['steps'][1]);assert not assess(case)['complete']

@pytest.mark.parametrize('action,data,status,error',[
 ('evaluate',{'plan_id':'commercial_ppo','service':'medical','amount_cents':0},400,'INVALID_REQUEST'),
 ('transition',{'claim_id':'UNKNOWN-1','target':'paid'},404,'NOT_FOUND'),
 ('read',{'claim_id':'UNKNOWN-1'},404,'NOT_FOUND')])
def test_error_responses_do_not_require_payout_payment_or_history(action,data,status,error):
    case=workflow_case();case['steps']=[{'action':action,'actor':'none' if action=='evaluate' else 'finance-demo','data':data,'expect':{'status':status,'error':error}}]
    assert assess(case)['complete']


def test_denied_evaluation_needs_reason_and_zero_is_a_present_monetary_value():
    case=sample_case(payout=0);case['steps'][0]['expect'].update(decision='denied',reason='INACTIVE_POLICY');assert assess(case)['complete']
    del case['steps'][0]['expect']['reason'];assert not assess(case)['complete']


def test_zero_ledger_and_null_before_payment_are_not_treated_as_missing():
    case=workflow_case()
    for step in case['steps']:step['expect']['payout_cents']=0
    case['steps'][-1]['expect']['payment_cents']=0
    assert assess(case)['complete']


def test_schema_constrains_success_fields_and_error_observability_without_changing_base_validity():
    case=workflow_case();schema=generation_schema(1,case['rule_ids']);assert not list(Draft202012Validator(schema).iter_errors({'cases':[case]}))
    del case['steps'][-1]['expect']['payment_cents'];assert list(Draft202012Validator(schema).iter_errors({'cases':[case]}))
    assert validate_cases([case],case['rule_ids'])[0]['valid']
    case=guarded_case();case['steps'][1]['expect']['revision']=1;assert list(Draft202012Validator(schema).iter_errors({'cases':[case]}))


def test_a_case_level_union_does_not_hide_missing_assertions_at_one_step():
    case=workflow_case();del case['steps'][0]['expect']['payout_cents'];assert not assess(case)['complete']


def test_execution_and_export_recheck_completeness_even_for_a_matching_approval_hash(tmp_path):
    case=sample_case();del case['steps'][0]['expect']['payout_cents'];studio=StudioService(ExperimentStore(tmp_path/'ai.sqlite'),FixtureProvider({'cases':[case]}));record=studio.generate(generation_request())
    with studio.store.transaction() as db:
        record['state']='approved';record['approved_ids']=[case['id']];record['approval']={'hashes':{case['id']:digest(case)},'assertion_policy_fingerprint':policy_fingerprint()};studio.store.save(db,record)
    for call in (lambda:studio.execute(record['id'],{'expected_revision':record['revision']}),lambda:studio.export_pytest(record['id'])):
        with pytest.raises(StudioError) as error:call()
        assert error.value.code=='INCOMPLETE_ASSERTIONS'


def test_old_complete_approval_requires_fresh_policy_review_without_changing_historical_case(tmp_path):
    studio=StudioService(ExperimentStore(tmp_path/'ai.sqlite'),FixtureProvider());record=studio.generate(generation_request());record=studio.review(record['id'],review_request(record));before=deepcopy(record['proposals'][0]['case'])
    with studio.store.transaction() as db:record['approval'].pop('assertion_policy_fingerprint');studio.store.save(db,record)
    with pytest.raises(StudioError) as error:studio.export_pytest(record['id'])
    assert error.value.code=='STALE_ASSERTION_POLICY'
    viewed=studio.view(record['id']);assert not viewed['approval_matches_assertion_policy'] and viewed['proposals'][0]['review_ready']
    record=studio.review(record['id'],review_request(record));assert studio.execute(record['id'],{'expected_revision':record['revision']})['status']=='passed'
    assert studio.store.get(record['id'])['proposals'][0]['case']==before
