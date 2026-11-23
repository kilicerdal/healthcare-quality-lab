import json
import pytest
from healthcare_quality.reliability_evidence import seal
from tools.fingerprints import source_hash
pytestmark=[pytest.mark.api,pytest.mark.regression]
def test_saved_dashboard_is_read_only_and_checks_integrity(client,app,tmp_path):
 path=tmp_path/'dashboard.json';app.config['RELIABILITY_EVIDENCE']=str(path)
 assert client.get('/api/advanced/reliability-study').status_code==404
 path.write_text(json.dumps(seal(dict(source_hash=source_hash(),scope='<script>not HTML</script>'))))
 r=client.get('/api/advanced/reliability-study');assert r.status_code==200 and r.json['matches_current_source']
 assert client.post('/api/advanced/reliability-study',json={}).status_code==405
 path.write_text('{"payload":{},"content_hash":"bad"}')
 assert client.get('/api/advanced/reliability-study').status_code==409
 assert client.get('/reliability').status_code==200

def test_shared_mode_protects_raw_model_evidence(tmp_path):
 from healthcare_quality.app import create_app
 from werkzeug.security import generate_password_hash
 app=create_app(dict(TESTING=True,DATABASE=str(tmp_path/'shared.sqlite'),AUTH_MODE='shared',SECRET_KEY='s'*40,IDENTITIES={'owner':dict(password_hash=generate_password_hash('fixture-password'),roles=['customer'],actor_id='customer-m100')}))
 client=app.test_client();url='/api/advanced/reliability-study'
 assert client.get(url).status_code==401
 client.post('/api/auth/login',json=dict(username='owner',password='fixture-password'))
 assert client.get(url).status_code==403
