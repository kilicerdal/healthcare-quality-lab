import pytest
from tools.showcase import seed
pytestmark=[pytest.mark.unit,pytest.mark.regression]
def test_fresh_showcase_replays_without_inference_and_refuses_reuse(tmp_path):
    state=tmp_path/'state';out=tmp_path/'manifest.json';r=seed(state,out);assert r['live_model_requests']==0 and r['before_detected']==2 and r['after_detected']==12 and r['missing_gaps']==0
    with pytest.raises(ValueError):seed(state,tmp_path/'another.json')


def test_one_command_launcher_is_scoped_and_refuses_existing_state(tmp_path):
    from tools.launch_demo import commands
    plan=commands(tmp_path/'fresh',8897);assert plan[0][-1]=='--runtime-only' and plan[1][-2:]==['--port','8897']
    state=tmp_path/'existing';state.mkdir();(state/'keep').write_text('retain')
    with pytest.raises(ValueError):commands(state,8897)
    with pytest.raises(ValueError):commands(tmp_path/'new',80)
