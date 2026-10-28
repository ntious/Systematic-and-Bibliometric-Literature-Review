from hashlib import sha256
import json
from pathlib import Path
import zipfile
import pytest
from slr import screening, replication
from slr.cli import run, main


@pytest.fixture
def bundle(tmp_path):
    run('configs/example_review.toml',tmp_path/'run','Examples/demo_records.json')
    db=tmp_path/'review.sqlite'
    screening.initialize(db,tmp_path/'run','Synthetic',['A','B'],'C','Criteria')
    original=db.read_bytes()
    folder=replication.create(db,tmp_path/'bundle')
    assert db.read_bytes()==original
    return folder


def test_bundle_replay_and_cli(bundle,capsys):
    result=replication.verify(bundle)
    assert result['passed'], result
    assert any(c['check']=='screening replay' for c in result['checks'])
    assert main(['verify',str(bundle)])==0
    assert 'fingerprint' in capsys.readouterr().out
    with pytest.raises(FileExistsError):replication.create(bundle/'screening.sqlite',bundle)


def test_zip_verified_without_extraction(bundle,tmp_path):
    archive=tmp_path/'bundle.zip'
    with zipfile.ZipFile(archive,'w') as z:
        for p in bundle.rglob('*'):
            if p.is_file():z.write(p,p.relative_to(bundle).as_posix())
    assert replication.verify(archive)['passed']


@pytest.mark.parametrize('change',['tamper','missing','extra'])
def test_file_changes_rejected(bundle,change):
    p=bundle/'screening'/'review.json'
    if change=='tamper':p.write_text('{}')
    elif change=='missing':p.unlink()
    else:(bundle/'unlisted.txt').write_text('extra')
    assert not replication.verify(bundle)['passed']


def test_rehashed_false_counts_fail_semantic_replay(bundle):
    path=bundle/'screening'/'review.json';value=json.loads(path.read_text());value['prisma']['identified']=999
    path.write_text(json.dumps(value));replication.seal(bundle)
    result=replication.verify(bundle)
    assert not result['passed']
    assert not next(c for c in result['checks'] if c['check']=='screening replay')['passed']


def test_unsafe_zip_paths_rejected(tmp_path):
    archive=tmp_path/'bad.zip'
    with zipfile.ZipFile(archive,'w') as z:z.writestr('../outside.txt','bad')
    with pytest.raises(ValueError,match='Unsafe'):replication.verify(archive)
    assert not (tmp_path/'outside.txt').exists()


def test_symlinks_rejected(bundle,tmp_path):
    (bundle/'linked').symlink_to(tmp_path/'run')
    with pytest.raises(ValueError,match='symlinks'):replication.verify(bundle)


def test_evidence_bundle_and_wrong_review_rejected(tmp_path):
    from slr.dashboard_demo import create_demo
    entry=create_demo(tmp_path/'demo',count=12,completed=True)
    folder=replication.create(entry['screening_db'],tmp_path/'bundle',entry['evidence_db'])
    assert replication.verify(folder)['passed']
    assert (folder/'evidence.sqlite').is_file()
    other=create_demo(tmp_path/'other',count=12,completed=True)
    with pytest.raises(ValueError,match='different review'):
        replication.create(entry['screening_db'],tmp_path/'wrong',other['evidence_db'])
    assert not (tmp_path/'wrong').exists()


def test_duplicate_zip_names_rejected(tmp_path):
    archive=tmp_path/'duplicate.zip'
    with zipfile.ZipFile(archive,'w') as z:
        z.writestr('same.txt','first')
        with pytest.warns(UserWarning):z.writestr('same.txt','second')
    with pytest.raises(ValueError,match='Duplicate'):replication.verify(archive)


def test_rehashed_false_ai_disclosure_fails_binding(bundle):
    path=bundle/'ai-disclosure.json';value=json.loads(path.read_text());value['stages'][0]['requests_prepared']=999
    path.write_text(json.dumps(value));replication.seal(bundle)
    result=replication.verify(bundle)
    assert not result['passed']
    assert not next(c for c in result['checks'] if c['check']=='AI disclosure binding')['passed']


def test_saved_protocol_document_retained_in_bundle(bundle,tmp_path):
    from slr import protocol
    protocol.save(bundle/'screening.sqlite',{},'A',expected_version=0)
    output=replication.create(bundle/'screening.sqlite',tmp_path/'with-protocol')
    assert (output/'protocol'/'PROTOCOL.md').is_file()
    assert replication.verify(output)['passed']


def test_unicode_bundle_verifies_with_a_legacy_default_encoding(bundle,tmp_path,monkeypatch):
    from slr import questions
    db=bundle/'screening.sqlite'
    questions.mutate(db,dict(actor='A',action='save',expected_revision=0,topic='研究テーマ',questions=['Quels effets pour les étudiants ?']))
    revision=questions.state(db)['revision']
    questions.mutate(db,dict(actor='A',action='request',expected_revision=revision,mode='refine',provider='ollama',model='研究モデル'))
    original=Path.write_text
    def legacy_write(path,data,encoding=None,errors=None,newline=None):
        return original(path,data,encoding=encoding or 'cp1252',errors=errors,newline=newline)
    monkeypatch.setattr(Path,'write_text',legacy_write)
    result=replication.create(db,tmp_path/'unicode-bundle')
    assert replication.verify(result)['passed']
    assert '研究モデル' in (result/'ai-disclosure.json').read_bytes().decode('utf-8')


def test_legacy_bundle_replays_without_retroactive_reasoning(bundle):
    path=bundle/'ai-assistance-and-revision-record.json'
    value=json.loads(path.read_text());value.pop('framework_reasoning');path.write_text(json.dumps(value),encoding='utf-8')
    replication.seal(bundle)
    manifest=bundle/replication.MANIFEST;value=json.loads(manifest.read_text());value.pop('question_framework_contract');manifest.write_text(json.dumps(value),encoding='utf-8')
    assert replication.verify(bundle)['passed']
