from conftest import defer_protocol
import json
from hashlib import sha256

import pytest

from slr import screening
from slr.cli import main, run
from slr.manuscript import capture, digest, export


@pytest.fixture
def ledger(tmp_path):
    run('configs/example_review.toml', tmp_path / 'run', 'Examples/demo_records.json')
    db = tmp_path / 'review.sqlite'
    screening.initialize(db, tmp_path / 'run', '<script>Review</script>', ['alice', 'bob'], 'carol', 'Criteria')
    defer_protocol(db)
    return db


def test_capture_is_read_only_and_run_is_bound(ledger, tmp_path):
    before = ledger.read_bytes()
    inputs = capture(ledger, tmp_path / 'run')
    assert ledger.read_bytes() == before
    assert 'reverified' in inputs['retrieval_verification']
    inputs['screening']['origin']['mode'] = 'changed'
    assert capture(ledger)['screening']['origin']['mode'] == 'offline-fixture'


def test_provisional_draft_and_claim_binding(ledger, tmp_path):
    inputs = capture(ledger)
    output = export(inputs, tmp_path / 'report')
    methods = (output / 'methods.md').read_text()
    assert 'Screening is incomplete' in methods
    assert 'no database search was executed' in methods
    assert 'no paired decisions' in methods
    assert 'No evidence findings' in methods
    provenance = json.loads((output / 'report-provenance.json').read_text())
    assert provenance['inputs_sha256'] == digest(inputs)
    for claim in provenance['claims']:
        value = inputs
        for key in claim['pointer'].strip('/').split('/'):
            value = value[key]
        assert digest(value) == claim['value_sha256']
    manifest = json.loads((output / 'manifest.json').read_text())
    assert not manifest['review_complete']
    for name, expected in manifest['files'].items():
        assert sha256((output / name).read_bytes()).hexdigest() == expected


def test_snapshot_reproduction_and_tampering(ledger, tmp_path):
    first = export(capture(ledger), tmp_path / 'first')
    assert main(['report', '--snapshot', str(first / 'report-inputs.json'), '--output', str(tmp_path / 'second')]) == 0
    for path in first.iterdir():
        assert path.read_bytes() == (tmp_path / 'second' / path.name).read_bytes()
    data = json.loads((first / 'report-inputs.json').read_text())
    data['screening']['prisma']['complete'] = True
    (first / 'report-inputs.json').write_text(json.dumps(data))
    with pytest.raises(SystemExit):
        main(['report', '--snapshot', str(first / 'report-inputs.json'), '--output', str(tmp_path / 'bad')])
    assert not (tmp_path / 'bad').exists()


def test_never_overwrites_and_html_escapes(ledger, tmp_path):
    inputs = capture(ledger)
    inputs['screening']['origin']['mode'] = '<script>alert(1)</script>'
    output = export(inputs, tmp_path / 'report')
    assert '<script>' not in (output / 'report.html').read_text()
    with pytest.raises(FileExistsError):
        export(inputs, output)


def test_complete_review_and_undefined_kappa(ledger, tmp_path):
    for record in screening.snapshot(ledger)['records']:
        for actor in ('alice', 'bob'):
            screening.decide(ledger, record['record_id'], actor, 'title', 'exclude', 'Wrong population', expected_version=1)
    output = export(capture(ledger), tmp_path / 'complete')
    text = (output / 'methods.md').read_text()
    assert 'Screening is recorded as complete' in text
    assert 'kappa undefined' in text
    assert 'one identical category' in text


def test_committed_wal_is_captured(ledger):
    import sqlite3
    connection = sqlite3.connect(ledger)
    try:
        connection.execute('PRAGMA journal_mode=WAL')
        connection.execute("UPDATE review SET name='Committed WAL review'")
        connection.commit()
        assert capture(ledger)['screening']['name'] == 'Committed WAL review'
    finally:
        connection.close()
