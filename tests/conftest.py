"""Every test receives an isolated app/database; live servers clean up on teardown."""
import os
from pathlib import Path
import threading
import pytest
from werkzeug.serving import make_server
from healthcare_quality.app import create_app
from healthcare_quality.workflow import ClaimStore,WorkflowService
ROOT=Path(__file__).resolve().parents[1]
os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH",str(ROOT/".browsers"))

@pytest.fixture
def app(tmp_path):
    return create_app({"TESTING":True,"DATABASE":str(tmp_path/"api.sqlite")})

@pytest.fixture
def client(app):return app.test_client()

@pytest.fixture
def workflow(tmp_path):return WorkflowService(ClaimStore(tmp_path/"unit.sqlite"))

@pytest.fixture
def live_url(tmp_path):
    server=make_server("127.0.0.1",0,create_app({"TESTING":True,"DATABASE":str(tmp_path/"browser.sqlite")}),threaded=True)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown();thread.join(timeout=5);server.server_close()
