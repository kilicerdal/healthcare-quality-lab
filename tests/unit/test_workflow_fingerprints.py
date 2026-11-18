import pytest
from tools import fingerprints
pytestmark=[pytest.mark.unit,pytest.mark.regression]
def test_all_ci_workflows_invalidate_release_verification(tmp_path,monkeypatch):
    for name in ('requirements.txt','requirements-dev.txt','pytest.ini'):(tmp_path/name).write_text('fixture')
    folder=tmp_path/'.github/workflows';folder.mkdir(parents=True);(folder/'ci.yml').write_text('ci');p=folder/'live-ai.yml';p.write_text('before');monkeypatch.setattr(fingerprints,'ROOT',tmp_path);before=fingerprints.source_hash();p.write_text('after');assert fingerprints.source_hash()!=before
