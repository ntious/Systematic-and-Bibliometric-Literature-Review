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

from . import __version__, screening, evidence, questions, review_plan
from .bibliometrics import descriptive_summary, networks
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
        from .ai_setup import AISettings
        self.ai = AISettings(self.root, self.executor)
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
            criteria_managed_by_protocol = screening._guided_protocol(conn)
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
                'criteria_managed_by_protocol': criteria_managed_by_protocol, 'screening_access': state['screening_access'], 'records': state['records'], 'counts': state['prisma'], 'criteria': state['criteria'],
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
        if entry.get('run'):
            _,_,origin=screening.verify_run(entry['run'])
            if origin!=state['origin']:
                raise ValueError('This review was updated outside the workspace. Reconnect it or create a new review with combined metadata before changing its corpus.')
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
        rows, _, manifest = screening.verify_run(run)
        if manifest.get('mode','').startswith(('live','approved')):
            authorization=manifest.get('authorization')
            if not authorization or authorization.get('kind')!='main':
                raise ValueError('Only an approved main search may replace a review corpus')
            review_plan.check_authorization(entry['screening_db'],authorization)
        descriptive_summary([Record(**row) for row in rows])
        old = Path(entry['screening_db'])
        with sqlite3.connect(old.resolve().as_uri() + '?mode=ro', uri=True) as conn:
            reviewers, adjudicator = conn.execute('SELECT reviewers,adjudicator FROM review').fetchone()
            initial_criteria = conn.execute('SELECT text FROM criteria ORDER BY version LIMIT 1').fetchone()[0]
        db = folder / 'screening.sqlite'
        screening.initialize(db, run, entry['name'], json.loads(reviewers), adjudicator, initial_criteria)
        questions.copy_history(old, db)
        review_plan.copy_history(old, db)
        self.update(entry['id'], run=str(run), screening_db=str(db))
        return {'review_id': entry['id'], 'records': len(screening.snapshot(db)['records'])}

    def search(self, identifier, body):
        return self.plan_run(identifier, body, 'main')

    def plan_run(self, identifier, body, kind):
        with self.lock:
            entry = self.entry(identifier)
            if any(j.get('review_id')==identifier and j['status']=='running' for j in self.jobs.values()):
                raise ValueError('A review job is already running')
            if kind == 'main':
                entry, corpus = self.mutable_corpus(identifier)
                if corpus['records']:
                    raise ValueError('Main search requires an empty review; existing corpora are preserved')
            if any(k in body for k in ('query','queries','sources','limit','year_from','year_to','date_from','date_to')):
                raise ValueError('Search settings come from the approved protocol. Open Review protocol to edit and approve them.')
            authorization = review_plan.authorize(entry['screening_db'], body, kind)
            job_id = authorization['run_id']
            folder = self.root / ('approved-'+kind+'-'+job_id)
            job = {'id':job_id,'review_id':identifier,'status':'running','stage':kind+' search',
                   'session_report':str(folder/'SESSION.md'),'started_utc':timestamp()}
            self.jobs[job_id]=job
            self._save_jobs()
            def execute():
                result = None
                try:
                    result = review_plan.run_authorized(entry['screening_db'], authorization, folder)
                    with self.lock:
                        review_plan.check_authorization(entry['screening_db'], authorization)
                        if kind == 'main':
                            # Registration re-check happens under the same workspace lock as edits.
                            _, corpus = self.mutable_corpus_for_registration(identifier, job_id)
                            self._replace_corpus(entry, corpus, result, folder)
                        active = self.entry(identifier)['screening_db']
                        review_plan.record_run(active, authorization, result, 'complete')
                        job.update(status='complete',finished_utc=timestamp())
                        self._save_jobs()
                except Exception as exc:
                    reason = str(exc) if isinstance(exc,(ValueError,OSError,RuntimeError)) else type(exc).__name__
                    with self.lock:
                        active = self.entry(identifier)['screening_db']
                        review_plan.record_run(active, authorization, result or folder/'retrieval', 'failed', error=reason)
                        job.update(status='failed',error=reason,finished_utc=timestamp())
                        self._save_jobs()
            self.executor.submit(execute)
            return dict(job)

    def mutable_corpus_for_registration(self, identifier, own_job):
        entry=self.entry(identifier)
        if any(j.get('review_id')==identifier and j['status']=='running' and j['id']!=own_job for j in self.jobs.values()):
            raise ValueError('Another review job is running')
        snapshot=screening.snapshot(entry['screening_db'])
        if snapshot['events'] or entry.get('evidence_db') or snapshot['records']:
            raise ValueError('The corpus changed; results retained separately')
        return entry,snapshot

    def plan_action(self, identifier, body):
        with self.lock:
            entry=self.entry(identifier)
            if body.get('action')=='ai-decision':
                from .protocol_ai import decide
                return decide(entry['screening_db'],body)
            if body.get('action')!='ai-request':
                return review_plan.mutate(entry['screening_db'],body)
            self.guard_ai_job(identifier)
            config=dict(self.ai.config)
            if config.get('mode')=='off':raise ValueError('Select a model in Settings first')
            if (body.get('selected_provider'),body.get('selected_model'))!=(config['provider'],config['model']):
                raise ValueError('AI selection changed. Review the selected model before running.')
            if config['mode']=='cloud' and body.get('allow_external') is not True:
                raise ValueError('Confirm sending the approved questions and selected section to the cloud provider')
            from . import protocol_ai
            packet=protocol_ai.request(entry['screening_db'],body,config)
            job_id=uuid4().hex;folder=self.root/('protocol-ai-'+job_id)
            from .pipeline import SessionJournal
            journal=SessionJournal(folder,{'operation':'Protocol AI','request_id':packet['request_id'],'section':body.get('section')})
            job={'id':job_id,'review_id':identifier,'status':'running','stage':'Protocol suggestions','task':'protocol','provider':config['provider'],'model':config['model'],
                 'session_report':str(folder/'SESSION.md'),'started_utc':timestamp()}
            self.jobs[job_id]=job;self._save_jobs()
            def execute():
                try:
                    response=self.ai.run_packet(packet,folder/'model',allow_external=body.get('allow_external') is True,config=config)
                    protocol_ai.record(entry['screening_db'],response)
                    journal.data['status']='complete';journal.record('Protocol AI','info','Proposals recorded without changing the protocol draft or approval',evidence='model/response.json')
                    with self.lock:job.update(status='complete',finished_utc=timestamp());self._save_jobs()
                except Exception as exc:
                    reason=str(exc) if isinstance(exc,ValueError) else type(exc).__name__
                    protocol_ai.failure(entry['screening_db'],packet['request_id'],reason)
                    journal.data['status']='failed';journal.record('Protocol AI','error',reason,remedy='Review the response and explicitly retry, or continue manually. Draft and approvals are unchanged.')
                    with self.lock:job.update(status='failed',error=reason,finished_utc=timestamp());self._save_jobs()
            self.executor.submit(execute)
            return dict(job)

    def pilot_preview(self, identifier):
        return review_plan.inspect_pilots(self.entry(identifier)['screening_db'])

    def mutate_screening(self, identifier, body):
        with self.lock:
            entry = self.entry(identifier)
            if any(j.get('review_id') == identifier and j['status'] == 'running' for j in self.jobs.values()):
                raise ValueError('Wait for retrieval to finish before screening')
            db = entry['screening_db']
            version, action = body['version'], body['action']
            if type(version) is not int:
                raise ValueError('Criteria version must be an integer')
            if action == 'screening-access':
                return screening.screening_access(db, body.get('actor'), body.get('rationale'), expected_version=version, expected_binding=body.get('binding'), revoke=body.get('revoke'))
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

    def guard_ai_job(self, identifier):
        if any(j.get('review_id') == identifier and j.get('task') in ('questions','protocol','evidence') and j['status'] == 'running' for j in self.jobs.values()):
            raise ValueError('AI is already working for this review. Wait for it to finish before starting another request.')

    def ai_jobs(self):
        with self.lock:
            fields = ('id','review_id','task','status','stage','provider','model','started_utc','finished_utc','error')
            return {'jobs': [{k:j[k] for k in fields if k in j} for j in self.jobs.values() if j.get('task') in ('questions','protocol','evidence')]}

    def run_ai_request(self,identifier,body):
        with self.lock:
            entry=self.entry(identifier)
            if not entry.get('evidence_db'):raise ValueError('Start an evidence ledger first')
            self.guard_ai_job(identifier)
            packet=evidence.get_request(entry['evidence_db'],body['request_id'])
            config=dict(self.ai.config)
            if config.get('mode')=='off':raise ValueError('Open Settings and select an AI model first')
            if body.get('selected_provider')!=config['provider'] or body.get('selected_model')!=config['model']:
                raise ValueError('AI selection changed. Review the selected provider/model before running.')
            if config.get('mode')=='cloud' and body.get('allow_external') is not True:
                raise ValueError('Confirm sending this saved request to the selected cloud provider')
            job_id=uuid4().hex;folder=self.root/('ai-request-'+job_id)
            from .pipeline import SessionJournal
            journal=SessionJournal(folder,{'operation':'AI generation','provider':config['provider'],'model':config['model'],'request_id':packet['request_id']})
            job={'id':job_id,'review_id':identifier,'status':'running','stage':'Generating AI proposals','task':'evidence','session_report':str(folder/'SESSION.md'),'provider':config['provider'],'model':config['model'],'started_utc':timestamp()}
            self.jobs[job_id]=job;self._save_jobs()
            def execute():
                try:
                    envelope=self.ai.run_packet(packet,folder/'model',allow_external=body.get('allow_external') is True,config=config)
                    ids=evidence.import_ai(entry['evidence_db'],envelope)
                    journal.data['status']='complete'
                    journal.record('AI generation','info',f'{len(ids)} proposals imported pending human review',evidence='model/response.json')
                    with self.lock:job.update(status='complete',stage='AI proposals await human review',proposal_ids=ids,finished_utc=timestamp());self._save_jobs()
                except Exception as exc:
                    journal.data['status']='failed'
                    reason=str(exc) if isinstance(exc,ValueError) else type(exc).__name__
                    journal.record('AI generation or validation','error',reason,evidence='model/',remedy='Inspect saved output and provider usage before an explicit retry. No proposals are automatically approved.')
                    with self.lock:job.update(status='failed',error=('AI request failed: '+reason if isinstance(exc,ValueError) else 'AI generation or proposal validation failed. Inspect saved output and provider usage before retrying.'),finished_utc=timestamp());self._save_jobs()
            self.executor.submit(execute)
            return dict(job)


    def question_action(self, identifier, body):
        with self.lock:
            entry = self.entry(identifier)
            if body.get('action') != 'request':
                return questions.mutate(entry['screening_db'], body)
            self.guard_ai_job(identifier)
            config = dict(self.ai.config)
            if config.get('mode') == 'off':
                raise ValueError('Open Settings and select an AI model first')
            if (body.get('selected_provider'), body.get('selected_model')) != (config['provider'], config['model']):
                raise ValueError('AI selection changed. Review the selected provider/model before running.')
            if config['mode'] == 'cloud' and body.get('allow_external') is not True:
                raise ValueError('Confirm sending the saved topic and questions to the selected cloud provider')
            result = questions.mutate(entry['screening_db'], body | {'provider': config['provider'], 'model': config['model']})
            packet = result['history'][-1]['content']['packet']
            job_id = uuid4().hex
            folder = self.root / ('question-ai-' + job_id)
            from .pipeline import SessionJournal
            journal = SessionJournal(folder, {'operation': 'Topic/question proposals', 'request_id': packet['request_id'],
                                             'provider': config['provider'], 'model': config['model']})
            job = {'id': job_id, 'review_id': identifier, 'status': 'running', 'stage': 'Topic/question proposals', 'task':'questions', 'provider':config['provider'], 'model':config['model'],
                   'session_report': str(folder / 'SESSION.md'), 'started_utc': timestamp()}
            self.jobs[job_id] = job
            self._save_jobs()
            def execute():
                try:
                    envelope = self.ai.run_packet(packet, folder / 'model', allow_external=body.get('allow_external') is True, config=config)
                    questions.record_response(entry['screening_db'], envelope)
                    journal.data['status'] = 'complete'
                    journal.record('Topic/question AI', 'info', 'Proposals recorded; draft and approval unchanged', evidence='model/response.json')
                    with self.lock:
                        job.update(status='complete', finished_utc=timestamp())
                        self._save_jobs()
                except Exception as exc:
                    reason = str(exc) if isinstance(exc, ValueError) else type(exc).__name__
                    journal.data['status'] = 'failed'
                    journal.record('Topic/question AI', 'error', reason, remedy='Inspect saved response and provider usage before explicitly retrying. No draft or approval was changed.')
                    with self.lock:
                        job.update(status='failed', error=reason, finished_utc=timestamp())
                        self._save_jobs()
            self.executor.submit(execute)
            return dict(job)

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

    def import_venue_metrics(self, identifier, body):
        from .corpus import parse_venue_metrics
        with self.lock:
            self.entry(identifier)
            name = body.get('name', '')
            if not isinstance(name,str) or Path(name).suffix.lower() != '.csv':
                raise ValueError('Choose a venue-metrics CSV file')
            raw = base64.b64decode(body.get('base64',''), validate=True)
            if len(raw)>5*1024*1024:
                raise ValueError('Venue-metrics CSV exceeds 5 MB')
            text=raw.decode('utf-8-sig')
            if body.get('format')=='scimago':
                from .venue_metrics import scimago_snapshot
                text=scimago_snapshot(text,body.get('year'),body.get('retrieved_date',''))
                normalized=text.encode('utf-8')
            else:normalized=raw
            rows = parse_venue_metrics(text)
            folder = self.root / ('venue-metrics-' + uuid4().hex)
            folder.mkdir()
            (folder/'input.csv').write_bytes(normalized)
            if body.get('format')=='scimago':(folder/'scimago-original.csv').write_bytes(raw)
            write_json(folder/'rows.json',rows)
            write_json(folder/'manifest.json',{'mode':'external-venue-metrics','original_name':Path(name).name,'imported_utc':timestamp(),
                'files':{p.name:sha256(p.read_bytes()).hexdigest() for p in sorted(folder.iterdir())}})
            self.update(identifier,venue_metrics=str(folder))
            return {'rows':len(rows),'years':sorted({r['year'] for r in rows})}

    def fetch_venue_metrics(self, identifier, body):
        from .venue_metrics import PROVIDERS
        from datetime import date
        provider,year=body.get('provider'),body.get('year')
        limit=body.get('limit',10)
        if provider not in PROVIDERS:raise ValueError('Choose Elsevier or Clarivate')
        if type(year) is not int or not 1997<=year<=date.today().year:raise ValueError('Invalid metric year')
        if type(limit) is not int or not 1<=limit<=100:raise ValueError('Choose 1–100 top venues')
        with self.lock:
            self.entry(identifier)
            if any(j.get('review_id')==identifier and j['status']=='running' for j in self.jobs.values()):
                raise ValueError('Wait for the running review job')
            venues=self.corpus_analysis(identifier,scope=body.get('scope','all'))['venues'][:limit]
            from .pipeline import SessionJournal
            folder=self.root/('venue-metrics-'+uuid4().hex)
            journal=SessionJournal(folder,{'operation':'venue metrics','provider':provider,'year':year,'venues':len(venues)})
            job_id=uuid4().hex
            job={'id':job_id,'review_id':identifier,'status':'running','stage':'venue metrics',
                 'started_utc':timestamp(),'session_report':str(folder/'SESSION.md'),'kind':'venue-metrics'}
            self.jobs[job_id]=job;self._save_jobs()
            def execute():
                from .venue_metrics import retrieve,csv_snapshot
                try:
                    rows,audit=retrieve(venues,provider,year)
                    write_json(folder/'lookup-audit.json',audit)
                    for item in audit:
                        if item['status']!='retrieved':
                            journal.record('venue lookup','warning',item['venue']+': '+item.get('reason','No usable data returned'),
                                evidence='lookup-audit.json',remedy='Check provider access, ISSNs and year; use an authorized provider export where available.')
                    if not rows:raise ValueError('No usable metrics returned; previous snapshot preserved. See session log.')
                    raw=csv_snapshot(rows).encode('utf-8')
                    result=self.import_venue_metrics(identifier,{'name':provider+'-'+str(year)+'.csv','base64':base64.b64encode(raw).decode()})
                    journal.data['status']='partial' if any(i['status']!='retrieved' for i in audit) else 'complete'
                    journal.record('metrics snapshot','info',str(len(rows))+' provider rows saved with source links',evidence='lookup-audit.json')
                    with self.lock:
                        job.update(status='complete',outcome=journal.data['status'],finished_utc=timestamp(),rows=result['rows'])
                        self._save_jobs()
                except Exception as exc:
                    message=str(exc) if isinstance(exc,ValueError) else 'Venue metric retrieval failed; inspect provider access and retry'
                    journal.data['status']='failed'
                    journal.record('venue metrics','error',message,remedy='Configure the server API key and approved provider access, or import the provider CSV. Existing metrics are preserved.')
                    with self.lock:
                        job.update(status='failed',error=message,finished_utc=timestamp());self._save_jobs()
            self.executor.submit(execute)
            return dict(job)

    def corpus_analysis(self, identifier, *, scope='all', year=None, category=None, include_input=False):
        from .corpus import corpus_summary, parse_venue_metrics
        if scope not in ('all','included'):
            raise ValueError('Choose all or included report scope')
        entry=self.entry(identifier)
        state=screening.snapshot(entry['screening_db'])
        records=[Record(**r['metadata']) for r in state['records'] if scope=='all' or r['fulltext']=='include']
        metrics=[]; origin=None
        if entry.get('venue_metrics'):
            folder=Path(entry['venue_metrics'])
            manifest=json.loads((folder/'manifest.json').read_text())
            for name in manifest['files']:
                if sha256((folder/name).read_bytes()).hexdigest()!=manifest['files'].get(name):
                    raise ValueError('External venue-metrics snapshot hash mismatch')
            metrics=parse_venue_metrics((folder/'input.csv').read_text(encoding='utf-8-sig'))
            origin={'filename':manifest['original_name'],'imported_utc':manifest['imported_utc'],'sha256':manifest['files']['input.csv'],'rows':len(metrics)}
        report=corpus_summary(records,metrics,year=year,category=category)
        report.update(screening_complete=state['prisma']['complete'],scope=scope,review_id=state['review_id'],criteria_version=state['criteria_version'],metric_import=origin)
        if include_input:
            report['_input_records']=[r.to_dict() for r in records]
            report['_metric_folder']=entry.get('venue_metrics')
        return report

    def export_corpus(self, identifier, **options):
        from .corpus import export_corpus
        report=self.corpus_analysis(identifier,include_input=True,**options)
        inputs=report.pop('_input_records')
        metric_folder=report.pop('_metric_folder')
        folder=self.root / ('corpus-export-' + uuid4().hex)
        folder.mkdir()
        export_corpus(report,folder)
        write_json(folder/'input-records.json',inputs)
        if metric_folder:
            raw=(Path(metric_folder)/'input.csv').read_bytes()
            if sha256(raw).hexdigest()!=report['metric_import']['sha256']:
                raise ValueError('External metrics changed during export')
            (folder/'external-venue-metrics.csv').write_bytes(raw)
            original=Path(metric_folder)/'scimago-original.csv'
            if original.exists():
                metric_manifest=json.loads((Path(metric_folder)/'manifest.json').read_text())
                original_bytes=original.read_bytes()
                if sha256(original_bytes).hexdigest()!=metric_manifest['files'].get(original.name):raise ValueError('SCImago original hash mismatch')
                (folder/original.name).write_bytes(original_bytes)
        write_json(folder/'manifest.json',{'scope':report['scope'],'review_id':report['review_id'],'created_utc':timestamp(),
            'files':{p.name:sha256(p.read_bytes()).hexdigest() for p in sorted(folder.iterdir())}})
        data=io.BytesIO()
        with zipfile.ZipFile(data,'w',zipfile.ZIP_DEFLATED) as archive:
            for path in sorted(folder.iterdir()):archive.write(path,path.name)
        return data.getvalue()

    def export(self, identifier):
        entry = self.entry(identifier)
        folder = self.root / ('export-' + uuid4().hex)
        from .replication import create as create_bundle
        create_bundle(entry['screening_db'], folder, entry.get('evidence_db'))
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
            if path in ('/app.js', '/settings.js', '/questions.js', '/question_frameworks.js', '/protocol.js', '/protocol_helpers.js', '/verification.js', '/styles.css'):
                return self.send(200, (WEB / path[1:]).read_bytes(), 'text/javascript; charset=utf-8' if path.endswith('.js') else 'text/css; charset=utf-8')
            if path == '/api/question-frameworks':
                from .question_frameworks import catalog
                return self.send(200, catalog())
            if path == '/api/ai-settings':
                return self.send(200, self.server.workspace.ai.status())
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
            if path == '/api/ai-jobs':
                return self.send(200, self.server.workspace.ai_jobs())
            if path == '/api/job':
                job = self.server.workspace.jobs.get(query.get('id', [''])[0])
                if not job:
                    raise ValueError('Job not found')
                return self.send(200, job)
            identifier = query.get('review', [''])[0]
            entry = self.server.workspace.entry(identifier)
            if path in ('/api/corpus','/api/corpus-export'):
                options={'scope':query.get('scope',['all'])[0], 'year':int(query['year'][0]) if query.get('year',[''])[0] else None, 'category':query.get('category',[''])[0] or None}
                if path == '/api/corpus-export':
                    return self.send(200,self.server.workspace.export_corpus(identifier,**options),'application/zip',download='corpus-analysis.zip')
                return self.send(200,self.server.workspace.corpus_analysis(identifier,**options))
            if path == '/api/plan':
                return self.send(200, review_plan.state(entry['screening_db']) | {'pilots':self.server.workspace.pilot_preview(identifier)})
            if path == '/api/questions':
                return self.send(200, questions.state(entry['screening_db']))
            if path == '/api/questions-export':
                return self.send(200, questions.disclosure(entry['screening_db']), download='ai-assistance-and-revision-record.json')
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
            if urlsplit(self.path).path == '/api/verify-bundle':
                if self.headers.get('Content-Type', '').split(';')[0] != 'application/zip':
                    raise ValueError('Choose a review bundle ZIP')
                length = int(self.headers.get('Content-Length', '0'))
                if not 0 < length <= 64 * 1024 * 1024:
                    raise ValueError('Viewer upload limit is 64 MiB; use slr verify for larger local bundles')
                from .replication import verify
                with tempfile.TemporaryDirectory(prefix='litatlas-viewer-') as temp:
                    path = Path(temp) / 'bundle.zip'
                    remaining = length
                    with path.open('xb') as handle:
                        while remaining:
                            data = self.rfile.read(min(remaining, 1024 * 1024))
                            if not data: raise ValueError('Incomplete ZIP upload')
                            handle.write(data)
                            remaining -= len(data)
                    with zipfile.ZipFile(path) as archive:
                        if sum(i.file_size for i in archive.infolist()) > 128 * 1024 * 1024:
                            raise ValueError('Viewer expanded-size limit is 128 MiB; use slr verify for larger local bundles')
                    result = verify(path)
                return self.send(200, result)
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
            if path == '/api/ai-settings':
                action = body.get('action')
                if action == 'local-setup':
                    if body.get('accept_license') is not True:raise ValueError('Review and accept the selected model license before downloading')
                    result = workspace.ai.setup(body.get('model'))
                elif action == 'cloud-models':result = workspace.ai.cloud_models(body.get('provider'), body.get('key'), body.get('remember') is True)
                elif action == 'cloud-save':result = workspace.ai.save_cloud(body.get('provider'), body.get('model'))
                elif action == 'test':result = workspace.ai.test()
                elif action == 'off':result = workspace.ai.disable()
                elif action == 'forget-key':result = workspace.ai.remove_key(body.get('provider'))
                else:raise ValueError('Unknown AI settings action')
                return self.send(200,result)
            if path == '/api/create':
                return self.send(200, workspace.create(body))
            identifier = body.get('review_id')
            if path in ('/api/import', '/api/search', '/api/screening', '/api/evidence', '/api/venue-metrics', '/api/venue-metrics-fetch', '/api/evidence-run', '/api/questions', '/api/plan', '/api/plan-run'):
                workspace.guard_ledger(identifier, body)
            if path == '/api/venue-metrics-fetch':
                return self.send(200,workspace.fetch_venue_metrics(identifier,body))
            if path == '/api/venue-metrics':
                return self.send(200,workspace.import_venue_metrics(identifier,body))
            if path == '/api/import':
                return self.send(200, workspace.import_uploads(identifier, body))
            if path == '/api/search':
                return self.send(200, workspace.search(identifier, body))
            if path == '/api/screening':
                return self.send(200, workspace.mutate_screening(identifier, body))
            if path == '/api/plan':
                return self.send(200, workspace.plan_action(identifier,body))
            if path == '/api/plan-run':
                return self.send(200, workspace.plan_run(identifier,body,body.get('kind')))
            if path == '/api/questions':
                return self.send(200, workspace.question_action(identifier, body))
            if path == '/api/evidence-run':
                return self.send(200,workspace.run_ai_request(identifier,body))
            if path == '/api/evidence':
                return self.send(200, workspace.evidence_action(identifier, body))
            self.send(404, {'error': 'Not found'})
        except Exception as exc:
            self.error(exc)

    def error(self, exc):
        if isinstance(exc, PermissionError):
            self.send(403, {'error': str(exc)})
        elif isinstance(exc, (ValueError, TypeError, KeyError, sqlite3.IntegrityError, zipfile.BadZipFile)):
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
        workspace.ai.close()
        workspace.executor.shutdown(wait=False, cancel_futures=True)
    return 0
