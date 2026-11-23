import pytest
from tools.evaluate_first_attempts_v86 import prepare,run
from tests.unit.test_v85_evaluation_runner import Fixture as OldFixture
from healthcare_quality.expectation_scorecard_v86 import KIND
pytestmark=[pytest.mark.unit,pytest.mark.regression]
class Fixture(OldFixture):
 def start(self,*a,**kw):r=super().start(*a,**kw);r['kind']=KIND;return r

def test_exposed_failure_stops_before_fresh_assessment(tmp_path):
 class Bad(Fixture):
  def start(self,*a,**kw):r=super().start(*a,**kw);r['rows'][0]['first']['assessment']['eligible']=False;return r
 f=Bad();r=run(prepare(),tmp_path/'out',tmp_path/'s.sqlite',f);assert len(f.calls)==2 and r['fresh_planned']==2 and not r['fresh_complete'] and r['fresh_first_attempt_percent'] is None

def test_known_successes_do_not_inflate_two_fresh_scores(tmp_path):
 f=Fixture();r=run(prepare(),tmp_path/'out',tmp_path/'s.sqlite',f);assert len(f.calls)==4 and r['actual_calls']==8 and r['fresh_first_passes']==2 and r['fresh_planned']==2 and not r['qualification']
