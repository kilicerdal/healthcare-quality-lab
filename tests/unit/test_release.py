import json
from pathlib import Path
import stat
import zipfile
import pytest
from tools.release import inspect,stage,activate,rollback,pointer,verify_tree,ReleaseError,sha,sidecar,build
pytestmark=[pytest.mark.unit,pytest.mark.regression]

def bundle(tmp_path,version="5.0.0",members=None):
    archive=tmp_path/("v"+version+"-source.zip")
    members=members or {"healthcare_quality/__init__.py":f'__version__ = "{version}"\n'.encode(),"requirements.txt":b'Flask==3.1.2\n'}
    with zipfile.ZipFile(archive,"w") as z:
        for name,content in members.items():z.writestr("Healthcare Quality Lab/"+name,content)
    manifest={"version":version,"sha256":sha(archive.read_bytes()),"files":{name:sha(content) for name,content in members.items()}}
    sidecar(archive).write_text(json.dumps(manifest));return archive


def test_bundle_stage_and_restage_validate_every_member(tmp_path):
    archive=bundle(tmp_path);target=tmp_path/'deploy'
    assert len(inspect(archive)['files'])==2
    first=stage(archive,target);assert not first['reused']
    assert stage(archive,target)['reused']
    assert verify_tree(target/'releases'/first['release_id'])['version']=='5.0.0'


def test_atomic_activation_rollback_and_separate_state(tmp_path):
    a=bundle(tmp_path,'4.0.0');b=bundle(tmp_path);target=tmp_path/'deploy'
    old=stage(a,target)['release_id'];new=stage(b,target)['release_id']
    activate(target,old);activate(target,new)
    assert pointer(target)['current']==new and pointer(target)['previous']==old
    state=target/'state'/new;state.mkdir(parents=True);(state/'sentinel').write_text('preserved')
    assert rollback(target)['current']==old
    assert (state/'sentinel').read_text()=='preserved'
    assert activate(target,new)['current']==new
    assert not list(target.glob('.pointer-*'))


def test_modified_archive_fails_before_staging(tmp_path):
    archive=bundle(tmp_path);archive.write_bytes(archive.read_bytes()+b'tamper')
    with pytest.raises(ReleaseError,match='checksum'):stage(archive,tmp_path/'deploy')
    assert not (tmp_path/'deploy').exists()

@pytest.mark.parametrize('name',['../escape.txt','/absolute.txt','a/../../escape','a\\escape','.env','.local/secrets','a/./b'])
def test_unsafe_or_excluded_members_are_rejected(tmp_path,name):
    archive=bundle(tmp_path,members={name:b'payload'})
    with pytest.raises(ReleaseError):inspect(archive)
    assert not (tmp_path.parent/'escape.txt').exists()


def test_manifest_member_digest_and_missing_member_are_rejected(tmp_path):
    archive=bundle(tmp_path);manifest=json.loads(sidecar(archive).read_text());manifest['files']['requirements.txt']='0'*64;sidecar(archive).write_text(json.dumps(manifest))
    with pytest.raises(ReleaseError,match='digest'):inspect(archive)
    manifest['files'].pop('requirements.txt');sidecar(archive).write_text(json.dumps(manifest))
    with pytest.raises(ReleaseError):inspect(archive)


def test_duplicate_and_symlink_members_are_rejected(tmp_path):
    archive=bundle(tmp_path)
    with pytest.warns(UserWarning):
        with zipfile.ZipFile(archive,'a') as z:z.writestr('Healthcare Quality Lab/requirements.txt',b'duplicate')
    manifest=json.loads(sidecar(archive).read_text());manifest['sha256']=sha(archive.read_bytes());sidecar(archive).write_text(json.dumps(manifest))
    with pytest.raises(ReleaseError,match='Duplicate'):inspect(archive)
    archive=bundle(tmp_path)
    with zipfile.ZipFile(archive,'a') as z:
        link=zipfile.ZipInfo('Healthcare Quality Lab/link');link.external_attr=(stat.S_IFLNK|0o777)<<16;z.writestr(link,'outside')
    manifest=json.loads(sidecar(archive).read_text());manifest['sha256']=sha(archive.read_bytes());sidecar(archive).write_text(json.dumps(manifest))
    with pytest.raises(ReleaseError,match='type'):inspect(archive)


def test_modified_staged_payload_cannot_be_activated(tmp_path):
    target=tmp_path/'deploy';id=stage(bundle(tmp_path),target)['release_id']
    (target/'releases'/id/'requirements.txt').write_text('changed')
    with pytest.raises(ReleaseError,match='changed'):activate(target,id)
    assert pointer(target)['current'] is None


def test_unknown_staged_file_and_pointer_traversal_are_rejected(tmp_path):
    target=tmp_path/'deploy';id=stage(bundle(tmp_path),target)['release_id']
    (target/'releases'/id/'unexpected.py').write_text('injected')
    with pytest.raises(ReleaseError):activate(target,id)
    with pytest.raises(ReleaseError):activate(target,'../../elsewhere')
    with pytest.raises(ReleaseError):rollback(target)


def test_packaging_requires_fresh_pass_and_will_not_overwrite(tmp_path,monkeypatch):
    import tools.release as module
    root=tmp_path/'source';(root/'artifacts').mkdir(parents=True);(root/'app.py').write_text('print("synthetic")')
    monkeypatch.setattr(module,'ROOT',root);monkeypatch.setattr(module,'source_hash',lambda:'current')
    verification={'status':'passed','source_hash':'old','version':'5.0.0','tests_passed':1,'categories':{'unit':1}}
    (root/'artifacts/verification.json').write_text(json.dumps(verification))
    with pytest.raises(ReleaseError,match='Fresh'):build(tmp_path/'output')
    verification['source_hash']='current';(root/'artifacts/verification.json').write_text(json.dumps(verification))
    record=build(tmp_path/'output');assert inspect(record['archive'])['version']=='5.0.0'
    with pytest.raises(ReleaseError,match='overwrite'):build(tmp_path/'output')
