import json,logging,re,sqlite3
import pytest
pytestmark=[pytest.mark.api,pytest.mark.regression]

def test_readiness_checks_stores_but_does_not_require_ollama(client,app):
    response=client.get('/api/ready');assert response.status_code==200 and response.json['status']=='ready'
    assert response.json['ai']=='Optional; not probed by readiness'
    with sqlite3.connect(app.extensions['quality_lab'].store.path) as db:db.execute('DROP TABLE ai_experiments')
    response=client.get('/api/ready');assert response.status_code==503 and response.json['storage']['quality']=='unavailable'


def test_showcase_has_five_milestones_and_fixed_evidence_allowlist(client):
    response=client.get('/api/showcase');assert response.status_code==200 and len(response.json['milestones'])==5
    assert response.json['repository_visibility']=='public'
    assert client.get('/api/showcase/evidence/reserved').status_code==200
    assert client.get('/api/showcase/evidence/not-allowed').status_code==404


def test_request_ids_and_logs_include_no_query_or_payload(client,caplog):
    with caplog.at_level(logging.INFO):
        response=client.post('/api/evaluate?private_note=NEVER_LOG_THIS',json={'invalid':'NEVER_LOG_BODY'})
    assert response.status_code==400 and re.fullmatch('[a-f0-9]{32}',response.headers['X-Request-ID'])
    assert response.headers['Server-Timing'].startswith('app;dur=')
    records=[json.loads(r.message) for r in caplog.records if r.message.startswith('{')]
    record=next(r for r in records if r.get('request_id')==response.headers['X-Request-ID'])
    assert record['route']=='/api/evaluate' and record['status']==400
    assert 'NEVER_LOG' not in json.dumps(records)
    assert client.get('/missing').headers['X-Request-ID']!=response.headers['X-Request-ID']


def test_storage_error_is_explicit_and_traceable(client,app,monkeypatch):
    def fail(*args):raise sqlite3.OperationalError('injected storage unavailability')
    monkeypatch.setattr(app.extensions['workflow'],'list',fail)
    response=client.get('/api/claims',headers={'X-Demo-Actor':'auditor-demo'})
    assert response.status_code==503 and response.json['error']=='STORAGE_ERROR'
    assert response.headers['X-Request-ID'] and 'injected' not in response.get_data(as_text=True)
