import base64
from concurrent.futures import ThreadPoolExecutor
from hashlib import sha256
from http.client import HTTPConnection
import io
import json
from pathlib import Path
import threading
import zipfile

import pytest

from slr.dashboard import DashboardServer, Workspace
from slr.dashboard_demo import create_demo
from slr import screening


@pytest.fixture
def workspace(tmp_path):
    result = Workspace(tmp_path / 'workspace')
    yield result
    result.executor.shutdown(wait=True)


def new_review(workspace):
    return workspace.create({'name': 'Browser test review', 'question': 'How can examples support learning?',
                            'criteria': 'Include empirical studies of learning.', 'reviewers': ['A', 'B'], 'adjudicator': 'C'})


def upload(workspace, entry, rows=None):
    rows = rows or [{'source': 'synthetic', 'source_id': '1', 'title': 'Synthetic learning study', 'doi': '10.9999/test', 'authors': ['Example A', 'Example B'], 'year': 2024}]
    return workspace.import_uploads(entry['id'], {'source': 'synthetic', 'files': [{'name': 'input.json', 'base64': base64.b64encode(json.dumps(rows).encode()).decode()}]})


def test_review_create_import_and_persistence(workspace):
    entry = new_review(workspace)
    assert workspace.state(entry['id'])['counts']['identified'] == 0
    upload(workspace, entry)
    state = workspace.state(entry['id'])
    assert state['counts']['records_to_screen'] == 1 and state['ledger_id']
    reopened = Workspace(workspace.root)
    assert reopened.list()['reviews'][0]['id'] == entry['id']
    assert reopened.state(entry['id'])['records'][0]['metadata']['title'] == 'Synthetic learning study'
    reopened.executor.shutdown()


def test_duplicate_doi_import_and_old_tab_guard(workspace):
    entry = new_review(workspace)
    old = workspace.state(entry['id'])['ledger_id']
    upload(workspace, entry)
    upload(workspace, entry)
    state = workspace.state(entry['id'])
    assert state['counts']['identified'] == 2 and state['counts']['duplicates_removed'] == 1
    with pytest.raises(ValueError, match='corpus changed'):
        workspace.guard_ledger(entry['id'], {'ledger_id': old})
    workspace.guard_ledger(entry['id'], {'ledger_id': state['ledger_id']})


def test_screening_uses_real_rules_and_blocks_corpus_replacement(workspace):
    entry = new_review(workspace)
    upload(workspace, entry)
    workspace.mutate_screening(entry['id'], {'action': 'decide', 'version': 1, 'actor': 'A', 'record_id': 'R000001', 'stage': 'title', 'decision': 'include'})
    db = workspace.entry(entry['id'])['screening_db']
    assert screening.snapshot(db, reviewer='A')['queue'] == []
    assert len(screening.snapshot(db, reviewer='B')['queue']) == 1
    with pytest.raises(ValueError, match='screening decisions'):
        upload(workspace, entry)
    with pytest.raises(ValueError, match='title screening'):
        workspace.mutate_screening(entry['id'], {'action': 'decide', 'version': 1, 'actor': 'A', 'record_id': 'R000001', 'stage': 'fulltext', 'decision': 'include'})


def test_invalid_files_and_identity_validation(workspace):
    with pytest.raises(ValueError, match='separate adjudicator'):
        workspace.create({'name': 'Bad', 'question': 'Q', 'criteria': 'C', 'reviewers': ['A', 'A'], 'adjudicator': 'B'})
    entry = new_review(workspace)
    with pytest.raises(ValueError, match='Supported files'):
        workspace.import_uploads(entry['id'], {'source': 'S', 'files': [{'name': '../../secret.py', 'base64': 'AA=='}]})
    assert workspace.state(entry['id'])['counts']['records_to_screen'] == 0


def test_synthetic_demo_reconciles_and_evidence_exports(workspace):
    demo = create_demo(workspace.root / 'demo', count=12, completed=True)
    entry = workspace._register(demo)
    state = workspace.state(entry['id'])
    assert state['review']['demo'] and state['counts']['complete']
    assert state['evidence']['covered'] == 18 and state['evidence']['pending'] == 6 and state['evidence']['flagged'] == 1
    archive = zipfile.ZipFile(io.BytesIO(workspace.export(entry['id'])))
    assert 'screening/prisma.svg' in archive.namelist() and 'evidence/evidence.csv' in archive.namelist()
    assert json.loads(archive.read('evidence/manifest.json'))['status'] == 'complete'


@pytest.fixture
def server(workspace):
    result = DashboardServer(('127.0.0.1', 0), workspace)
    thread = threading.Thread(target=result.serve_forever, daemon=True)
    thread.start()
    yield result
    result.shutdown()
    result.server_close()
    thread.join(timeout=3)


def request(server, path, body=None, token=True, extra=None):
    conn = HTTPConnection('127.0.0.1', server.server_port, timeout=20)
    headers = {'X-SLR-Token': server.token} if token else {}
    if body is not None:
        headers['Content-Type'] = 'application/json'
    headers.update(extra or {})
    conn.request('POST' if body is not None else 'GET', path, json.dumps(body) if body is not None else None, headers)
    response = conn.getresponse()
    payload, status, result_headers = response.read(), response.status, dict(response.getheaders())
    conn.close()
    return status, payload, result_headers


def test_server_static_assets_session_token_and_csp(server):
    status, page, headers = request(server, '/', token=False)
    assert status == 200 and b'__SLR_TOKEN__' not in page
    assert server.token.encode() in page
    assert "script-src 'self'" in headers['Content-Security-Policy']
    assert headers['Cache-Control'] == 'no-store'
    assert request(server, '/app.js', token=False)[0] == 200
    assert request(server, '/api/workspace', token=False)[0] == 403
    assert request(server, '/api/workspace')[0] == 200
    assert request(server, '/../../pyproject.toml', token=False)[0] != 200


def test_server_rejects_cross_origin_and_host_rebinding(server):
    assert request(server, '/api/workspace', extra={'Origin': 'https://example.com'})[0] == 403
    assert request(server, '/', token=False, extra={'Host': 'example.com'})[0] == 403


def test_http_create_import_decision_and_export(server):
    status, raw, _ = request(server, '/api/create', {'name': 'HTTP review', 'question': 'Q', 'criteria': 'C', 'reviewers': ['A', 'B'], 'adjudicator': 'C'})
    assert status == 200
    entry = json.loads(raw)
    upload(server.workspace, entry)
    state = server.workspace.state(entry['id'])
    body = {'review_id': entry['id'], 'ledger_id': state['ledger_id'], 'action': 'decide', 'version': 1,
            'record_id': 'R000001', 'actor': 'A', 'stage': 'title', 'decision': 'exclude', 'reason': 'Wrong design'}
    assert request(server, '/api/screening', body)[0] == 200
    assert request(server, '/api/screening', {**body, 'ledger_id': 'stale'})[0] == 400
    assert request(server, '/api/export?review='+entry['id'])[0] == 200


def test_invalid_import_does_not_replace_the_current_corpus(workspace):
    entry = new_review(workspace)
    original = workspace.state(entry['id'])['ledger_id']
    with pytest.raises(ValueError, match='Publication years'):
        upload(workspace, entry, [{'source': 'test', 'source_id': '1', 'title': 'Invalid year', 'year': 'yesterday'}])
    assert workspace.state(entry['id'])['ledger_id'] == original


def test_running_retrieval_blocks_import_and_finishes_atomically(workspace, monkeypatch):
    entry = new_review(workspace)
    started, release = threading.Event(), threading.Event()
    def fake_search(config, output):
        from slr.cli import run
        started.set()
        assert release.wait(10)
        return run(config, output, 'Examples/demo_records.json')
    monkeypatch.setattr('slr.dashboard.run_search', fake_search)
    job = workspace.search(entry['id'], {'query': 'synthetic', 'sources': ['crossref'], 'limit': 10})
    assert started.wait(5)
    try:
        with pytest.raises(ValueError, match='already running'):
            upload(workspace, entry)
    finally:
        release.set()
    workspace.executor.shutdown(wait=True)
    assert workspace.jobs[job['id']]['status'] == 'complete'
    assert workspace.state(entry['id'])['counts']['records_to_screen'] == 2


def test_failed_retrieval_preserves_the_old_ledger(workspace, monkeypatch):
    entry = new_review(workspace)
    original = workspace.state(entry['id'])['ledger_id']
    def fail(*args):
        raise ValueError('Synthetic retrieval failure')
    monkeypatch.setattr('slr.dashboard.run_search', fail)
    job = workspace.search(entry['id'], {'query': 'synthetic', 'sources': ['crossref'], 'limit': 10})
    workspace.executor.shutdown(wait=True)
    assert workspace.jobs[job['id']]['status'] == 'failed'
    assert workspace.state(entry['id'])['ledger_id'] == original
