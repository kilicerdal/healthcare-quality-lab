from pathlib import Path
import os,py_compile,subprocess,sys
import pytest
from tools.release import stage,verify_tree,activate,ReleaseError
from tests.unit.test_release import bundle
from healthcare_quality.ai_studio import StudioService,ExperimentStore,StudioError
from tests.support.ai_fixtures import FixtureProvider,generation_request,review_request
from healthcare_quality.evaluation import retrieve
pytestmark=[pytest.mark.unit,pytest.mark.regression]

def test_reproduced_injected_bytecode_cannot_pass_staged_verification(tmp_path):
    source=b"value = 'good'\n";archive=bundle(tmp_path,members={'probe.py':source});target=tmp_path/'deployment'
    id=stage(archive,target)['release_id'];tree=target/'releases'/id;module=tree/'probe.py';stamp=module.stat().st_mtime
    module.write_bytes(b"value = 'evil'\n");os.utime(module,(stamp,stamp));py_compile.compile(str(module),doraise=True,invalidation_mode=py_compile.PycInvalidationMode.TIMESTAMP)
    module.write_bytes(source);os.utime(module,(stamp,stamp))
    observed=subprocess.check_output([sys.executable,'-B','-c','import probe;print(probe.value)'],cwd=tree,text=True,env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'}).strip()
    assert observed=='evil' # Demonstrates why -B alone is insufficient; temporary harmless module only.
    with pytest.raises(ReleaseError,match='[Bb]ytecode|cache'):verify_tree(tree)
    with pytest.raises(ReleaseError):activate(target,id)

@pytest.mark.parametrize('state',['generating','running'])
def test_legacy_interrupted_experiment_is_recovered_and_requires_new_review(tmp_path,state):
    service=StudioService(ExperimentStore(tmp_path/'ai.sqlite'),FixtureProvider());record=service.generate(generation_request());record=service.review(record['id'],review_request(record))
    with service.store.transaction() as db:
        record['state']=state;service.store.save(db,record)
    restarted=StudioService(ExperimentStore(service.store.path),FixtureProvider());saved=restarted.store.get(record['id'])
    assert saved['state']=='interrupted' and saved['revision']>record['revision']
    assert saved['approval'] is None and saved['approved_ids']==[]
    assert saved['raw_generation']==record['raw_generation'] and saved['proposals']==record['proposals']
    with pytest.raises(StudioError) as error:restarted.execute(record['id'],{'expected_revision':saved['revision']})
    assert error.value.code=='REVIEW_REQUIRED'

@pytest.mark.parametrize('query,expected',[('HC-007',['HC-007']),('hc-007',['HC-007']),('HC-007 WF-004',['HC-007','WF-004']),('HC-999',[]),('HC-0070',[])])
def test_exact_rule_ids_do_not_pull_unrelated_namespace_matches(query,expected):
    assert [r['rule_id'] for r in retrieve(query)]==expected
