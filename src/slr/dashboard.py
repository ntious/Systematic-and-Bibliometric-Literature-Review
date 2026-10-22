"""Loopback-only dashboard server using the same workflow services as the CLI."""
import argparse
import base64
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from hashlib import sha256
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import json
from pathlib import Path
import secrets
import sqlite3
import tempfile
from threading import RLock
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4
import zipfile

from . import __version__, screening, evidence
from .bibliometrics import descriptive_summary, networks
from .cli import run as run_search
from .dashboard_demo import FRAMEWORK, create_demo
from .evidence_cli import export_evidence
from .imports import import_files
from .models import Record
from .reporting import write_results, write_json
from .review_cli import export_review

WEB = Path(__file__).with_name('web')
MAX_BODY = 8 * 1024 * 1024


def timestamp():
    return datetime.now(timezone.utc).isoformat()


class Workspace:
    def __init__(self, root, *, demo=False):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.registry = self.root / 'workspace.json'
        self.lock = RLock()
        self.executor = ThreadPoolExecutor(max_workers=2)
        self.jobs_path = self.root / 'jobs.json'
        self.jobs = json.loads(self.jobs_path.read_text()) if self.jobs_path.exists() else {}
        for job in self.jobs.values():
            if job['status'] == 'running':
                job.update(status='failed', error='Server restarted before completion; job was not resumed', finished_utc=timestamp())
                if job.get('session_report'):
                    from .pipeline import SessionJournal
                    journal = SessionJournal.reopen(Path(job['session_report']).parent)
                    journal.data['status'] = 'interrupted'
                    journal.record('process restart', 'error', job['error'], remedy='Inspect saved artifacts and start a new session; this job was not resumed.')
        self._save_jobs()
        self.entries = json.loads(self.registry.read_text(encoding='utf-8')) if self.registry.exists() else []
        if demo and not self.entries:
            self._register(create_demo(self.root / 'demo-review'))
            self._register(create_demo(self.root / 'demo-evidence', count=12, completed=True))

    def _save_jobs(self):
        temp = self.jobs_path.with_suffix('.tmp')
        temp.write_text(json.dumps(self.jobs, ensure_ascii=False, indent=2), encoding='utf-8')
        temp.replace(self.jobs_path)

    def _save(self):
        temporary = self.registry.with_suffix('.tmp')
        temporary.write_text(json.dumps(self.entries, ensure_ascii=False, indent=2), encoding='utf-8')
        temporary.replace(self.registry)

    def _register(self, entry):
        with self.lock:
            entry = {**entry, 'id': uuid4().hex, 'created_utc': timestamp()}
            self.entries.append(entry)
            self._save()
            return entry

    def entry(self, identifier):
        with self.lock:
            item = next((r for r in self.entries if r['id'] == identifier), None)
            if item is None:
                raise ValueError('Review not found')
            return dict(item)

    def update(self, identifier, **values):
        with self.lock:
            row = next((r for r in self.entries if r['id'] == identifier), None)
            if row is None:
                raise ValueError('Review not found')
            row.update(values)
            self._save()

    def attach(self, screening_db, evidence_db=None):
        path = Path(screening_db).resolve()
        state = screening.snapshot(path)
        if evidence_db:
            result = evidence.snapshot(Path(evidence_db).resolve())
            if result['scope']['snapshot']['review_id'] != state['review_id']:
                raise ValueError('Evidence ledger belongs to a different review')
        existing = next((r for r in self.entries if r['screening_db'] == str(path)), None)
        if existing:
            if evidence_db:
                self.update(existing['id'], evidence_db=str(Path(evidence_db).resolve()))
            return self.entry(existing['id'])
        return self._register({'name': state['name'], 'question': 'Connected local review', 'screening_db': str(path),
                               'run': None, 'evidence_db': str(Path(evidence_db).resolve()) if evidence_db else None, 'demo': False})

    def create(self, body):
        name = evidence.text(body.get('name'), 'Review name')
        question = evidence.text(body.get('question'), 'Research question')
        criteria = evidence.text(body.get('criteria'), 'Screening criteria')
        reviewers = body.get('reviewers')
        adjudicator = body.get('adjudicator')
        if not isinstance(reviewers, list) or len(reviewers) != 2 or any(not isinstance(r, str) or not r.strip() for r in reviewers) or not isinstance(adjudicator, str) or not adjudicator.strip() or len(set([r.strip() for r in reviewers] + [adjudicator.strip()])) != 3:
            raise ValueError('Provide two reviewer names and a separate adjudicator')
        folder = self.root / ('review-' + uuid4().hex)
        run = folder / 'retrieval'
        run.mkdir(parents=True)
        write_results(run, [])
        write_json(run / 'manifest.json', {'status': 'complete', 'mode': 'empty-review', 'config': {}, 'searches': [], 'version': __version__,
                   'files': {p.name: sha256(p.read_bytes()).hexdigest() for p in sorted(run.iterdir())}})
        db = folder / 'screening.sqlite'
        screening.initialize(db, run, name, reviewers, adjudicator, criteria)
        return self._register({'name': name, 'question': question, 'run': str(run), 'screening_db': str(db), 'evidence_db': None, 'demo': False})

    def list(self):
        with self.lock:
            entries = list(self.entries)
        result = []
        for entry in entries:
            try:
                state = screening.snapshot(entry['screening_db'])
                result.append({k: entry[k] for k in ('id', 'name', 'question', 'demo', 'created_utc')} | {'counts': state['prisma']})
            except (ValueError, OSError, sqlite3.DatabaseError):
                result.append({k: entry[k] for k in ('id', 'name', 'question', 'demo', 'created_utc')} | {'unavailable': True})
        return {'reviews': result, 'version': __version__}

    def state(self, identifier):
        entry = self.entry(identifier)
        state = screening.snapshot(entry['screening_db'])
        with sqlite3.connect(Path(entry['screening_db']).resolve().as_uri() + '?mode=ro', uri=True) as conn:
            reviewers, adjudicator = conn.execute('SELECT reviewers,adjudicator FROM review').fetchone()
        records = [Record(**r['metadata']) for r in state['records']]
        evidence_summary = None
        if entry.get('evidence_db'):
            data = evidence.snapshot(entry['evidence_db'])
            evidence_summary = {k: data[k] for k in ('complete', 'scope_current', 'pending', 'flagged')}
            evidence_summary.update(approved=sum(p['state'] == 'approve' and not p['checks']['flags'] for p in data['proposals']),
                                    covered=sum(r['proposal_id'] is not None for r in data['coverage']), total=len(data['coverage']))
        events = [{'id': r['sequence'], 'actor': r['actor'], 'record_id': r['record_id'], 'kind': r['kind'],
                   'stage': r['stage'], 'value': r['value'], 'created_utc': r['created_utc']} for r in state['events'][-8:]]
        return {'ledger_id': state['review_id'], 'review': {k: entry[k] for k in ('id', 'name', 'question', 'demo', 'created_utc')},
                'records': state['records'], 'counts': state['prisma'], 'criteria': state['criteria'],
                'reviewers': json.loads(reviewers), 'adjudicator': adjudicator, 'summary': descriptive_summary(records),
                'evidence': evidence_summary, 'activity': list(reversed(events)),
                'jobs': [dict(job) for job in self.jobs.values() if job.get('review_id') == identifier],
                'coverage': {field: sum(bool(getattr(r, field)) for r in records) for field in ('authors', 'keywords', 'references')},
                'retrieval': {'mode': state['origin'].get('mode'), 'searches': state['origin'].get('searches', []),
                              'truncated': any(s.get('truncated', False) for s in state['origin'].get('searches', []))}}

    def mutable_corpus(self, identifier):
        entry = self.entry(identifier)
        if any(j.get('review_id') == identifier and j['status'] == 'running' for j in self.jobs.values()):
            raise ValueError('A retrieval job is already running for this review')
        state = screening.snapshot(entry['screening_db'])
        if not entry.get('run') and state['records']:
            raise ValueError('This connected review has no original retrieval folder. Create a new review and import its retrieved metadata together with the additional files.')
        if state['events'] or entry.get('evidence_db'):
            raise ValueError('This corpus has screening decisions. Create a new review to import or retrieve additional records.')
        return entry, state

    def guard_ledger(self, identifier, body):
        entry = self.entry(identifier)
        if body.get('ledger_id') != screening.snapshot(entry['screening_db'])['review_id']:
            raise ValueError('The captured corpus changed. Reload this review before making another decision.')

    def import_uploads(self, identifier, body):
        with self.lock:
            entry, state = self.mutable_corpus(identifier)
            source = evidence.text(body.get('source'), 'Source label')
            uploads = body.get('files')
            if not isinstance(uploads, list) or not 1 <= len(uploads) <= 10:
                raise ValueError('Upload 1–10 CSV, RIS or normalized JSON files')
            folder = self.root / ('import-' + uuid4().hex)
            folder.mkdir()
            paths = []
            for i, item in enumerate(uploads):
                suffix = Path(item['name']).suffix.lower()
                if suffix not in ('.csv', '.ris', '.json'):
                    raise ValueError('Supported files: CSV, RIS or normalized JSON')
                path = folder / f'upload-{i}{suffix}'
                path.write_bytes(base64.b64decode(item['base64'], validate=True))
                paths.append(path)
            if entry.get('run'):
                paths.insert(0, Path(entry['run']) / 'retrieved.json')
                if not json.loads(paths[0].read_text()):
                    paths.pop(0)
            run = import_files(paths, folder / 'retrieval', source)
            return self._replace_corpus(entry, state, run, folder)

    def _replace_corpus(self, entry, state, run, folder):
        rows, _, _ = screening.verify_run(run)
        descriptive_summary([Record(**row) for row in rows])
        old = Path(entry['screening_db'])
        with sqlite3.connect(old.resolve().as_uri() + '?mode=ro', uri=True) as conn:
            reviewers, adjudicator = conn.execute('SELECT reviewers,adjudicator FROM review').fetchone()
        db = folder / 'screening.sqlite'
        screening.initialize(db, run, entry['name'], json.loads(reviewers), adjudicator, state['criteria']['text'])
        self.update(entry['id'], run=str(run), screening_db=str(db))
        return {'review_id': entry['id'], 'records': len(screening.snapshot(db)['records'])}

    def search(self, identifier, body):
        with self.lock:
            entry, state = self.mutable_corpus(identifier)
            if state['records']:
                raise ValueError('Search requires an empty review; import combined retrieval JSON files to combine searches.')
            config = {'query': body.get('query'), 'sources': body.get('sources'), 'max_records_per_source': body.get('limit', 100)}
            for key in ('year_from', 'year_to', 'date_from', 'date_to'):
                if body.get(key) is not None:
                    config[key] = body[key]
            from .cli import load_config
            from .pipeline import run_plan, validate_plan
            plan = None
            if 'queries' in body:
                plan = validate_plan({**{k: v for k, v in config.items() if k != 'query'}, 'queries': body['queries'], **({'relevance_policy':body['relevance_policy']} if body.get('relevance_policy') is not None else {})})
            folder = self.root / ('search-' + uuid4().hex)
            folder.mkdir()
            config_path = folder / 'review.toml'
            config_path.write_text('\n'.join(k + ' = ' + json.dumps(v) for k, v in config.items()), encoding='utf-8')
            load_config(config_path)
            job_id = uuid4().hex
            self.jobs[job_id] = {'id': job_id, 'review_id': identifier, 'status': 'running', 'started_utc': timestamp()}
            self._save_jobs()
            def execute():
                try:
                    if plan is not None:
                        def progress(event):
                            with self.lock:
                                self.jobs[job_id].update(event)
                                self._save_jobs()
                        run = run_plan(plan, folder / 'pipeline', progress=progress)
                    else:
                        run = run_search(config_path, folder / 'retrieval')
                    with self.lock:
                        self._replace_corpus(entry, state, run, folder)
                        self.jobs[job_id].update(status='complete', finished_utc=timestamp())
                        if plan is not None:
                            report = json.loads((folder / 'pipeline' / 'session.json').read_text())
                            self.jobs[job_id]['outcome'] = report['status']
                            self.jobs[job_id]['calibration_available'] = (folder / 'pipeline' / 'calibration' / 'manifest.json').exists()
                        self._save_jobs()
                except Exception as exc:
                    with self.lock:
                        self.jobs[job_id].update(status='failed', error=str(exc) if isinstance(exc, (ValueError, OSError, RuntimeError)) else 'Retrieval failed', finished_utc=timestamp())
                        if plan is not None and (folder / 'pipeline' / 'session.json').exists():
                            from .pipeline import SessionJournal
                            journal = SessionJournal.reopen(folder / 'pipeline')
                            journal.data['status'] = 'failed'
                            journal.record('dashboard job', 'error', str(exc), remedy='Inspect pipeline and corpus registration artifacts. The selected corpus changes only after verification succeeds.')
                        self._save_jobs()
            self.executor.submit(execute)
            return dict(self.jobs[job_id])

    def mutate_screening(self, identifier, body):
        with self.lock:
            entry = self.entry(identifier)
            if any(j.get('review_id') == identifier and j['status'] == 'running' for j in self.jobs.values()):
                raise ValueError('Wait for retrieval to finish before screening')
            db = entry['screening_db']
            version, action = body['version'], body['action']
            if type(version) is not int:
                raise ValueError('Criteria version must be an integer')
            if action in ('decide', 'adjudicate'):
                screening.decide(db, body['record_id'], body['actor'], body['stage'], body['decision'], body.get('reason', ''),
                                  adjudicate=action == 'adjudicate', expected_version=version)
            elif action == 'retrieve':
                screening.record_retrieval(db, body['record_id'], body['actor'], body['status'], body.get('reason', ''), expected_version=version)
            elif action == 'link':
                screening.link_study(db, body['record_id'], body['actor'], body['study_id'], expected_version=version)
            elif action == 'criteria':
                screening.revise_criteria(db, body['text'], expected_version=version)
            else:
                raise ValueError('Unknown screening action')
            return {'saved': True}

    def evidence_action(self, identifier, body):
        with self.lock:
            entry = self.entry(identifier)
            action = body['action']
            if action == 'init':
                if entry.get('evidence_db'):
                    raise ValueError('Evidence ledger already exists')
                db = self.root / ('evidence-' + uuid4().hex + '.sqlite')
                framework = body.get('framework') or json.loads((WEB / 'framework.json').read_text(encoding='utf-8'))
                evidence.initialize(db, entry['screening_db'], framework)
                self.update(identifier, evidence_db=str(db))
                return {'saved': True}
            db = entry.get('evidence_db')
            if not db:
                raise ValueError('Start an evidence ledger after screening is complete')
            if action == 'source':
                evidence.text(body['text'], 'Source text')
                value = body['text']
                with tempfile.TemporaryDirectory(dir=self.root) as directory:
                    source = Path(directory) / 'source.txt'
                    source.write_text(value, encoding='utf-8')
                    result = evidence.add_source(db, body['record_id'], source, body['kind'], body['label'])
                return {'source_id': result}
            if action == 'propose':
                return {'proposal_ids': evidence.submit(db, body['task'], body.get('record_id'), body['output'], {'method': 'manual', 'actor': body['actor']})}
            if action == 'review':
                return {'revision': evidence.review(db, body['proposal_id'], body['actor'], body['decision'], body['rationale'],
                         revision=body['revision'], support_confirmed=body.get('support_confirmed', False))}
            if action == 'prepare':
                return evidence.prepare(db, body['task'], body.get('record_id'))
            if action == 'import':
                return {'proposal_ids': evidence.import_ai(db, body['envelope'])}
            raise ValueError('Unknown evidence action')

    def export(self, identifier):
        entry = self.entry(identifier)
        folder = self.root / ('export-' + uuid4().hex)
        export_review(entry['screening_db'], folder / 'screening')
        if entry.get('evidence_db'):
            export_evidence(entry['evidence_db'], folder / 'evidence')
        result = io.BytesIO()
        with zipfile.ZipFile(result, 'w', zipfile.ZIP_DEFLATED) as archive:
            for path in folder.rglob('*'):
                if path.is_file():
                    archive.write(path, str(path.relative_to(folder)))
        return result.getvalue()


class DashboardServer(ThreadingHTTPServer):
    daemon_threads = True
    def __init__(self, address, workspace):
        self.workspace = workspace
        self.token = secrets.token_urlsafe(32)
        super().__init__(address, Handler)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def send(self, status, value, mime='application/json; charset=utf-8', *, download=None):
        data = json.dumps(value, ensure_ascii=False).encode() if mime.startswith('application/json') else value
        self.send_response(status)
        self.send_header('Content-Type', mime)
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; connect-src 'self'; font-src 'self'; object-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
        self.send_header('Referrer-Policy', 'no-referrer')
        if download:
            self.send_header('Content-Disposition', 'attachment; filename="' + download + '"')
        self.end_headers()
        self.wfile.write(data)

    def _check(self, api=False):
        port = self.server.server_port
        allowed = {f'127.0.0.1:{port}', f'localhost:{port}'}
        if self.headers.get('Host') not in allowed:
            raise PermissionError('Dashboard accepts local requests only')
        origin = self.headers.get('Origin')
        if origin and origin not in {'http://' + host for host in allowed}:
            raise PermissionError('Cross-origin requests are not allowed')
        if api and not secrets.compare_digest(self.headers.get('X-SLR-Token', ''), self.server.token):
            raise PermissionError('Dashboard session expired. Reload the page.')

    def do_GET(self):
        try:
            parsed = urlsplit(self.path)
            path, query = parsed.path, parse_qs(parsed.query)
            self._check(path.startswith('/api/'))
            if path in ('/', '/index.html'):
                value = (WEB / 'index.html').read_text(encoding='utf-8').replace('__SLR_TOKEN__', self.server.token)
                return self.send(200, value.encode(), 'text/html; charset=utf-8')
            if path in ('/app.js', '/styles.css'):
                return self.send(200, (WEB / path[1:]).read_bytes(), 'text/javascript; charset=utf-8' if path.endswith('.js') else 'text/css; charset=utf-8')
            if path == '/api/workspace':
                return self.send(200, self.server.workspace.list())
            if path == '/api/job-calibration':
                job = self.server.workspace.jobs.get(query.get('id', [''])[0])
                if not job or not job.get('calibration_available'):
                    raise ValueError('Calibration sample not available')
                folder = Path(job['session_report']).parent / 'calibration'
                return self.send(200, {'csv': (folder / 'human-review.csv').read_text(encoding='utf-8'), 'report': json.loads((folder / 'report.json').read_text())})
            if path == '/api/job-report':
                job = self.server.workspace.jobs.get(query.get('id', [''])[0])
                if not job or not job.get('session_report'):
                    raise ValueError('Session report not available')
                return self.send(200, {'markdown': Path(job['session_report']).read_text(encoding='utf-8')})
            if path == '/api/job':
                job = self.server.workspace.jobs.get(query.get('id', [''])[0])
                if not job:
                    raise ValueError('Job not found')
                return self.send(200, job)
            identifier = query.get('review', [''])[0]
            entry = self.server.workspace.entry(identifier)
            if path == '/api/state':
                return self.send(200, self.server.workspace.state(identifier))
            if path == '/api/queue':
                return self.send(200, screening.snapshot(entry['screening_db'], reviewer=query.get('actor', [''])[0]))
            if path == '/api/networks':
                state = screening.snapshot(entry['screening_db'])
                rows = state['records']
                if query.get('scope', ['all'])[0] == 'included':
                    rows = [r for r in rows if r['fulltext'] == 'include']
                records = [Record(**r['metadata']) for r in rows]
                graphs, coverage = networks(records, min_occurrences=int(query.get('minimum', ['1'])[0]),
                     min_edge_count=int(query.get('edges', ['1'])[0]), normalization=query.get('normalization', ['cosine'])[0])
                return self.send(200, {'graphs': graphs, 'coverage': coverage, 'scope': 'included' if query.get('scope', ['all'])[0] == 'included' else 'all'})
            if path == '/api/evidence':
                return self.send(200, evidence.snapshot(entry['evidence_db']) if entry.get('evidence_db') else None)
            if path == '/api/export':
                return self.send(200, self.server.workspace.export(identifier), 'application/zip', download='review-export.zip')
            self.send(404, {'error': 'Not found'})
        except Exception as exc:
            self.error(exc)

    def do_POST(self):
        try:
            self._check(True)
            if self.headers.get('Content-Type', '').split(';')[0] != 'application/json':
                raise ValueError('Send JSON requests')
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 < length <= MAX_BODY:
                raise ValueError('Request is empty or exceeds the 8 MB limit')
            body = json.loads(self.rfile.read(length))
            if not isinstance(body, dict):
                raise ValueError('Request must be a JSON object')
            workspace = self.server.workspace
            path = urlsplit(self.path).path
            if path == '/api/create':
                return self.send(200, workspace.create(body))
            identifier = body.get('review_id')
            if path in ('/api/import', '/api/search', '/api/screening', '/api/evidence'):
                workspace.guard_ledger(identifier, body)
            if path == '/api/import':
                return self.send(200, workspace.import_uploads(identifier, body))
            if path == '/api/search':
                return self.send(200, workspace.search(identifier, body))
            if path == '/api/screening':
                return self.send(200, workspace.mutate_screening(identifier, body))
            if path == '/api/evidence':
                return self.send(200, workspace.evidence_action(identifier, body))
            self.send(404, {'error': 'Not found'})
        except Exception as exc:
            self.error(exc)

    def error(self, exc):
        if isinstance(exc, PermissionError):
            self.send(403, {'error': str(exc)})
        elif isinstance(exc, (ValueError, TypeError, KeyError, sqlite3.IntegrityError)):
            self.send(400, {'error': str(exc) if not isinstance(exc, KeyError) else 'Missing request field'})
        elif isinstance(exc, (BrokenPipeError, ConnectionResetError)):
            pass
        else:
            self.send(500, {'error': 'The operation could not be completed. Check the selected local review and try again.'})


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace', default='outputs/dashboard')
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--demo', action='store_true', help='Seed an empty workspace with explicitly synthetic examples')
    parser.add_argument('--review-db', help='Connect an existing local screening database')
    parser.add_argument('--evidence-db', help='Evidence ledger matching --review-db')
    args = parser.parse_args(argv)
    if args.evidence_db and not args.review_db:
        parser.error('--evidence-db requires --review-db')
    workspace = Workspace(args.workspace, demo=args.demo)
    if args.review_db:
        workspace.attach(args.review_db, args.evidence_db)
    try:
        server = DashboardServer(('127.0.0.1', args.port), workspace)
        print(f'LitAtlas dashboard: http://127.0.0.1:{server.server_port}', flush=True)
        print('Local workspace ready. Press Ctrl+C to stop.', flush=True)
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        if 'server' in locals():
            server.server_close()
        workspace.executor.shutdown(wait=False, cancel_futures=True)
    return 0
