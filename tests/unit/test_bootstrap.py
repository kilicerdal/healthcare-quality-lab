import pytest
from tools.bootstrap import plan,ROOT
pytestmark=[pytest.mark.unit,pytest.mark.regression]

def test_runtime_setup_does_not_install_test_browser():
    python,commands=plan(runtime_only=True)
    assert str(python).startswith(str(ROOT/".venv")) and len(commands)==1
    assert commands[0][-1]==str(ROOT/"requirements.txt")


def test_development_browser_install_is_explicit():
    _,commands=plan(browser=True)
    assert commands[0][-1]==str(ROOT/"requirements-dev.txt")
    assert commands[1][-3:]==['playwright','install','chromium']
