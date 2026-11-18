import json
import pytest
from healthcare_quality import focused,reference
from healthcare_quality.reliability import ReliabilityLab,dataset,summary
from tests.support.ai_fixtures import FixtureProvider,sample_case
pytestmark=[pytest.mark.unit,pytest.mark.ai,pytest.mark.regression]
class Correct:
    def generate(self,model,prompt,schema):
        data=schema['properties']['cases']['items']['properties']['steps']['items']['properties']['data']['const'];ctx=focused.context_for(data);c=sample_case();c['rule_ids']=ctx['source_ids'];c['steps'][0]['data']=data;c['steps'][0]['expect']=reference.evaluate(data)[0]
        return {'text':json.dumps({'assessment':focused.expected_assessment(ctx),'cases':[c]})}
def test_reserved_repeats_exposure_and_no_repair(tmp_path):
    lab=ReliabilityLab(tmp_path/'r.sqlite',Correct());b=dict(models=['qwen3.5:27b'],task_ids=['R01','R02'],repeats=2);r=lab.start(b,False)
    assert r['state']=='completed' and r['first_exposure'] and r['summary']['qwen3.5:27b']['correct']==4
    assert not lab.start(b,False)['first_exposure'];assert all('expect' not in x for x in r['rows'])
def test_literal_reserved_outcomes_independent_reference():
    for t in dataset()['tasks']:assert reference.evaluate(t['data'])[0]==t['expect']
def test_provider_error_not_correct(tmp_path):
    lab=ReliabilityLab(tmp_path/'r.sqlite',FixtureProvider('bad json'));r=lab.start(dict(models=['qwen2.5:3b'],task_ids=['R01'],repeats=1),False);assert r['summary']['qwen2.5:3b']['correct']==0 and r['summary']['qwen2.5:3b']['errors']==1
@pytest.mark.parametrize('change',[{'repeats':True},{'repeats':4},{'models':['cloud']},{'task_ids':['R99']},{'task_ids':[]},{'models':[]}])
def test_reject_invalid_budget(tmp_path,change):
    from healthcare_quality.ai_studio import StudioError
    with pytest.raises(StudioError):ReliabilityLab(tmp_path/'r.sqlite').start(dict(models=['qwen3.5:27b'],task_ids=['R01'],repeats=1,**{})|change,False)


def test_cross_worker_lease_and_cancel_fence(tmp_path):
    import threading,time
    entered=threading.Event();release=threading.Event()
    class Slow(Correct):
        def generate(self,*args):entered.set();release.wait(3);return super().generate(*args)
    path=tmp_path/'r.sqlite';lab=ReliabilityLab(path,Slow());b=dict(models=['qwen3.5:27b'],task_ids=['R01'],repeats=1);r=lab.start(b);assert entered.wait(2)
    other=ReliabilityLab(path,Correct())
    with pytest.raises(ValueError):other.start(b,False)
    assert lab.cancel(r['id'])['state']=='cancelled';release.set()
    end=time.monotonic()+3
    while lab.lock.locked() and time.monotonic()<end:time.sleep(.01)
    assert lab.store.get(r['id'])['state']=='cancelled' and lab.store.get(r['id'])['rows']==[]
