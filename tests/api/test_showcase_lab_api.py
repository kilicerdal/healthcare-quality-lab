import pytest
from tools.demo import seed
pytestmark=[pytest.mark.api,pytest.mark.regression]

def test_scenarios_are_explicit_and_do_not_modify_saved_claims(client,app):
    assert len(client.get('/api/showcase-lab').json['scenarios'])==4
    before=app.extensions['workflow'].list('auditor-demo')
    result=client.post('/api/showcase-lab/run',json={'scenario':'concurrency'})
    assert result.status_code==200 and result.json['status']=='passed'
    assert sorted(r['status'] for r in result.json['responses'])==[200,409]
    assert len({r['request_id'] for r in result.json['responses']})==2
    assert result.json['state']=={'status':'paid','revision':3,'events':3,'ledger_entries':1,'payment_cents':90000}
    assert app.extensions['workflow'].list('auditor-demo')==before

def test_actual_worker_interruption_and_retry(client):
    result=client.post('/api/showcase-lab/run',json={'scenario':'recovery'}).json
    assert result['status']=='passed'
    assert result['before']==result['after_interruption']
    assert result['after_retry']['ledger_entries']==1
    assert result['after_retry']['payment_cents']==90000

def test_requirement_change_blocks_actual_studio_execution(client):
    result=client.post('/api/showcase-lab/run',json={'scenario':'rule-change'}).json
    assert result['status']=='passed'
    guard=next(c for c in result['checks'] if 'execution guard' in c['label'])
    assert guard['observed']=='STALE_REFERENCE'

def test_incorrect_expectation_exposes_business_mismatch(client):
    result=client.post('/api/showcase-lab/run',json={'scenario':'oracle'}).json
    assert result['status']=='passed'
    fact=result['investigation']
    assert fact['proposed']['payout_cents']==112345
    assert fact['independent_expected']['payout_cents']==102345
    assert fact['mismatches'][0]['field']=='payout_cents'
    assert 'Not approved' in fact['approval']

@pytest.mark.parametrize('body',[{}, {'scenario':'unknown'}, {'scenario':'recovery','path':'/tmp/other'}, {'scenario':[]},None])
def test_rejects_arbitrary_demo_input(client,body):
    assert client.post('/api/showcase-lab/run',json=body).status_code==400

def test_cross_origin_demo_write_rejected(client):
    assert client.post('/api/showcase-lab/run',json={'scenario':'oracle'},headers={'Origin':'https://untrusted.example'}).status_code==403

def test_demo_seed_refuses_existing_state(tmp_path):
    seed(tmp_path/'demo')
    with pytest.raises(ValueError,match='new empty'):seed(tmp_path/'demo')
