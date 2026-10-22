from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import sqlite3

import pytest

from slr import protocol as p
from slr import screening as s
from slr.cli import main, run
from slr.review_cli import export_review

EXAMPLE = json.loads(Path('configs/example_protocol.json').read_text(encoding='utf-8'))


def status(report, item):
    return next(i['status'] for i in report['items'] if i['item'] == item)


@pytest.fixture
def ledger(tmp_path):
    run('configs/example_review.toml', tmp_path / 'run', 'Examples/demo_records.json')
    db = tmp_path / 'review.sqlite'
    s.initialize(db, tmp_path / 'run', 'Protocol review', ['alice', 'bob'], 'carol', 'Criteria v1')
    return db


def amended(**changes):
    value = deepcopy(EXAMPLE)
    value.update(changes)
    return value


# PRISMA-P completeness

def test_example_protocol_is_complete_with_conditional_items():
    report = p.checklist(EXAMPLE)
    assert report['complete'] and report['missing'] == []
    assert len(report['items']) == 26
    assert {i['item'] for i in report['items'] if i['status'] == 'not_applicable'} == {'1b', '5c', '15d'}


def test_empty_draft_is_valid_but_lists_missing_items():
    report = p.checklist({})
    assert not report['complete']
    assert {'1a', '2', '3a', '6', '7', '8', '9', '10', '17'} <= set(report['missing'])
    assert status(report, '1b') == 'not_applicable' and status(report, '5c') == 'not_applicable'
    # Unknown synthesis type: both quantitative and narrative items stay applicable.
    assert {'15b', '15c', '15d'} <= set(report['missing'])


def test_non_quantitative_synthesis_switches_items():
    draft = amended(synthesis={**EXAMPLE['synthesis'], 'quantitative': False, 'methods': '', 'additional_analyses': '', 'non_quantitative': ''})
    report = p.checklist(draft)
    assert status(report, '15b') == status(report, '15c') == 'not_applicable'
    assert report['missing'] == ['15d']


def test_update_sponsor_and_contact_conditions():
    report = p.checklist(amended(is_update=True, support={'sources': 'Grant X', 'sponsor': 'Funder Y', 'sponsor_role': ''},
                                 authors=[{**a, 'contact': False} for a in EXAMPLE['authors']]))
    assert set(report['missing']) == {'1b', '5c', '3a'}


@pytest.mark.parametrize('change,message', [
    ({'unknown_field': 'x'}, 'Unknown protocol field: unknown_field'),
    ({'authors': [{'name': 'A', 'orcid': 'x'}]}, r'Unknown protocol field: authors\[0\].orcid'),
    ({'title': 5}, 'title must be text'),
    ({'is_update': 'no'}, 'is_update must be true or false'),
    ({'anticipated_start': '2026-13-01'}, 'YYYY-MM-DD'),
    ({'anticipated_start': '2027-01-01'}, 'must not be after'),
    ({'objectives': {'framework': 'PIZZA'}}, 'framework must be one of'),
    ({'stage': 'thinking'}, 'stage must be one of'),
    ({'objectives': {'elements': {'Population': 3}}}, 'elements must map'),
    ({'keywords': 'ai'}, 'keywords must be a list'),
])
def test_validation_errors(change, message):
    with pytest.raises(ValueError, match=message):
        p.validate(amended(**change))


# Registry drafts

def test_prospero_and_osf_fields_map_protocol_content():
    prospero = {f['field']: f for f in p.registry_fields(EXAMPLE, 'prospero')['fields']}
    assert prospero['Named contact']['value'] == 'Alice Example'
    assert prospero['Named contact email']['value'] == 'alice@example.org'
    assert prospero['Participants/population']['value'] == 'Learners in formal education settings'
    assert prospero['Comparator(s)/control']['value'] == 'No support or non-AI support'
    assert 'OpenAlex via OpenAlex API (planned search 2026-02-01)' in prospero['Searches']['value']
    assert prospero['Details of any existing review of the same topic by the same authors']['status'] == 'needs_entry'
    osf = p.registry_fields(EXAMPLE, 'osf')
    assert osf['template'].startswith('OSF Generalized') and 'verify' in osf['notice']
    assert {f['field']: f['value'] for f in osf['fields']}['Interfaces'] == 'OpenAlex API; Crossref REST API'


def test_registry_needs_entry_for_draft():
    fields = p.registry_fields({'title': 'Draft'}, 'prospero')
    assert 'Review title' not in fields['needs_entry'] and 'Review question' in fields['needs_entry']


# Append-only versions and criteria links

def test_first_version_and_amendment_history(ledger):
    assert p.save(ledger, EXAMPLE, 'carol', expected_version=0) == 1
    with pytest.raises(ValueError, match='Stale protocol version: current version is 1'):
        p.save(ledger, EXAMPLE, 'carol', expected_version=0)
    change = amended(outcomes={**EXAMPLE['outcomes'], 'additional': 'Engagement only'}, stage='searching')
    assert p.save(ledger, change, 'alice', expected_version=1,
                  amendment={'description': 'Narrowed additional outcomes', 'rationale': 'Feasibility'}) == 2
    data = p.state(ledger)
    assert data['version'] == 2 and data['protocol'] == p.validate(change)
    first, second = data['history']
    assert first['amendment'] is None and first['changed_sections'] == sorted(EXAMPLE)
    assert second['amendment'] == {'description': 'Narrowed additional outcomes', 'rationale': 'Feasibility'}
    assert second['changed_sections'] == ['outcomes', 'stage'] and second['actor'] == 'alice'
    canonical = json.dumps(p.validate(change), ensure_ascii=False, sort_keys=True, separators=(',', ':'))
    assert second['sha256'] == sha256(canonical.encode()).hexdigest()


@pytest.mark.parametrize('amendment,message', [
    (None, 'description and a rationale'),
    ({'description': 'Changed', 'rationale': ' '}, 'description and a rationale'),
    ({'description': 'Changed'}, 'description and a rationale'),
])
def test_amendments_require_description_and_rationale(ledger, amendment, message):
    p.save(ledger, EXAMPLE, 'carol', expected_version=0)
    with pytest.raises(ValueError, match=message):
        p.save(ledger, amended(stage='searching'), 'carol', expected_version=1, amendment=amendment)


def test_rejects_first_amendment_unchanged_content_and_unknown_actor(ledger):
    with pytest.raises(ValueError, match='first protocol version'):
        p.save(ledger, EXAMPLE, 'carol', expected_version=0, amendment={'description': 'x', 'rationale': 'y'})
    with pytest.raises(ValueError, match='not assigned'):
        p.save(ledger, EXAMPLE, 'mallory', expected_version=0)
    p.save(ledger, EXAMPLE, 'carol', expected_version=0)
    with pytest.raises(ValueError, match='unchanged'):
        p.save(ledger, deepcopy(EXAMPLE), 'carol', expected_version=1, amendment={'description': 'x', 'rationale': 'y'})


def test_invalid_protocol_is_not_saved(ledger):
    with pytest.raises(ValueError):
        p.save(ledger, {'title': 1}, 'carol', expected_version=0)
    assert p.state(ledger)['version'] == 0


def test_protocol_history_is_append_only(ledger):
    p.save(ledger, EXAMPLE, 'carol', expected_version=0)
    with sqlite3.connect(ledger) as conn:
        for statement in ("UPDATE protocol SET actor='eve'", 'DELETE FROM protocol'):
            with pytest.raises(sqlite3.DatabaseError, match='append-only protocol'):
                conn.execute(statement)


def test_criteria_revisions_must_be_documented_by_amendments(ledger):
    p.save(ledger, EXAMPLE, 'carol', expected_version=0)
    assert p.state(ledger)['undocumented_criteria_revisions'] == []
    s.revise_criteria(ledger, 'Criteria v2', expected_version=1)
    data = p.state(ledger)
    assert data['undocumented_criteria_revisions'] == [2] and data['criteria_version'] == 2
    p.save(ledger, amended(eligibility={**EXAMPLE['eligibility'], 'report_characteristics': 'Published 2018-2025'}), 'carol',
           expected_version=1, amendment={'description': 'Widened date range', 'rationale': 'Pilot found earlier key studies'})
    data = p.state(ledger)
    assert data['undocumented_criteria_revisions'] == []
    assert [link['protocol_versions'] for link in data['criteria_links']] == [[1], [2]]
    assert data['history'][1]['criteria_version'] == 2


def test_criteria_revision_before_any_protocol_is_reported(ledger):
    s.revise_criteria(ledger, 'Criteria v2', expected_version=1)
    data = p.state(ledger)
    assert data['version'] == 0 and data['protocol'] is None and data['undocumented_criteria_revisions'] == [2]


def test_reading_state_does_not_modify_older_ledgers(ledger):
    before = ledger.read_bytes()
    assert p.state(ledger)['version'] == 0
    with sqlite3.connect(ledger) as conn:
        assert conn.execute("SELECT 1 FROM sqlite_master WHERE name='protocol'").fetchone() is None
    assert ledger.read_bytes() == before


# Exports and CLI

def test_export_from_file(tmp_path):
    source = tmp_path / 'protocol.json'
    source.write_text(json.dumps(amended(title='Pipes | and\nnewlines')), encoding='utf-8')
    result = p.export(tmp_path / 'out', protocol_file=source)
    out = tmp_path / 'out'
    assert result['prisma_p_complete']
    names = {'protocol.json', 'prisma-p-checklist.json', 'prisma-p-checklist.md', 'prospero-fields.json', 'prospero-fields.md',
             'osf-fields.json', 'osf-fields.md', 'PROTOCOL.md', 'manifest.json'}
    assert {f.name for f in out.iterdir()} == names
    manifest = json.loads((out / 'manifest.json').read_text(encoding='utf-8'))
    assert manifest['origin']['mode'] == 'protocol-file-unversioned'
    assert all(sha256((out / n).read_bytes()).hexdigest() == h for n, h in manifest['files'].items())
    assert 'Pipes \\| and<br>newlines' in (out / 'prospero-fields.md').read_text(encoding='utf-8')
    with pytest.raises(FileExistsError):
        p.export(tmp_path / 'out', protocol_file=source)


def test_export_from_ledger_includes_amendments(ledger, tmp_path):
    with pytest.raises(ValueError, match='no saved protocol'):
        p.export(tmp_path / 'none', database=ledger)
    p.save(ledger, EXAMPLE, 'carol', expected_version=0)
    s.revise_criteria(ledger, 'Criteria v2', expected_version=1)
    p.export(tmp_path / 'out', database=ledger)
    history = json.loads((tmp_path / 'out/protocol-history.json').read_text(encoding='utf-8'))
    assert history['undocumented_criteria_revisions'] == [2]
    text = (tmp_path / 'out/amendments.md').read_text(encoding='utf-8')
    assert 'Version 1' in text and 'Initial protocol' in text and 'without a protocol amendment:** 2' in text
    with pytest.raises(ValueError, match='exactly one'):
        p.export(tmp_path / 'both', database=ledger, protocol_file='configs/example_protocol.json')


def test_review_export_carries_protocol(ledger, tmp_path):
    export_review(ledger, tmp_path / 'without')
    assert not (tmp_path / 'without/protocol.json').exists()
    p.save(ledger, EXAMPLE, 'carol', expected_version=0)
    export_review(ledger, tmp_path / 'with')
    data = json.loads((tmp_path / 'with/protocol.json').read_text(encoding='utf-8'))
    assert data['version'] == 1
    assert 'protocol.json' in json.loads((tmp_path / 'with/manifest.json').read_text(encoding='utf-8'))['files']


def test_cli_workflow(ledger, tmp_path, capsys):
    assert main(['protocol', 'check', '--file', 'configs/example_protocol.json']) == 0
    assert json.loads(capsys.readouterr().out)['complete']
    assert main(['protocol', 'save', '--db', str(ledger), '--file', 'configs/example_protocol.json', '--actor', 'carol', '--expected-version', '0']) == 0
    assert json.loads(capsys.readouterr().out) == {'protocol_version': 1}
    changed = tmp_path / 'changed.json'
    changed.write_text(json.dumps(amended(stage='screening')), encoding='utf-8')
    with pytest.raises(SystemExit) as error:
        main(['protocol', 'save', '--db', str(ledger), '--file', str(changed), '--actor', 'carol', '--expected-version', '1', '--amendment', 'Stage'])
    assert error.value.code == 1
    assert main(['protocol', 'save', '--db', str(ledger), '--file', str(changed), '--actor', 'carol', '--expected-version', '1',
                 '--amendment', 'Stage update', '--rationale', 'Screening started']) == 0
    capsys.readouterr()
    assert main(['protocol', 'status', '--db', str(ledger)]) == 0
    assert json.loads(capsys.readouterr().out)['version'] == 2
    assert main(['protocol', 'export', '--db', str(ledger), '--output', str(tmp_path / 'export')]) == 0
    assert (tmp_path / 'export/osf-fields.md').exists()
