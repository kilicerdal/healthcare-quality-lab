import pytest
from tests.unit.test_coverage_lab import approved,body
from tests.unit.test_survivors import baseline
from tests.support.survivor_fixtures import case
from tests.support.ai_fixtures import FixtureProvider
pytestmark=[pytest.mark.api,pytest.mark.ai,pytest.mark.regression]
def test_survivor_plan_generation_and_comparison_api(app):
    lab=app.extensions['coverage_lab'];before=baseline(lab);client=app.test_client();plan=client.get('/api/coverage/scores/'+before['id']+'/survivor-plan').json
    lab.studio.provider=FixtureProvider({'cases':[case()]})
    result=client.post('/api/coverage/scores/'+before['id']+'/generate-survivors',json={'group_id':'evaluator','plan_hash':plan['plan_hash'],'model':'qwen2.5-coder:3b','variant':False})
    assert result.status_code==201 and result.json['approval'] is None and result.json['survivor_sequence_matches']
    after=lab.score(body(approved(lab,case()),approved(lab,case('workflow'))))
    comparison=client.post('/api/coverage/compare',json={'before_id':before['id'],'after_id':after['id']});assert comparison.status_code==201 and len(comparison.json['newly_detected'])==10
    assert client.get('/api/coverage/scores/'+before['id']+'/survivor-plan?variant=unknown').status_code==400
