import json
from concurrent.futures import ThreadPoolExecutor
from hashlib import sha256
import sqlite3
from xml.etree import ElementTree as ET

import pytest

from slr.cli import main, run
from slr.models import Record
from slr.reporting import write_json, write_results
from slr.review_cli import export_review
from slr import screening as s


@pytest.fixture
def ledger(tmp_path):
    folder = tmp_path / 'run'
    run('configs/example_review.toml', folder, 'Examples/demo_records.json')
    db = tmp_path / 'review.sqlite'
    assert s.initialize(db, folder, 'Example review', ['alice', 'bob'], 'carol', 'Example criteria') == 2
    return db


def vote(db, record, actor, value, stage='title', reason='', version=1, adjudicate=False):
    s.decide(db, record, actor, stage, value, reason, adjudicate=adjudicate, expected_version=version)


def include_title(db, record='R000001'):
    for actor in ('alice', 'bob'):
        vote(db, record, actor, 'include')


def retrieve(db, record='R000001', value='retrieved', reason=''):
    s.record_retrieval(db, record, 'alice', value, reason, expected_version=1)


def test_initial_pending_and_blind_queue(ledger):
    assert s.snapshot(ledger)['prisma']['title_pending'] == 2
    assert not s.snapshot(ledger)['prisma']['complete']
    vote(ledger, 'R000001', 'alice', 'include')
    queue = s.snapshot(ledger, reviewer='bob')
    assert len(queue['queue']) == 2 and queue['criteria_version'] == 1
    assert 'events' not in queue and 'title' not in queue['queue'][0]
    assert len(s.snapshot(ledger, reviewer='alice')['queue']) == 1
    with pytest.raises(ValueError, match='Unknown reviewer'):
        s.snapshot(ledger, reviewer='eve')


def test_conflict_blocks_downstream_and_requires_adjudicator(ledger):
    vote(ledger, 'R000001', 'alice', 'include')
    vote(ledger, 'R000001', 'bob', 'exclude', reason='Wrong population')
    assert s.snapshot(ledger)['prisma']['title_conflicts'] == 1
    with pytest.raises(ValueError, match='resolve to include'):
        retrieve(ledger)
    with pytest.raises(ValueError, match='role'):
        vote(ledger, 'R000001', 'alice', 'include', reason='Resolution', adjudicate=True)
    vote(ledger, 'R000001', 'carol', 'include', reason='Eligible population', adjudicate=True)
    retrieve(ledger)
    assert s.snapshot(ledger)['prisma']['reports_assessed'] == 1
    with pytest.raises(ValueError, match='conflicting'):
        vote(ledger, 'R000001', 'carol', 'exclude', reason='Changed mind', adjudicate=True)


def test_eligibility_requires_retrieved_fulltext(ledger):
    with pytest.raises(ValueError, match='title screening'):
        vote(ledger, 'R000001', 'alice', 'include', stage='fulltext')
    include_title(ledger)
    with pytest.raises(ValueError, match='marked retrieved'):
        vote(ledger, 'R000001', 'alice', 'include', stage='fulltext')
    retrieve(ledger, value='not_retrieved', reason='Library request unsuccessful')
    with pytest.raises(ValueError, match='marked retrieved'):
        vote(ledger, 'R000001', 'alice', 'include', stage='fulltext')
    assert s.snapshot(ledger)['prisma']['reports_not_retrieved'] == 1
    with pytest.raises(ValueError, match='already recorded'):
        retrieve(ledger)


def test_complete_flow_and_study_link(ledger, tmp_path):
    include_title(ledger)
    retrieve(ledger)
    for actor in ('alice', 'bob'):
        vote(ledger, 'R000001', actor, 'include', stage='fulltext')
        vote(ledger, 'R000002', actor, 'exclude', reason='Wrong population')
    data = s.snapshot(ledger)
    assert data['prisma']['included_reports_without_study'] == 1
    assert not data['prisma']['complete']
    with pytest.raises(ValueError, match='adjudicator'):
        s.link_study(ledger, 'R000001', 'alice', 'S1', expected_version=1)
    s.link_study(ledger, 'R000001', 'carol', 'S1', expected_version=1)
    counts = export_review(ledger, tmp_path / 'report')
    assert counts['complete'] and counts['studies_included'] == 1
    assert counts['identified'] == counts['duplicates_removed'] + counts['records_to_screen']
    assert counts['records_to_screen'] == counts['records_excluded'] + counts['reports_sought']
    assert counts['reports_sought'] == counts['reports_not_retrieved'] + counts['reports_assessed']
    assert counts['reports_assessed'] == counts['reports_excluded'] + counts['reports_included']
    assert len(json.loads((tmp_path / 'report/records.json').read_text())) == 1
    ET.parse(tmp_path / 'report/prisma.svg')
    manifest = json.loads((tmp_path / 'report/manifest.json').read_text())
    assert all(sha256((tmp_path / 'report' / name).read_bytes()).hexdigest() == digest for name, digest in manifest['files'].items())
    with pytest.raises(FileExistsError):
        export_review(ledger, tmp_path / 'report')


def test_different_exclusion_reasons_require_resolution(ledger):
    include_title(ledger)
    retrieve(ledger)
    vote(ledger, 'R000001', 'alice', 'exclude', stage='fulltext', reason='Wrong design')
    vote(ledger, 'R000001', 'bob', 'exclude', stage='fulltext', reason='Wrong population')
    assert s.snapshot(ledger)['prisma']['eligibility_conflicts'] == 1
    vote(ledger, 'R000001', 'carol', 'exclude', stage='fulltext', reason='Wrong design <primary> & confirmed', adjudicate=True)
    data = s.snapshot(ledger)
    assert data['prisma']['exclusion_reasons'] == {'Wrong design <primary> & confirmed': 1}
    from slr.review_cli import flow_svg
    svg = flow_svg(data['prisma'])
    ET.fromstring(svg)
    assert '&lt;primary&gt; &amp;' in svg


def test_new_criteria_resets_state_but_preserves_audit(ledger):
    include_title(ledger)
    retrieve(ledger)
    assert s.revise_criteria(ledger, 'Revised criteria', expected_version=1) == 2
    data = s.snapshot(ledger)
    assert data['prisma']['title_pending'] == 2 and data['prisma']['reports_sought'] == 0
    assert len(data['events']) == 3 and len(data['criteria_history']) == 2
    with pytest.raises(ValueError, match='Stale'):
        vote(ledger, 'R000001', 'alice', 'include')
    vote(ledger, 'R000001', 'alice', 'include', version=2)
    with pytest.raises(ValueError, match='already exists'):
        s.revise_criteria(ledger, 'Example criteria', expected_version=2)


def test_events_immutable_and_duplicate_rejected(ledger):
    vote(ledger, 'R000001', 'alice', 'include')
    with pytest.raises(ValueError, match='already recorded'):
        vote(ledger, 'R000001', 'alice', 'exclude', reason='Error')
    with sqlite3.connect(ledger) as conn:
        with pytest.raises(sqlite3.IntegrityError, match='append-only'):
            conn.execute('DELETE FROM events')
        with pytest.raises(sqlite3.IntegrityError, match='immutable'):
            conn.execute("UPDATE criteria SET text='changed'")


def test_concurrent_duplicate_vote_is_atomic(ledger):
    def submit(_):
        try:
            vote(ledger, 'R000001', 'alice', 'include')
            return True
        except ValueError:
            return False
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sum(pool.map(submit, [1, 2])) == 1
    assert len(s.snapshot(ledger)['events']) == 1


@pytest.mark.parametrize('actor,value,reason', [('eve', 'include', ''), ('alice', 'exclude', '')])
def test_invalid_actor_or_missing_reason(ledger, actor, value, reason):
    with pytest.raises(ValueError):
        vote(ledger, 'R000001', actor, value, reason=reason)
    assert not s.snapshot(ledger)['events']


def test_unknown_record(ledger):
    with pytest.raises(ValueError, match='Unknown record'):
        vote(ledger, 'R999999', 'alice', 'include')


def test_missing_database_not_created(tmp_path):
    db = tmp_path / 'missing.sqlite'
    with pytest.raises(ValueError, match='does not exist'):
        s.snapshot(db)
    assert not db.exists()


def test_modified_run_rejected(tmp_path):
    folder = tmp_path / 'run'
    run('configs/example_review.toml', folder, 'Examples/demo_records.json')
    (folder / 'records.json').write_text('[]')
    with pytest.raises(ValueError, match='hash mismatch'):
        s.initialize(tmp_path / 'bad.sqlite', folder, 'Review', ['a', 'b'], 'c', 'Criteria')
    assert not (tmp_path / 'bad.sqlite').exists()


def test_multiple_reports_can_share_one_study(ledger):
    for record in ('R000001', 'R000002'):
        include_title(ledger, record)
        retrieve(ledger, record)
        for actor in ('alice', 'bob'):
            vote(ledger, record, actor, 'include', stage='fulltext')
        s.link_study(ledger, record, 'carol', 'S1', expected_version=1)
    counts = s.snapshot(ledger)['prisma']
    assert counts['complete'] and counts['reports_included'] == 2 and counts['studies_included'] == 1


def test_review_cli_and_stale_version(ledger, capsys):
    assert main(['review', 'queue', '--db', str(ledger), '--reviewer', 'alice']) == 0
    assert len(json.loads(capsys.readouterr().out)['queue']) == 2
    assert main(['review', 'decide', '--db', str(ledger), '--version', '1', '--record', 'R000001', '--actor', 'alice', '--stage', 'title', '--decision', 'include']) == 0
    with pytest.raises(SystemExit) as error:
        main(['review', 'decide', '--db', str(ledger), '--version', '9', '--record', 'R000001', '--actor', 'bob', '--stage', 'title', '--decision', 'include'])
    assert error.value.code == 1
