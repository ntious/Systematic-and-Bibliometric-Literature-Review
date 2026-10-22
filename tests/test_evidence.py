from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import sqlite3
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError, URLError

import pytest

from slr import evidence as e
from slr import screening as s
from slr.cli import main, run
from slr.evidence_ai import ModelError, run_openai
from slr.evidence_cli import export_evidence

FRAMEWORK = {'id': 'test-v1', 'fields': [{'id': 'sample_size', 'description': 'Reported sample size'},
             {'id': 'findings', 'description': 'Reported findings'}],
             'appraisal': {'id': 'custom-test-v1', 'description': 'Illustrative only',
             'domains': [{'id': 'selection', 'description': 'Selection description', 'judgments': ['low', 'high', 'unclear']}]}}


@pytest.fixture
def ledger(tmp_path):
    run_folder = tmp_path / 'retrieval'
    run('configs/example_review.toml', run_folder, 'Examples/demo_records.json')
    screening = tmp_path / 'screening.sqlite'
    s.initialize(screening, run_folder, 'Evidence test', ['alice', 'bob'], 'carol', 'Example criteria')
    for actor in ('alice', 'bob'):
        s.decide(screening, 'R000001', actor, 'title', 'include', expected_version=1)
        s.decide(screening, 'R000002', actor, 'title', 'exclude', 'Wrong population', expected_version=1)
    s.record_retrieval(screening, 'R000001', 'alice', 'retrieved', expected_version=1)
    for actor in ('alice', 'bob'):
        s.decide(screening, 'R000001', actor, 'fulltext', 'include', expected_version=1)
    s.link_study(screening, 'R000001', 'carol', 'S1', expected_version=1)
    db = tmp_path / 'evidence.sqlite'
    assert e.initialize(db, screening, FRAMEWORK) == 1
    source = tmp_path / 'source.txt'
    source.write_text('We surveyed 120 participants.\fNo causal effect was estimated.', encoding='utf-8')
    assert e.add_source(db, 'R000001', source, 'fulltext', 'Synthetic source') == 1
    return db


def item(key='sample_size', value='120 participants', quote='120 participants', page=1):
    return {'key': key, 'status': 'reported', 'value': value, 'anchors': [{'source_id': 1, 'page': page, 'quote': quote}],
            'evidence_ids': [], 'uncertainty': 'low', 'rationale': 'Based on supplied source.'}


def submit(db, value=None, task='extract', actor='alice'):
    return e.submit(db, task, 'R000001' if task != 'gaps' else None, {'items': [value or item()]}, {'method': 'manual', 'actor': actor})[0]


def approve(db, proposal, revision=0):
    return e.review(db, proposal, 'bob', 'approve', 'Checked source support and uncertainty.', support_confirmed=True, revision=revision)


def envelope(request, output=None):
    return {'request_id': request['request_id'], 'request_sha256': request['request_sha256'],
            'provider': 'test-provider', 'model': 'test-model-v1', 'generated_utc': '2026-10-22T00:00:00Z',
            'response_id': 'test-1', 'usage': None, 'output': output or {'items': [item()]}}


def test_prepare_snapshots_pages_framework_and_hash(ledger):
    request = e.prepare(ledger, 'extract', 'R000001')
    packet = request['packet']
    assert e.digest(packet) == request['request_sha256']
    assert packet['data']['sources'][0]['pages'][1]['page'] == 2
    assert packet['framework']['id'] == 'test-v1'
    assert packet['response_schema']['properties']['items']['items']['properties']['key']['enum'] == ['sample_size', 'findings']
    assert 'untrusted data' in packet['instructions']
    assert e.get_request(ledger, request['request_id']) == request
    with pytest.raises(ValueError, match='max_chars'):
        e.prepare(ledger, 'extract', 'R000001', max_chars=10)
    assert len(e.snapshot(ledger)['requests']) == 1


def test_manual_proposals_pending_until_human_confirmation(ledger):
    proposal = submit(ledger)
    data = e.snapshot(ledger)
    assert data['pending'] == 1 and not data['complete']
    assert data['proposals'][0]['checks']['anchors'][0]['start'] == 12
    with pytest.raises(ValueError, match='explicit human'):
        e.review(ledger, proposal, 'bob', 'approve', 'Checked')
    assert approve(ledger, proposal) == 1
    assert e.snapshot(ledger)['coverage'][0]['proposal_id'] == proposal


@pytest.mark.parametrize('changes', [{'anchors': []}, {'anchors': [{'source_id': 999, 'page': 1, 'quote': '120'}]},
    {'anchors': [{'source_id': 1, 'page': 2, 'quote': '120 participants'}]},
    {'anchors': [{'source_id': 1, 'page': 1, 'quote': '999 participants'}]}])
def test_missing_or_invalid_quote_flagged_and_cannot_be_approved(ledger, changes):
    value = item()
    value.update(changes)
    proposal = submit(ledger, value)
    assert e.snapshot(ledger)['flagged'] == 1
    with pytest.raises(ValueError, match='Unsupported'):
        approve(ledger, proposal)
    assert not e.snapshot(ledger)['proposals'][0]['reviews']


def test_partial_response_is_atomic_on_schema_error(ledger):
    bad = item()
    bad['uncertainty'] = 'certain'
    with pytest.raises(ValueError, match='uncertainty'):
        e.submit(ledger, 'extract', 'R000001', {'items': [item(), bad]}, {'method': 'manual', 'actor': 'alice'})
    assert not e.snapshot(ledger)['batches']


def test_quote_whitespace_is_exact(ledger):
    value = item(quote=' 120 participants ')
    proposal = submit(ledger, value)
    assert e.snapshot(ledger)['flagged'] == 1
    with pytest.raises(ValueError):
        approve(ledger, proposal)


def test_not_reported_is_explicit_not_missing_or_zero(ledger):
    value = item()
    value.update(status='not_reported', value=None, anchors=[], uncertainty='unknown')
    proposal = submit(ledger, value)
    approve(ledger, proposal)
    row = e.snapshot(ledger)['coverage'][0]
    assert row['status'] == 'not_reported' and row['proposal_id'] == proposal
    bad = deepcopy(value)
    bad['value'] = '0'
    with pytest.raises(ValueError, match='null'):
        submit(ledger, bad)


def test_appraisal_framework_and_no_aggregate_score(ledger):
    proposal = submit(ledger, item('selection', 'unclear'), task='appraise')
    approve(ledger, proposal)
    with pytest.raises(ValueError, match='outside'):
        submit(ledger, item('selection', 'invented-score'), task='appraise')
    assert e.snapshot(ledger)['coverage'][-1]['proposal_id'] == proposal


def test_review_revisions_preserve_history_and_require_explicit_replacement(ledger):
    first = submit(ledger)
    approve(ledger, first)
    second = submit(ledger, item(value='120 people'))
    with pytest.raises(ValueError, match='Another approved'):
        approve(ledger, second)
    with pytest.raises(ValueError, match='Stale'):
        e.review(ledger, first, 'bob', 'reject', 'Correction', revision=0)
    e.review(ledger, first, 'bob', 'reject', 'Replacing with a clearer value', revision=1)
    approve(ledger, second)
    data = e.snapshot(ledger)
    assert len(data['proposals'][0]['reviews']) == 2
    assert data['coverage'][0]['proposal_id'] == second


def test_concurrent_review_is_atomic(ledger):
    proposal = submit(ledger)
    def work(_):
        try:
            approve(ledger, proposal)
            return True
        except ValueError:
            return False
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sum(pool.map(work, [1, 2])) == 1
    assert e.snapshot(ledger)['proposals'][0]['revision'] == 1


def test_immutable_history_and_duplicate_source(ledger):
    source = ledger.parent / 'source.txt'
    with pytest.raises(ValueError, match='already attached'):
        e.add_source(ledger, 'R000001', source, 'fulltext', 'Again')
    with sqlite3.connect(ledger) as conn:
        with pytest.raises(sqlite3.IntegrityError, match='append-only'):
            conn.execute('DELETE FROM sources')
    with pytest.raises(ValueError, match='non-included'):
        e.add_source(ledger, 'R000002', source, 'excerpt', 'Excluded')


def test_ai_import_provenance_and_hash_validation(ledger):
    request = e.prepare(ledger, 'extract', 'R000001')
    response = envelope(request)
    proposal = e.import_ai(ledger, response)[0]
    data = e.snapshot(ledger)
    assert data['proposals'][0]['state'] == 'pending'
    assert data['batches'][0]['producer']['model'] == 'test-model-v1'
    assert data['batches'][0]['producer']['request_sha256'] == request['request_sha256']
    with pytest.raises(ValueError, match='already been imported'):
        e.import_ai(ledger, response)
    response['request_sha256'] = 'wrong'
    with pytest.raises(ValueError, match='hash mismatch'):
        e.import_ai(ledger, response)
    assert proposal == 1


def test_ai_cannot_cite_sources_added_after_its_request(ledger):
    request = e.prepare(ledger, 'extract', 'R000001')
    source = ledger.parent / 'later.txt'
    source.write_text('New source has 120 participants.')
    assert e.add_source(ledger, 'R000001', source, 'excerpt', 'Later source') == 2
    value = item()
    value['anchors'][0]['source_id'] = 2
    proposal = e.import_ai(ledger, envelope(request, {'items': [value]}))[0]
    assert 'source_not_in_saved_request' in e.snapshot(ledger)['proposals'][0]['checks']['flags']
    with pytest.raises(ValueError, match='Unsupported'):
        approve(ledger, proposal)


def test_hypotheses_depend_on_currently_approved_evidence(ledger, tmp_path):
    with pytest.raises(ValueError, match='Approve'):
        e.prepare(ledger, 'gaps')
    extraction = submit(ledger)
    approve(ledger, extraction)
    request = e.prepare(ledger, 'gaps')
    value = {'key': 'hypothesis', 'status': 'reported', 'value': 'Larger multi-institution studies may be useful; this is a hypothesis.',
             'anchors': [], 'evidence_ids': [extraction], 'uncertainty': 'high', 'rationale': 'Limited captured evidence; independently validate.'}
    proposal = e.import_ai(ledger, envelope(request, {'items': [value]}))[0]
    approve(ledger, proposal)
    e.review(ledger, extraction, 'bob', 'reject', 'Correcting the evidence', revision=1)
    data = e.snapshot(ledger)
    assert 'missing_or_unapproved_supporting_evidence' in data['proposals'][1]['checks']['flags']
    assert not data['complete']
    export_evidence(ledger, tmp_path / 'report')
    assert 'Larger multi-institution studies' not in (tmp_path / 'report/synthesis.md').read_text()


def test_screening_scope_change_blocks_writes_but_preserves_historical_exports(ledger, tmp_path):
    proposal = submit(ledger)
    approve(ledger, proposal)
    screening = ledger.parent / 'screening.sqlite'
    s.revise_criteria(screening, 'Revised criteria', expected_version=1)
    with pytest.raises(ValueError, match='scope changed'):
        e.prepare(ledger, 'extract', 'R000001')
    data = e.snapshot(ledger)
    assert not data['scope_current'] and not data['complete']
    export_evidence(ledger, tmp_path / 'historical')
    assert 'HISTORICAL' in (tmp_path / 'historical/synthesis.md').read_text()


def test_complete_export_citations_coverage_and_screening_unchanged(ledger, tmp_path):
    screening = ledger.parent / 'screening.sqlite'
    before = screening.read_bytes()
    for key in ('sample_size', 'findings'):
        approve(ledger, submit(ledger, item(key)))
    approve(ledger, submit(ledger, item('selection', 'unclear'), task='appraise'))
    assert e.snapshot(ledger)['complete']
    output = tmp_path / 'export'
    result = export_evidence(ledger, output)
    assert result['complete'] and result['approved_items'] == 3
    manifest = json.loads((output / 'manifest.json').read_text())
    assert all(sha256((output / name).read_bytes()).hexdigest() == value for name, value in manifest['files'].items())
    draft = (output / 'synthesis.md').read_text()
    assert '[E1]' in draft and 'supplied page 1' in draft
    assert screening.read_bytes() == before
    with pytest.raises(FileExistsError):
        export_evidence(ledger, output)


def test_pending_unsupported_text_excluded_from_working_draft(ledger, tmp_path):
    submit(ledger, item(value='UNSUPPORTED INVENTED CLAIM', quote='not found'))
    export_evidence(ledger, tmp_path / 'export')
    assert 'UNSUPPORTED INVENTED CLAIM' not in (tmp_path / 'export/synthesis.md').read_text()
    assert 'UNSUPPORTED INVENTED CLAIM' in (tmp_path / 'export/evidence.json').read_text()


def test_invalid_framework_and_unknown_actor(ledger):
    invalid = deepcopy(FRAMEWORK)
    invalid['fields'].append(invalid['fields'][0])
    with pytest.raises(ValueError, match='duplicate'):
        e.validate_framework(invalid)
    with pytest.raises(ValueError, match='Actor'):
        submit(ledger, actor='unknown')


def test_api_payload_and_pending_import_boundary(ledger, tmp_path, monkeypatch):
    request = e.prepare(ledger, 'extract', 'R000001')
    monkeypatch.setenv('OPENAI_API_KEY', 'test-secret-never-log')
    response = {'id': 'resp-test', 'status': 'completed', 'model': 'test-snapshot', 'usage': {'total_tokens': 123},
                'output': [{'type': 'reasoning'}, {'type': 'message', 'content': [{'type': 'output_text', 'text': json.dumps({'items': [item()]})}]}]}
    handle = MagicMock()
    handle.__enter__.return_value.read.return_value = json.dumps(response).encode()
    with patch('slr.evidence_ai.urlopen', return_value=handle) as mock:
        result = run_openai(ledger, request['request_id'], 'user-selected-model', tmp_path / 'model')
    payload = json.loads(mock.call_args.args[0].data)
    assert payload['model'] == 'user-selected-model' and payload['store'] is False
    assert payload['tools'] == [] and payload['text']['format']['strict']
    assert result['model'] == 'test-snapshot'
    assert not e.snapshot(ledger)['proposals']
    assert all('test-secret-never-log' not in path.read_text() for path in (tmp_path / 'model').iterdir())
    e.import_ai(ledger, result)
    assert e.snapshot(ledger)['proposals'][0]['state'] == 'pending'


@pytest.mark.parametrize('response', [
    {'status': 'incomplete', 'output': []},
    {'status': 'completed', 'output': [{'type': 'message', 'content': [{'type': 'refusal', 'refusal': 'No'}]}]},
    {'status': 'completed', 'output': [{'type': 'message', 'content': [{'type': 'output_text', 'text': 'invalid json'}]}]}
])
def test_api_incomplete_refusal_and_invalid_json_fail_without_import(ledger, tmp_path, monkeypatch, response):
    request = e.prepare(ledger, 'extract', 'R000001')
    monkeypatch.setenv('OPENAI_API_KEY', 'test-secret')
    handle = MagicMock()
    handle.__enter__.return_value.read.return_value = json.dumps(response).encode()
    with patch('slr.evidence_ai.urlopen', return_value=handle):
        with pytest.raises(ModelError):
            run_openai(ledger, request['request_id'], 'model', tmp_path / 'failed')
    assert json.loads((tmp_path / 'failed/manifest.json').read_text())['status'] == 'failed'
    assert not e.snapshot(ledger)['proposals']


def test_api_missing_key_and_redacted_http_error(ledger, tmp_path, monkeypatch):
    request = e.prepare(ledger, 'extract', 'R000001')
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    with pytest.raises(ValueError, match='OPENAI_API_KEY'):
        run_openai(ledger, request['request_id'], 'model', tmp_path / 'missing')
    assert not (tmp_path / 'missing').exists()
    monkeypatch.setenv('OPENAI_API_KEY', 'secret')
    with patch('slr.evidence_ai.urlopen', side_effect=HTTPError('secret', 401, 'secret', {}, None)):
        with pytest.raises(ModelError) as error:
            run_openai(ledger, request['request_id'], 'model', tmp_path / 'failed')
    assert 'secret' not in str(error.value)


def test_cli_status_and_errors(ledger, capsys):
    assert main(['evidence', 'status', '--db', str(ledger)]) == 0
    assert json.loads(capsys.readouterr().out)['scope_current']
    with pytest.raises(SystemExit) as error:
        main(['evidence', 'review', '--db', str(ledger), '--proposal', '999', '--actor', 'bob', '--decision', 'approve', '--rationale', 'Checked', '--revision', '0', '--support-confirmed'])
    assert error.value.code == 1


def test_incomplete_screening_cannot_initialize_evidence(ledger, tmp_path):
    screening = ledger.parent / 'screening.sqlite'
    s.revise_criteria(screening, 'New criteria', expected_version=1)
    with pytest.raises(ValueError, match='Complete screening'):
        e.initialize(tmp_path / 'new.sqlite', screening, FRAMEWORK)
    assert not (tmp_path / 'new.sqlite').exists()


def test_source_quotes_and_values_are_escaped_in_html(ledger, tmp_path):
    path = tmp_path / 'markup.txt'
    path.write_text('<script>alert(1)</script>')
    source = e.add_source(ledger, 'R000001', path, 'excerpt', '<b>Source</b>')
    value = item(value='<script>alert(1)</script>', quote='<script>alert(1)</script>')
    value['anchors'][0]['source_id'] = source
    approve(ledger, submit(ledger, value))
    export_evidence(ledger, tmp_path / 'report')
    html = (tmp_path / 'report/report.html').read_text()
    assert '<script>' not in html and '&lt;script&gt;' in html
    assert 'href="source-2.txt"' in html and 'id="E1"' in html


def test_external_response_needs_model_and_timezone(ledger):
    request = e.prepare(ledger, 'extract', 'R000001')
    data = envelope(request)
    data['model'] = ''
    with pytest.raises(ValueError, match='model'):
        e.import_ai(ledger, data)
    data = envelope(request)
    data['generated_utc'] = '2026-10-22T00:00:00'
    with pytest.raises(ValueError, match='timezone-aware'):
        e.import_ai(ledger, data)
    assert not e.snapshot(ledger)['batches']


def test_api_timeout_has_no_retry_or_secret_output(ledger, tmp_path, monkeypatch):
    request = e.prepare(ledger, 'extract', 'R000001')
    monkeypatch.setenv('OPENAI_API_KEY', 'secret')
    with patch('slr.evidence_ai.urlopen', side_effect=URLError('secret')) as mock:
        with pytest.raises(ModelError) as error:
            run_openai(ledger, request['request_id'], 'model', tmp_path / 'timeout')
    assert mock.call_count == 1 and 'secret' not in str(error.value)
    assert json.loads((tmp_path / 'timeout/manifest.json').read_text())['status'] == 'failed'
