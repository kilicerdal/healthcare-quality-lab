import json,socket
from pathlib import Path
import pytest
from tools import showcase_server as server
pytestmark=[pytest.mark.unit,pytest.mark.regression]
def free_port():
 with socket.socket() as s:s.bind(('127.0.0.1',0));return s.getsockname()[1]

def test_owned_server_start_status_stop_and_preserved_replay(tmp_path):
 state=tmp_path/'demo';port=free_port()
 try:
  first=server.start(state,port);assert first['running'] and first['owned'] and first['ready'];assert server.start(state,port)['pid']==first['pid'];marker=state/'showcase-server.json';original=marker.read_text();bad=json.loads(original);bad['token']='wrong';marker.write_text(json.dumps(bad));assert not server.stop(state,port).get('owned');marker.write_text(original);assert server.status(state,port)['running'];out=server.stop(state,port);assert out['stopped'] and out['state_preserved'];assert (state/'expectations-v86.sqlite').exists();assert not server.status(state,port)['running']
 finally:server.stop(state,port)

@pytest.mark.parametrize('port',[True,0,1023,65536,'8902'])
def test_invalid_ports_cannot_target_any_process(tmp_path,port):
 with pytest.raises(ValueError):server.status(tmp_path,port)

def test_foreign_server_cannot_be_stopped(tmp_path,monkeypatch):
 token='owned-token';(tmp_path/'showcase-server.json').write_text(json.dumps(dict(port=8902,token=token,pid=12345)));calls=[]
 def fetch(port,path,*args,**kw):calls.append(path);return {'owner_hash':'foreign','pid':12345}
 monkeypatch.setattr(server,'fetch',fetch);out=server.stop(tmp_path,8902);assert not out['owned'] and calls==['/_showcase/status']
