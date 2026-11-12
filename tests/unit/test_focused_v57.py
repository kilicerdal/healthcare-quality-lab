from copy import deepcopy
import json
import pytest
from healthcare_quality import focused
from healthcare_quality.ai_studio import StudioError
from healthcare_quality.ai_schema import generation_schema
from tests.unit.test_coverage_lab import make
from tests.support.ai_fixtures import FixtureProvider,sample_case,review_request
pytestmark=[pytest.mark.unit,pytest.mark.ai,pytest.mark.regression]

def output(amount=112345):
    c=sample_case(amount=amount,payout=max(amount-10000,0));ctx=focused.context_for(c['steps'][0]['data']);c['rule_ids']=ctx['source_ids']
    return {'assessment':dict(rule_id='HC-007',decision='approved',deductible_cents=10000,after_deductible_cents=max(amount-10000,0),cap_cents=200000,payout_cents=min(max(amount-10000,0),200000)),'cases':[c]}
def generate(lab,amount=112345,change=None):
    o=output(amount)
    if change:change(o)
    lab.studio.provider=FixtureProvider(o)
    return lab.studio.generate_focused({'data':o['cases'][0]['steps'][0]['data'],'model':'qwen2.5-coder:3b'})

def test_focused_prompt_only_one_plan_and_free_expected_numbers():
    ctx=focused.context_for(output()['cases'][0]['steps'][0]['data']);prompt,schema=focused.prepare(ctx,generation_schema(1,ctx['source_ids']))
    assert ctx['source_ids']==['HC-003','HC-007']
    assert 'medicare_advantage' not in prompt and 'customer-m100' not in prompt
    assert 'const' not in schema['properties']['assessment']['properties']['payout_cents']
    assert '102345' not in prompt

@pytest.mark.parametrize('amount,expected',[(0,dict(rule_id='HC-001',decision='invalid',deductible_cents=None,after_deductible_cents=None,cap_cents=None,payout_cents=None)),(112345,dict(rule_id='HC-007',decision='approved',deductible_cents=10000,after_deductible_cents=102345,cap_cents=200000,payout_cents=102345)),(210001,dict(rule_id='HC-007',decision='approved',deductible_cents=10000,after_deductible_cents=200001,cap_cents=200000,payout_cents=200000))])
def test_literal_calculation(amount,expected):
    ctx=focused.context_for({'plan_id':'commercial_ppo','service':'medical','amount_cents':amount})
    assert focused.expected_assessment(ctx)==expected

@pytest.mark.parametrize('amount',[True,1.0,'1',None])
def test_invalid_amount_types(amount):
    with pytest.raises(ValueError):focused.context_for({'plan_id':'commercial_ppo','service':'medical','amount_cents':amount})

def test_calculation_mismatch_blocks_review_even_when_case_matches(tmp_path):
    lab=make(tmp_path);r=generate(lab,change=lambda o:o['assessment'].update(payout_cents=999))
    assert lab.studio.view(r['id'])['focused_validation']['status']=='mismatch'
    with pytest.raises(StudioError,match='focused calculation'):lab.studio.review(r['id'],review_request(r))
    assert lab.focused_metrics()['raw_failed']==1

def test_correct_focused_review_execute_export_and_metrics(tmp_path):
    lab=make(tmp_path);r=generate(lab);r=lab.studio.review(r['id'],review_request(r))
    assert lab.studio.execute(r['id'],{'expected_revision':r['revision']})['status']=='passed'
    assert 'focused.check' in lab.studio.export_pytest(r['id'])
    assert lab.focused_metrics()['raw_correct']==1

@pytest.mark.parametrize('bad',[None,{},['HC-003',None]])
def test_bad_citations_do_not_crash(bad):
    o=output();ctx=focused.context_for(o['cases'][0]['steps'][0]['data']);o['cases'][0]['rule_ids']=bad
    assert focused.check(ctx,o['assessment'],o['cases'])['status']=='mismatch'

def test_stale_protocol_rejected(tmp_path):
    o=output();ctx=focused.context_for(o['cases'][0]['steps'][0]['data']);ctx['protocol_hash']='old'
    assert focused.check(ctx,o['assessment'],o['cases'])['status']=='stale'

def test_assembly_copies_reviewed_inputs_and_requires_new_review(tmp_path):
    lab=make(tmp_path);records=[]
    for amount in (112345,127654):
        r=generate(lab,amount);records.append(lab.studio.review(r['id'],review_request(r)))
    calls=len(lab.studio.provider.calls)
    body={'sources':[{'id':r['id'],'expected_revision':r['revision']} for r in records],'reviewer_label':'Fixture reviewer','review_note':'Combine independently reviewed literal expectations.'}
    a=lab.assemble_evaluators(body)
    assert a['approval'] is None and a['expectation_origin']=='assembled_ai'
    assert a['proposals'][0]['case']['steps']==[r['proposals'][0]['case']['steps'][0] for r in records]
    assert len(lab.studio.provider.calls)==calls and len(a['assembly_sources'])==2
    with pytest.raises(StudioError):lab.studio.execute(a['id'],{'expected_revision':a['revision']})
    a=lab.studio.review(a['id'],review_request(a));assert lab.studio.execute(a['id'],{'expected_revision':a['revision']})['status']=='passed'
    assert 'assembly_sources' in lab.studio.export_pytest(a['id'])

def test_raw_metrics_ignore_later_proposal_changes(tmp_path):
    lab=make(tmp_path);r=generate(lab);r['proposals'][0]['case']['steps'][0]['expect']['payout_cents']=0
    assert focused.metrics([r])['raw_correct']==1

@pytest.mark.parametrize('body',[{}, {'data':{},'model':'cloud'}, {'data':{},'model':[]}])
def test_bad_focused_requests_never_infer(tmp_path,body):
    lab=make(tmp_path)
    with pytest.raises(StudioError):lab.studio.generate_focused(body)
    assert lab.studio.provider.calls==[]


def zero_output():
    o=output(0);o['assessment']=dict(rule_id='HC-001',decision='invalid',deductible_cents=None,after_deductible_cents=None,cap_cents=None,payout_cents=None);o['cases'][0]['steps'][0]['expect']={'status':400,'error':'INVALID_REQUEST'}
    return o

def replay_output():
    c=sample_case('AI-REPLAY',134567,124567);c['rule_ids']=['HC-007','WF-002','WF-003','WF-004','WF-005'];claim='REPLAY-571'
    def ok(status,state,revision,payment):return dict(status=status,claim_status=state,revision=revision,event_count=revision,payout_cents=124567,payment_cents=payment)
    c['steps']=[dict(action='submit',actor='customer-m100',data=dict(claim_id=claim,member_id='M100',service='medical',amount_cents=134567),expect=ok(201,'submitted',1,None)),dict(action='transition',actor='adjuster-demo',data=dict(claim_id=claim,target='approved'),expect=ok(200,'approved',2,None)),dict(action='transition',actor='finance-demo',data=dict(claim_id=claim,target='paid'),expect=ok(200,'paid',3,124567)),dict(action='transition',actor='finance-demo',data=dict(claim_id=claim,target='paid'),expect=dict(status=409,error='INVALID_TRANSITION')),dict(action='read',actor='customer-m100',data=dict(claim_id=claim),expect=ok(200,'paid',3,124567))]
    return {'cases':[c]}

@pytest.mark.parametrize('gap,provider_output',[('invalid-zero',zero_output()),('payment-replay',replay_output())])
def test_explicit_gaps_only_close_after_review_and_preserve_readback(tmp_path,gap,provider_output):
    lab=make(tmp_path,FixtureProvider(provider_output));r=lab.close_gap(gap,{'model':'qwen2.5-coder:3b'})
    status=lambda:next(g['status'] for g in lab.dashboard()['gaps'] if g['id']==gap)
    assert status()=='missing' and r['approval'] is None
    r=lab.studio.review(r['id'],review_request(r));assert status()=='represented'
    assert lab.studio.execute(r['id'],{'expected_revision':r['revision']})['status']=='passed'
    with pytest.raises(StudioError,match='already represented'):lab.close_gap(gap,{'model':'qwen2.5-coder:3b'})

@pytest.mark.parametrize('mode',['unreviewed','stale','duplicate'])
def test_assembly_rejects_unreviewed_stale_or_duplicate_sources(tmp_path,mode):
    lab=make(tmp_path);r=generate(lab)
    if mode!='unreviewed':r=lab.studio.review(r['id'],review_request(r))
    sources=[dict(id=r['id'],expected_revision=r['revision']-(1 if mode=='stale' else 0))]
    if mode=='duplicate':sources*=2
    with pytest.raises(StudioError):lab.assemble_evaluators(dict(sources=sources,reviewer_label='Fixture reviewer',review_note='Rejected assembly must not create a suite.'))
    assert len(lab.studio.store.list())==1

def test_calculation_only_reference_repair_is_explicit_and_does_not_change_raw_metrics(tmp_path):
    lab=make(tmp_path);r=generate(lab,change=lambda o:o['assessment'].update(payout_cents=999))
    preview=lab.studio.reference_preview(r['id']);assert preview['changes'][0]['step']=='assessment'
    child=lab.studio.apply_reference(r['id'],dict(expected_revision=r['revision'],reviewer_label='Fixture reviewer',review_note='Explicitly confirm calculation summary replacement.',reference_fingerprint=preview['reference_fingerprint'],preview_hash=preview['preview_hash'],reference_confirmed=True))
    assert child['approval'] is None and child['expectation_origin']=='reviewer_confirmed_reference'
    assert child['focused_validation']['status']=='matched'
    metrics=lab.focused_metrics();assert metrics['raw_failed']==1 and metrics['raw_correct']==0 and metrics['reference_assisted_cases']==1

def test_ai_correction_receives_calculation_mismatch_and_can_fix_it(tmp_path):
    lab=make(tmp_path);r=generate(lab,change=lambda o:o['assessment'].update(payout_cents=999));lab.studio.provider=FixtureProvider(output())
    child=lab.studio.correct(r['id'],dict(expected_revision=r['revision'],reviewer_label='Fixture reviewer',review_note='Request model correction of calculation summary.'))
    assert 'Assessment mismatch feedback' in lab.studio.provider.calls[0]['prompt']
    assert child['focused_validation']['status']=='matched' and child['approval'] is None
    assert lab.focused_metrics()['ai_correction_calls']==1


def test_assembly_retains_more_than_four_source_assumptions_without_losing_snapshots(tmp_path):
    lab=make(tmp_path);records=[]
    for i,amount in enumerate((112345,127654)):
        o=output(amount);o['cases'][0]['assumptions']=[f'Source {i} assumption {j}' for j in range(4)];lab.studio.provider=FixtureProvider(o)
        r=lab.studio.generate_focused({'data':o['cases'][0]['steps'][0]['data'],'model':'qwen2.5-coder:3b'});records.append(lab.studio.review(r['id'],review_request(r)))
    a=lab.assemble_evaluators(dict(sources=[dict(id=r['id'],expected_revision=r['revision']) for r in records],reviewer_label='Fixture reviewer',review_note='Inspect all source assumptions before new suite approval.'))
    assert len(a['proposals'][0]['case']['assumptions'])==1
    assert [s['case']['assumptions'] for s in a['assembly_sources']]==[r['proposals'][0]['case']['assumptions'] for r in records]
    assert a['approval'] is None


def test_live_measurement_refuses_reused_state_before_any_provider_call(tmp_path):
    import subprocess,sys
    state=tmp_path/'old-state';state.mkdir();(state/'sentinel').write_text('retain old evidence')
    out=tmp_path/'new-output'
    run=subprocess.run([sys.executable,'-m','tools.measure_focused','--state-dir',str(state),'--output',str(out)],capture_output=True,text=True)
    assert run.returncode==2 and 'cannot silently reuse old proposals' in run.stderr
    assert not out.exists() and (state/'sentinel').read_text()=='retain old evidence'
