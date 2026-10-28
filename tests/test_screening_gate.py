import json
import sqlite3
import pytest
from slr import screening as s, questions, protocol, ai_disclosure
from slr.cli import run
from slr.review_cli import main
from slr.manuscript import capture, render


@pytest.fixture
def db(tmp_path):
    run('configs/example_review.toml', tmp_path/'run', 'Examples/demo_records.json')
    path=tmp_path/'review.sqlite'
    s.initialize(path,tmp_path/'run','Synthetic imported review',['A','B'],'C','Criteria')
    with sqlite3.connect(path) as c:
        c.execute("UPDATE review SET origin=json_set(origin,'$.mode','import')")
    return path


def defer(db):
    gate=s.screening_access(db)
    return s.screening_access(db,'C','Retrospective imported library; protocol is being reconstructed transparently.',expected_version=s.snapshot(db)['criteria_version'],expected_binding=gate['binding'])


def vote(db):
    s.decide(db,'R000001','A','title','include',expected_version=1)


def test_import_gate_exception_revocation_and_readable_history(db):
    with pytest.raises(ValueError,match='Screening blocked'):vote(db)
    gate=defer(db);assert gate['basis']=='protocol-deferred'
    vote(db)
    s.screening_access(db,'C','Exception withdrawn pending protocol completion.',expected_version=1,expected_binding=gate['binding'],revoke=gate['exception']['sequence'])
    assert len(s.snapshot(db)['events'])==1
    with pytest.raises(ValueError,match='Screening blocked'):
        s.decide(db,'R000002','B','title','include',expected_version=1)
    report=render(capture(db))
    assert 'protocol-deferred' in report['methods.md'] or 'screening' in report['methods.md']


@pytest.mark.parametrize('change',['criteria','questions','protocol','corpus'])
def test_exception_invalidated_by_changes(db,change):
    defer(db)
    if change=='criteria':s.revise_criteria(db,'New criteria',expected_version=1)
    elif change=='questions':
        questions.mutate(db,dict(action='save',actor='A',expected_revision=0,topic='Synthetic',questions=['What changes?']))
        questions.mutate(db,dict(action='approve',actor='A',expected_revision=1))
    elif change=='protocol':protocol.save(db,{},'A',expected_version=0)
    else:
        with sqlite3.connect(db) as c:c.execute("UPDATE review SET origin=json_set(origin,'$.new','corpus')")
    assert not s.screening_access(db)['allowed']


def test_exception_rejects_wrong_actor_and_stale_view(db):
    gate=s.screening_access(db)
    with pytest.raises(ValueError,match='adjudicator'):
        s.screening_access(db,'A','A substantive exception rationale.',expected_version=1,expected_binding=gate['binding'])
    with pytest.raises(ValueError,match='context changed'):
        s.screening_access(db,'C','A substantive exception rationale.',expected_version=1,expected_binding={})
    assert not s.screening_access(db)['allowed']


def test_cli_requires_inspected_context_and_reports_deviation(db,tmp_path,capsys):
    context=tmp_path/'context.json';context.write_text(json.dumps(s.screening_access(db)))
    assert main(['screening-access','--db',str(db),'--actor','C','--version','1','--context',str(context),'--rationale','Retrospective library with explicitly deferred protocol.'])==0
    assert s.screening_access(db)['allowed']
    assert 'Retrospective library' in render(capture(db))['methods.md']


def test_ai_disclosure_unknown_is_not_zero_and_has_model_identity(db):
    assert ai_disclosure.capture(db)['stages'][0]['coverage']=='history unavailable'
    questions.mutate(db,dict(action='save',actor='A',expected_revision=0,topic='Synthetic',questions=['What works?']))
    state=questions.mutate(db,dict(action='request',mode='refine',actor='A',expected_revision=1,provider='ollama',model='synthetic:1'))
    request=state['history'][-1]['content']['packet']
    envelope=dict(request_id=request['request_id'],request_sha256=request['request_sha256'],provider='ollama',requested_model='synthetic:1',model='synthetic:1',model_digest='test-digest',output={'items':[{'field':'question','text':'What works in context?','rationale':'Clarify scope'}]})
    state=questions.record_response(db,envelope)
    questions.mutate(db,dict(action='decision',decision='reject',actor='A',expected_revision=state['revision'],proposal_sequence=state['history'][-1]['sequence'],index=0))
    disclosure=ai_disclosure.capture(db);stage=disclosure['stages'][0]
    assert stage['requests_prepared']==1 and stage['responses_recorded']==1
    assert stage['human_decisions']==dict(accept=0,edit=0,reject=1)
    assert stage['models'][0]['model_digest']=='test-digest'
    assert 'instructions' not in json.dumps(disclosure)
    assert 'AI assistance' in render(capture(db))['methods.md']


def test_deduplication_notice_matches_recorded_method(db):
    assert 'Matching normalized DOI;' in s.snapshot(db)['prisma']['deduplication_notice']
    with sqlite3.connect(db) as c:
        c.execute("UPDATE review SET origin=json_set(origin,'$.deduplication','doi-or-source-id-v1')")
    notice=s.snapshot(db)['prisma']['deduplication_notice']
    assert 'exact source/ID' in notice and 'no fuzzy' in notice


def test_legacy_evidence_scope_ignores_only_new_derived_reporting_fields(db):
    from slr import evidence
    frozen=s.snapshot(db)
    for key in ('screening_access','screening_deviations'):frozen.pop(key)
    for key in ('deduplication_method','deduplication_notice'):frozen['prisma'].pop(key)
    scope={'screening_path':str(db),'snapshot':frozen,'snapshot_sha256':evidence.digest(frozen)}
    assert evidence.scope_current(scope)
    defer(db)
    assert evidence.scope_current(scope)
    vote(db)
    assert not evidence.scope_current(scope)
