import io,json,urllib.error
import pytest
from healthcare_quality.ollama_provider import OllamaProvider,ProviderError
pytestmark=[pytest.mark.unit,pytest.mark.regression]
def test_local_http_schema_error_body_is_retained(monkeypatch):
 def rejected(*args,**kwargs):raise urllib.error.HTTPError('http://127.0.0.1:11434/api/generate',400,'Bad Request',{},io.BytesIO(b'{"error":"unsupported schema"}'))
 monkeypatch.setattr('urllib.request.urlopen',rejected)
 with pytest.raises(ProviderError) as error:OllamaProvider('advanced').generate('qwen2.5-coder:3b','fixture',{})
 assert error.value.raw_response['http_status']==400 and 'unsupported schema' in error.value.raw_response['body'] and not error.value.raw_response['truncated']


def test_reasoning_is_explicit_and_private_deliberation_is_not_retained(monkeypatch):
 from healthcare_quality.ollama_provider import ExpectationOllamaProvider
 calls=[]
 class Response:
  def __enter__(self):return self
  def __exit__(self,*args):pass
  def read(self,*args):return json.dumps({'done':True,'response':'{"observations":[]}','thinking':'private internal work','model':'qwen3.5:27b'}).encode()
 def send(request,**kwargs):calls.append(json.loads(request.data));return Response()
 monkeypatch.setattr('urllib.request.urlopen',send);p=ExpectationOllamaProvider(reasoning=True);r=p.generate('qwen3.5:27b','No tools',{})
 assert calls[0]['think'] is True and 'tools' not in calls[0]
 assert 'thinking' not in r['raw_envelope'] and not r['internal_deliberation_retained'];assert r['reasoning_requested']
 old=OllamaProvider('advanced');old.generate('qwen3.5:27b','Legacy',{});assert calls[-1]['think'] is False
