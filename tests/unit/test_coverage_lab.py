from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import pytest
from healthcare_quality.coverage_lab import CoverageLab,CATALOG,PROFILES,duplicates,gap_matches,scenario_hash
from healthcare_quality.ai_studio import StudioService,ExperimentStore,StudioError,checked_cases
from healthcare_quality.ai_runner import run_cases
from tests.support.ai_fixtures import FixtureProvider,sample_case,generation_request,review_request
pytestmark=[pytest.mark.unit,pytest.mark.ai,pytest.mark.regression]
CASES=json.loads(CATALOG.read_text())['cases']

def make(tmp_path,provider=None):
    studio=StudioService(ExperimentStore(tmp_path/'studio.sqlite'),provider or FixtureProvider())
    return CoverageLab(tmp_path/'coverage.sqlite',studio)
def approved(lab,case=None):
    if case:lab.studio.provider=FixtureProvider({'cases':[case]})
    request=generation_request();request['source_ids']=(case or sample_case())['rule_ids']
    r=lab.studio.generate(request);return lab.studio.review(r['id'],review_request(r))
def body(*records):return {'experiments':[{'id':r['id'],'expected_revision':r['revision']} for r in records]}
def item(case,key):return {**checked_cases([case],case['rule_ids'])[0],'key':key}
def workflow_case():
    data=json.loads(CATALOG.read_text())['cases'];find=lambda id:deepcopy(next(c for c in data if c['id']=='AI-COV-'+id)['steps'])
    steps=[find('OWN')[0],find('OWN')[1],find('DUP')[1],find('DUP')[2],find('ORDER')[1],find('ORDER')[2],find('PAY')[1],find('PAY')[2]]
    return {'id':'AI-ALL-WORKFLOW','title':'Eight-step fault-sensitive journey','rule_ids':['WF-001','WF-002','WF-003','WF-004','WF-005'],'rationale':'Assert role, duplicate, order, payment and history evidence.','assumptions':[],'steps':steps}

@pytest.mark.parametrize('case',CASES,ids=lambda c:c['id'])
def test_authored_catalog_has_complete_independent_expectations_and_passes(case):
    assert checked_cases([case],case['rule_ids'])[0]['review_ready']
    assert run_cases([case])['failed']==0

def test_dashboard_reports_bounded_inventory_and_missing_scenarios(tmp_path):
    lab=make(tmp_path);d=lab.dashboard()
    assert d['counts']['authored']==32 and d['counts']['eligible']==32
    assert {g['id'] for g in d['gaps'] if g['status']=='missing'}=={'invalid-zero','cap-plus-one','zero-payment','payment-replay'}
    assert 'not measured' in next(r for r in d['rules'] if r['id']=='WF-006')['limitation']
    assert not lab.studio.provider.calls

def test_unapproved_and_stale_cases_do_not_close_a_gap(tmp_path,monkeypatch):
    lab=make(tmp_path,FixtureProvider({'cases':[sample_case(amount=210001,payout=200000)]}))
    r=lab.studio.generate(generation_request());get=lambda:next(g for g in lab.dashboard()['gaps'] if g['id']=='cap-plus-one')['status']
    assert get()=='missing';lab.studio.review(r['id'],review_request(r));assert get()=='represented'
    monkeypatch.setattr('healthcare_quality.ai_studio.policy_fingerprint',lambda:'changed');assert get()=='missing'

def test_duplicate_normalizes_titles_ids_defaults_and_preserves_assertions():
    a=sample_case();b=sample_case('AI-SECOND');b['title']='Completely different words';b['steps'][0]['data'].update(active=True,in_network=True,authorized=True,formulary=True)
    groups=duplicates([item(a,'a'),item(b,'b')]);assert groups[0]['equivalent_assertion_groups']==[['a','b']]
    del b['steps'][0]['expect']['reason'];groups=duplicates([item(a,'a'),item(b,'b')]);assert groups[0]['different_assertions'] and not groups[0]['conflicts']
    b['steps'][0]['expect']['payout_cents']=1;assert duplicates([item(a,'a'),item(b,'b')])[0]['conflicts'][0]['field']=='payout_cents'
    b['steps'][0]['data']['amount_cents']=100001;assert not duplicates([item(a,'a'),item(b,'b')])

def test_claim_id_relationships_and_order_survive_normalization():
    a=workflow_case();b=deepcopy(a)
    for s in b['steps']:s['data']['claim_id']='RENAMED-ABC'
    assert scenario_hash(a)==scenario_hash(b)
    b['steps'][-1]['data']['claim_id']='OTHER-ABC';assert scenario_hash(a)!=scenario_hash(b)
    b=deepcopy(a);b['steps'][1],b['steps'][2]=b['steps'][2],b['steps'][1];assert scenario_hash(a)!=scenario_hash(b)

@pytest.mark.parametrize('profile',PROFILES,ids=lambda p:p['id'])
def test_known_fault_scoring_uses_actual_mismatches(profile,tmp_path):
    lab=make(tmp_path)
    if profile['family']=='workflow':case=workflow_case()
    else:
        from tools.benchmark import MUTATIONS
        case=deepcopy(next(c for c in CASES if c['id']=='AI-'+MUTATIONS[profile['defect']]))
    record=approved(lab,case);score=lab.score(body(record));target=next(f for f in score['faults'] if f['id']==profile['id'])
    assert score['state']=='scored' and target['status']=='detected'
    mismatch=target['observations'][0]['first_mismatch'];assert mismatch['expected']!=mismatch['observed'] and mismatch['rule_id']==profile['rule_id']
    assert score['baselines'][0]['result']['failed']==0

def test_untriggered_profiles_survive_and_do_not_receive_credit(tmp_path):
    lab=make(tmp_path);case=sample_case(amount=0,payout=0);case['rule_ids']=['HC-001'];case['steps'][0]['expect']={'status':400,'error':'INVALID_REQUEST'}
    score=lab.score(body(approved(lab,case)))
    assert score['detected']==0 and score['applicable']==7 and score['score']==0
    assert sum(f['status']=='not_applicable' for f in score['faults'])==5

def test_equivalent_approved_cases_are_scored_once(tmp_path):
    lab=make(tmp_path);a=approved(lab,sample_case());b=approved(lab,sample_case('AI-OTHER'))
    score=lab.score(body(a,b));assert score['selected_case_count']==2 and score['unique_case_count']==1

def test_different_assertion_sets_are_retained(tmp_path):
    lab=make(tmp_path);a=sample_case();b=sample_case('AI-OTHER');del b['steps'][0]['expect']['reason']
    score=lab.score(body(approved(lab,a),approved(lab,b)));assert score['unique_case_count']==2

def test_scoring_rejects_unreviewed_and_stale_revision(tmp_path):
    lab=make(tmp_path);r=lab.studio.generate(generation_request())
    with pytest.raises(StudioError):lab.score(body(r))
    reviewed=lab.studio.review(r['id'],review_request(r))
    with pytest.raises(StudioError) as error:lab.score(body(r))
    assert error.value.code=='STALE_REVISION'
    result=lab.score(body(reviewed));case=deepcopy(reviewed['proposals'][0]['case']);case['title']='Changed approved case'
    lab.studio.edit(r['id'],case['id'],{'expected_revision':reviewed['revision'],'case':case,'reviewer_label':'Fixture editor','review_note':'Changed after scoring.'})
    assert not lab.record(result['id'])['approval_snapshots_current']

def test_failed_healthy_baseline_produces_no_mutant_score(tmp_path,monkeypatch):
    lab=make(tmp_path);record=approved(lab);calls=[]
    def fail(*a,**k):calls.append(k);return {'failed':1,'results':[]}
    monkeypatch.setattr('healthcare_quality.coverage_lab.run_cases',fail)
    result=lab.score(body(record));assert result['state']=='baseline_failed' and result['score'] is None and not result['faults'] and len(calls)==1

def test_mutant_infrastructure_errors_are_not_detections(tmp_path,monkeypatch):
    lab=make(tmp_path);record=approved(lab);real=run_cases
    def error(cases,**kw):return {'failed':1,'results':[{'execution_error':'fixture storage outage','steps':[]}]} if kw else real(cases)
    monkeypatch.setattr('healthcare_quality.coverage_lab.run_cases',error)
    result=lab.score(body(record));assert result['state']=='incomplete' and result['score'] is None and result['errors']==7 and result['detected']==0

@pytest.mark.parametrize('bad',[{},None,{'experiments':[]},{'experiments':[{'id':'x','expected_revision':1}]*5}])
def test_scoring_request_budget_rejected(tmp_path,bad):
    with pytest.raises(StudioError):make(tmp_path).score(bad)

def suggestions(id='invalid-zero'):return {'suggestions':[{'gap_id':id,'explanation':'Invalid input must not become a financial result.','brief':'Generate a zero amount invalid request and assert the status and error.'}]}

def test_gap_analysis_preserves_snapshot_and_generation_remains_unapproved(tmp_path):
    provider=FixtureProvider(suggestions());lab=make(tmp_path,provider);analysis=lab.analyze({'model':'qwen2.5-coder:3b'})
    assert analysis['state']=='analyzed' and analysis['dashboard_snapshot']['snapshot_hash'] and len(provider.calls)==1
    provider.output={'cases':[sample_case()]};proposal=lab.propose(analysis['id'],{'suggestion_index':0})
    assert proposal['approval'] is None and not proposal['runs'] and proposal['gap_source']['gap_id']=='invalid-zero'
    # A model may ignore the brief; no coverage credit is awarded merely for lineage.
    assert next(g for g in lab.dashboard()['gaps'] if g['id']=='invalid-zero')['status']=='missing'

def test_unknown_model_claimed_gap_is_rejected_with_raw_response_preserved(tmp_path):
    lab=make(tmp_path,FixtureProvider(suggestions('invented-gap')));result=lab.analyze({'model':'qwen2.5-coder:3b'})
    assert result['state']=='failed' and result['raw_generation']
    with pytest.raises(StudioError):lab.propose(result['id'],{'suggestion_index':0})

def test_malformed_analysis_json_is_retained(tmp_path):
    lab=make(tmp_path,FixtureProvider('not JSON'));r=lab.analyze({'model':'qwen2.5-coder:3b'})
    assert r['state']=='failed' and r['raw_generation']['text']=='not JSON'

def test_gap_analysis_does_not_accept_duplicate_suggestions(tmp_path):
    answer=suggestions();answer['suggestions']*=2;lab=make(tmp_path,FixtureProvider(answer));assert lab.analyze({'model':'qwen2.5-coder:3b'})['state']=='failed'

def test_interrupted_analysis_recovers_and_fences_late_result(tmp_path):
    from tests.unit.test_operation_recovery import BlockingProvider
    provider=BlockingProvider();provider.output=suggestions();lab=make(tmp_path,provider)
    with ThreadPoolExecutor(max_workers=1) as pool:
        future=pool.submit(lab.analyze,{'model':'qwen2.5-coder:3b'});assert provider.entered.wait(3)
        with lab.store.transaction() as db:db.execute('UPDATE studio_operations SET expires_at=0')
        recovered=lab.records()[0];assert recovered['state']=='interrupted'
        provider.release.set()
        with pytest.raises(StudioError) as error:future.result(timeout=5)
        assert error.value.code=='OPERATION_LOST'

def test_arbitrary_fault_profile_cannot_enter_runner():
    with pytest.raises(ValueError):run_cases([sample_case()],evaluation_defect='shell')


def test_rule_map_uses_only_current_observed_score_evidence(tmp_path):
    lab=make(tmp_path);r=approved(lab);score=lab.score(body(r));dashboard=lab.dashboard()
    assert dashboard['latest_score']['current']
    assert next(row for row in dashboard['rules'] if row['id']=='HC-007')['observed_detected_profiles']==['eval-deductible']
    case=deepcopy(r['proposals'][0]['case']);case['title']='Edited after detection'
    lab.studio.edit(r['id'],case['id'],{'expected_revision':r['revision'],'case':case,'reviewer_label':'Fixture reviewer','review_note':'Invalidate approval after scoring.'})
    dashboard=lab.dashboard();assert not dashboard['latest_score']['current']
    assert not any(row['observed_detected_profiles'] for row in dashboard['rules'])


def test_skip_approval_is_not_misreported_as_paid_replay():
    rows={c['id']:deepcopy(c) for c in CASES}
    case=deepcopy(rows['AI-COV-ORDER']);case['steps']+=rows['AI-COV-PAY']['steps'][1:]
    last=deepcopy(case['steps'][-1]);last['action']='read';last['actor']='customer-m100';last['data']={'claim_id':'COV-100'};case['steps'].append(last)
    assert checked_cases([case],case['rule_ids'])[0]['review_ready']
    assert gap_matches('skip-approval',case) and not gap_matches('payment-replay',case)

def test_unknown_actor_is_not_foreign_customer_ownership_coverage():
    case=deepcopy(next(c for c in CASES if c['id']=='AI-COV-OWN'));case['steps'][1]['actor']='unknown-actor'
    assert checked_cases([case],case['rule_ids'])[0]['review_ready']
    assert not gap_matches('ownership',case)


def test_invalid_claim_id_boundary_is_not_normalized_into_valid_scenario():
    a=workflow_case();b=deepcopy(a)
    for step in b['steps']:step['data']['claim_id']='x'
    assert scenario_hash(a)!=scenario_hash(b)


@pytest.mark.parametrize('malformed',[{'id':'AI-BAD','rule_ids':None,'steps':None},'not-a-case',{'id':'AI-BAD','rule_ids':['HC-007'],'steps':[None]}])
def test_malformed_saved_proposals_remain_visible_without_breaking_dashboard(tmp_path,malformed):
    lab=make(tmp_path,FixtureProvider({'cases':[malformed]}));record=lab.studio.generate(generation_request())
    assert record['proposals'] and not record['proposals'][0]['valid']
    dashboard=lab.dashboard();assert dashboard['counts']['cases']==33 and dashboard['counts']['eligible']==32
    bad=next(i for i in dashboard['cases'] if i['experiment_id']==record['id']);assert bad['issues'] and not bad['eligible']


@pytest.mark.parametrize('failure',['provider','json'])
def test_generation_failure_with_no_cases_does_not_break_inventory(tmp_path,failure):
    from healthcare_quality.ollama_provider import ProviderError
    provider=FixtureProvider(error=ProviderError('Fixture unavailable')) if failure=='provider' else FixtureProvider('not JSON')
    lab=make(tmp_path,provider);r=lab.studio.generate(generation_request());assert r['state']=='generation_failed' and not r['proposals']
    assert lab.dashboard()['counts']['cases']==32
