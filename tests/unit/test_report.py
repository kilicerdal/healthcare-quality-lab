import pytest
from tools.render_report import render
pytestmark=[pytest.mark.unit,pytest.mark.regression]


@pytest.mark.parametrize("version",["v1","v2","v3","v4","v5","v5.1"])
def test_report_version_labels_do_not_rewrite_historical_content(version):
    source="# Healthcare Quality Lab "+version.upper()+" Engineering Report\n\n## What changed from V1 to V2\n\nV1 foundation remains preserved. V2 adds workflows.\n"
    html=render(source,version)
    assert "<title>Healthcare Quality Lab "+version.upper()+" Engineering Report</title>" in html
    assert "What changed from V1 to V2" in html
    assert "V1 foundation remains preserved. V2 adds workflows." in html
