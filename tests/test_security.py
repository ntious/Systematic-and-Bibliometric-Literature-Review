"""Regression tests for findings in reviewer_feedback.md (HIGH-1, MEDIUM-1 to MEDIUM-3)."""
import csv
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
from pathlib import Path
import threading
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request

import pytest

from slr import evidence as e
from slr import evidence_ai, search
from slr.bibliometrics_cli import analyze
from slr.cli import run
from slr.evidence_cli import export_evidence
from slr.imports import import_files
from slr.models import Record
from slr.reporting import export_records, safe_cell, unsafe_cell, write_csv
from slr.review_cli import export_review
from slr.screening import initialize
from test_evidence import item, ledger, submit  # noqa: F401  (pytest fixture reuse)

FORMULAS = ['=HYPERLINK("http://evil","x")', '+1+1', '-2+3', '@SUM(A1)', '\t=1', '\r=1']


def cells(path):
    with Path(path).open(encoding='utf-8', newline='') as handle:
        return [value for row in csv.reader(handle) for value in row]


# HIGH-1: CSV formula injection

@pytest.mark.parametrize('value', FORMULAS)
def test_formula_cells_are_quoted_and_reversible(value):
    assert safe_cell(value) == "'" + value
    assert unsafe_cell(safe_cell(value)) == value


@pytest.mark.parametrize('value', ['Plain title', "'quoted but harmless", '', None, 42, "O'Brien"])
def test_harmless_cells_unchanged(value):
    assert safe_cell(value) == value
    assert unsafe_cell(value) == value


def test_existing_quote_prefix_survives_roundtrip():
    value = "'=already quoted"
    assert safe_cell(value) == "''=already quoted"
    assert unsafe_cell(safe_cell(value)) == value


def test_write_csv_neutralizes_every_column(tmp_path):
    write_csv(tmp_path / 'out.csv', ['a', 'b'], [{'a': '=1+1', 'b': '@cmd'}])
    assert cells(tmp_path / 'out.csv') == ['a', 'b', "'=1+1", "'@cmd"]


def test_records_csv_is_safe_and_reimports_exactly(tmp_path):
    records = [Record('test', str(i), title=title, journal='-Journal') for i, title in enumerate(FORMULAS[:4], 1)]
    export_records(tmp_path, records)
    exported = cells(tmp_path / 'records.csv')
    assert not any(value.startswith(('=', '+', '-', '@')) for value in exported)
    assert [r['title'] for r in json.loads((tmp_path / 'records.json').read_text(encoding='utf-8'))] == FORMULAS[:4]
    folder = import_files([tmp_path / 'records.csv'], tmp_path / 'roundtrip', 'roundtrip')
    rows = json.loads((folder / 'records.json').read_text(encoding='utf-8'))
    assert [r['title'] for r in rows] == FORMULAS[:4]
    assert {r['journal'] for r in rows} == {'-Journal'}


def test_screening_csv_is_safe(tmp_path):
    fixture = tmp_path / 'records.json'
    fixture.write_text(json.dumps([Record('test', '1', title='=cmd|"/c calc"!A1').to_dict()]), encoding='utf-8')
    run('configs/example_review.toml', tmp_path / 'run', fixture)
    db = tmp_path / 'review.sqlite'
    initialize(db, tmp_path / 'run', 'Review', ['alice', 'bob'], 'carol', 'Criteria')
    export_review(db, tmp_path / 'report')
    assert '\'=cmd|"/c calc"!A1' in cells(tmp_path / 'report/screening.csv')


def test_evidence_csv_is_safe(ledger, tmp_path):  # noqa: F811
    proposal = submit(ledger, item(value='=SUM(1,1)'))
    e.review(ledger, proposal, 'bob', 'approve', '+Checked source.', support_confirmed=True)
    export_evidence(ledger, tmp_path / 'export')
    values = cells(tmp_path / 'export/evidence.csv')
    assert "'=SUM(1,1)" in values and "'+Checked source." in values


def test_bibliometric_csvs_are_safe(tmp_path):
    rows = [Record('test', str(i), title=f'@Study {i}', keywords=['=evil()', 'safe'], authors=['-Ann', 'Bob']).to_dict() for i in (1, 2)]
    source = tmp_path / 'input.json'
    source.write_text(json.dumps(rows), encoding='utf-8')
    output = analyze(tmp_path / 'analysis', input_path=source)
    for path in output.glob('*.csv'):
        assert not any(value.startswith(('=', '+', '-', '@')) for value in cells(path)), path.name
    assert "'=evil()" in cells(output / 'keywords-nodes.csv')


# MEDIUM-1: credentials must not follow redirects

class _Capture(BaseHTTPRequestHandler):
    seen = []

    def do_GET(self):
        _Capture.seen.append(self.headers.get('Authorization'))
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'{}')

    def log_message(self, *args):
        pass


def _serve(handler):
    server = HTTPServer(('127.0.0.1', 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def test_authorization_is_not_forwarded_on_redirect():
    _Capture.seen = []
    target = _serve(_Capture)

    class Redirect(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(302)
            self.send_header('Location', f'http://127.0.0.1:{target.server_port}/stolen')
            self.end_headers()

        def log_message(self, *args):
            pass

    origin = _serve(Redirect)
    try:
        request = Request(f'http://127.0.0.1:{origin.server_port}/', headers={'Authorization': 'Bearer secret'})
        with pytest.raises(HTTPError) as error:
            search._OPENER.open(request, timeout=5)  # bypass the HTTPS check to exercise the redirect handler
        assert error.value.code == 302
        assert _Capture.seen == []
    finally:
        origin.shutdown()
        target.shutdown()


def test_non_https_urls_are_refused_before_any_connection():
    with patch.object(search._OPENER, 'open') as opened:
        with pytest.raises(search.SearchError, match='HTTPS'):
            search.urlopen(Request('http://api.openalex.org/works'), timeout=5)
    opened.assert_not_called()


def test_redirect_is_reported_without_retry():
    redirect = HTTPError('https://example.org', 302, 'Found', {'Location': 'http://evil'}, None)
    with patch('slr.search.urlopen', side_effect=redirect) as opened:
        with pytest.raises(search.SearchError, match='HTTP 302'):
            search.HTTPClient(interval=0).get('https://example.org', {})
    assert opened.call_count == 1


def test_openai_adapter_uses_hardened_opener():
    assert evidence_ai.urlopen is search.urlopen


# MEDIUM-2: independent evidence review

def test_author_cannot_approve_own_manual_proposal(ledger):  # noqa: F811
    proposal = submit(ledger, actor='alice')
    with pytest.raises(ValueError, match='different actor'):
        e.review(ledger, proposal, 'alice', 'approve', 'Self check.', support_confirmed=True)
    assert e.snapshot(ledger)['proposals'][0]['state'] == 'pending'
    assert e.review(ledger, proposal, 'bob', 'approve', 'Independent check.', support_confirmed=True) == 1


def test_author_may_withdraw_own_proposal_by_rejecting(ledger):  # noqa: F811
    proposal = submit(ledger, actor='alice')
    assert e.review(ledger, proposal, 'alice', 'reject', 'Withdrawn by author.') == 1


def test_ai_proposals_can_be_approved_by_any_assigned_reviewer(ledger):  # noqa: F811
    request = e.prepare(ledger, 'extract', 'R000001')
    proposal = e.import_ai(ledger, {'request_id': request['request_id'], 'request_sha256': request['request_sha256'],
                                    'provider': 'test', 'model': 'm', 'generated_utc': '2026-10-22T00:00:00Z',
                                    'response_id': 'r', 'usage': None, 'output': {'items': [item()]}})[0]
    assert e.review(ledger, proposal, 'alice', 'approve', 'Checked.', support_confirmed=True) == 1


# MEDIUM-3: contact email stays out of shareable artifacts

EMAIL = 'researcher@example.org'


def _config(tmp_path):
    path = tmp_path / 'review.toml'
    path.write_text(f'query = "x"\nsources = ["crossref"]\nmailto = "{EMAIL}"\n', encoding='utf-8')
    return path


def test_mailto_redacted_from_completed_run(tmp_path):
    with patch('slr.cli.search', return_value=([], [{}], {'source': 'crossref'})) as searched:
        folder = run(_config(tmp_path), tmp_path / 'out')
    assert searched.call_args.args[5] == EMAIL  # the real address still reaches the provider
    assert json.loads((folder / 'manifest.json').read_text())['config']['mailto'] == '<redacted>'
    assert all(EMAIL not in path.read_text(encoding='utf-8') for path in folder.iterdir())


def test_mailto_redacted_from_failed_run(tmp_path):
    with patch('slr.cli.search', side_effect=search.SearchError('down')):
        with pytest.raises(search.SearchError):
            run(_config(tmp_path), tmp_path / 'out')
    assert EMAIL not in (tmp_path / 'out/manifest.json').read_text()


def test_config_without_mailto_unchanged(tmp_path):
    folder = run('configs/example_review.toml', tmp_path / 'out', 'Examples/demo_records.json')
    assert 'mailto' not in json.loads((folder / 'manifest.json').read_text())['config']
