"""Transactional, append-only human screening in a local SQLite ledger."""
from collections import Counter
from contextlib import contextmanager
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import random
import sqlite3
from uuid import uuid4

from .agreement import NOTE as AGREEMENT_NOTE, stage_agreement
from .models import Record, deduplicate

SCHEMA = """
CREATE TABLE review (id TEXT PRIMARY KEY, name TEXT NOT NULL, reviewers TEXT NOT NULL,
 adjudicator TEXT NOT NULL, identification TEXT NOT NULL, origin TEXT NOT NULL);
CREATE TABLE criteria (version INTEGER PRIMARY KEY, text TEXT NOT NULL, sha256 TEXT NOT NULL, created_utc TEXT NOT NULL);
CREATE TABLE records (id TEXT PRIMARY KEY, metadata TEXT NOT NULL);
CREATE TABLE events (sequence INTEGER PRIMARY KEY AUTOINCREMENT, review_id TEXT NOT NULL,
 record_id TEXT NOT NULL REFERENCES records(id), version INTEGER NOT NULL REFERENCES criteria(version),
 kind TEXT NOT NULL, stage TEXT NOT NULL, actor TEXT NOT NULL, value TEXT NOT NULL,
 reason TEXT NOT NULL, created_utc TEXT NOT NULL, UNIQUE(record_id,version,kind,stage,actor));
CREATE TRIGGER immutable_events_update BEFORE UPDATE ON events BEGIN SELECT RAISE(ABORT,'append-only events'); END;
CREATE TRIGGER immutable_events_delete BEFORE DELETE ON events BEGIN SELECT RAISE(ABORT,'append-only events'); END;
CREATE TRIGGER immutable_criteria_update BEFORE UPDATE ON criteria BEGIN SELECT RAISE(ABORT,'immutable criteria'); END;
CREATE TRIGGER immutable_criteria_delete BEFORE DELETE ON criteria BEGIN SELECT RAISE(ABORT,'immutable criteria'); END;
"""


def now():
    return datetime.now(timezone.utc).isoformat()


def _text(value, label):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f'{label} must be nonempty')
    return value.strip()


def verify_run(folder):
    """Reject failed, modified, or inconsistent retrieval snapshots."""
    folder = Path(folder)
    manifest = json.loads((folder / 'manifest.json').read_text(encoding='utf-8'))
    if manifest.get('status') != 'complete':
        raise ValueError('Only completed retrieval runs can enter screening')
    hashes = manifest.get('files', {})
    if not {'records.json', 'retrieved.json', 'duplicates.json', 'identification.json'} <= hashes.keys():
        raise ValueError('Manifest does not cover required screening inputs')
    for name, digest in hashes.items():
        if Path(name).name != name or '/' in name or '\\' in name:
            raise ValueError('Invalid artifact path in manifest')
        if sha256((folder / name).read_bytes()).hexdigest() != digest:
            raise ValueError(f'Artifact hash mismatch: {name}')
    records = [Record(**r).to_dict() for r in json.loads((folder / 'records.json').read_text(encoding='utf-8'))]
    retrieved = [Record(**r) for r in json.loads((folder / 'retrieved.json').read_text(encoding='utf-8'))]
    method = manifest.get('deduplication', 'doi-v1')
    if method not in ('doi-v1', 'doi-or-source-id-v1'):
        raise ValueError('Unknown deduplication method')
    unique, duplicates = deduplicate(retrieved, identity=method == 'doi-or-source-id-v1')
    if records != [r.to_dict() for r in unique] or duplicates != json.loads((folder / 'duplicates.json').read_text(encoding='utf-8')):
        raise ValueError('Retrieval and deduplication artifacts are inconsistent')
    counts = json.loads((folder / 'identification.json').read_text(encoding='utf-8'))
    if (counts.get('identified'), counts.get('duplicates_removed'), counts.get('records_for_screening')) != (len(retrieved), len(duplicates), len(unique)):
        raise ValueError('Identification counts are inconsistent')
    return records, counts, manifest


def initialize(database, run_folder, name, reviewers, adjudicator, criteria):
    name = _text(name, 'Review name')
    reviewers = [_text(r, 'Reviewer') for r in reviewers]
    adjudicator = _text(adjudicator, 'Adjudicator')
    if len(reviewers) != 2 or len(set(reviewers + [adjudicator])) != 3:
        raise ValueError('Provide two different reviewers and a separate adjudicator')
    criteria = _text(criteria, 'Criteria')
    records, counts, manifest = verify_run(run_folder)
    retrieved = json.loads((Path(run_folder) / 'retrieved.json').read_text(encoding='utf-8'))
    counts['identified_by_source'] = dict(Counter(r['source'] for r in retrieved))
    path = Path(database)
    with path.open('xb'):
        pass
    with sqlite3.connect(path) as conn:
        conn.executescript(SCHEMA)
        conn.execute('INSERT INTO review VALUES (?,?,?,?,?,?)', (str(uuid4()), name, json.dumps(reviewers), adjudicator, json.dumps(counts), json.dumps(manifest)))
        conn.execute('INSERT INTO criteria VALUES (1,?,?,?)', (criteria, sha256(criteria.encode()).hexdigest(), now()))
        for index, record in enumerate(records, 1):
            conn.execute('INSERT INTO records VALUES (?,?)', (f'R{index:06d}', json.dumps(record, ensure_ascii=False)))
    return len(records)


@contextmanager
def connect(database):
    if not Path(database).is_file():
        raise ValueError('Review database does not exist; initialize it first')
    conn = sqlite3.connect(Path(database).resolve().as_uri() + '?mode=rw', uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys=ON')
    try:
        conn.execute('BEGIN IMMEDIATE')
        yield conn
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    finally:
        conn.close()


def _context(conn):
    review = dict(conn.execute('SELECT * FROM review').fetchone())
    review['reviewers'] = json.loads(review['reviewers'])
    version = conn.execute('SELECT MAX(version) FROM criteria').fetchone()[0]
    return review, version


def _events(conn, record_id, version):
    return [dict(e) for e in conn.execute('SELECT * FROM events WHERE record_id=? AND version=? ORDER BY sequence', (record_id, version))]


def _state(events, stage, reviewers):
    votes = {e['actor']: e for e in events if e['kind'] == 'decision' and e['stage'] == stage}
    resolved = next((e for e in events if e['kind'] == 'adjudication' and e['stage'] == stage), None)
    if resolved:
        return resolved['value'], resolved['reason']
    if not all(r in votes for r in reviewers):
        return 'pending', ''
    a, b = (votes[r] for r in reviewers)
    if a['value'] != b['value'] or (a['value'] == 'exclude' and a['reason'] != b['reason']):
        return 'conflict', ''
    return a['value'], a['reason']


def _event(conn, review, version, record_id, kind, stage, actor, value, reason=''):
    if not conn.execute('SELECT 1 FROM records WHERE id=?', (record_id,)).fetchone():
        raise ValueError('Unknown record ID')
    try:
        conn.execute('INSERT INTO events (review_id,record_id,version,kind,stage,actor,value,reason,created_utc) VALUES (?,?,?,?,?,?,?,?,?)', (review['id'], record_id, version, kind, stage, actor, value, reason, now()))
    except sqlite3.IntegrityError:
        raise ValueError('This action is already recorded; history cannot be overwritten') from None


def _pilot(conn, version, reviewers):
    """The calibration pilot sample for this criteria version, or None."""
    rows = conn.execute("SELECT record_id, reason FROM events WHERE kind='pilot' AND version=? ORDER BY record_id", (version,)).fetchall()
    if not rows:
        return None
    ids = [r['record_id'] for r in rows]
    voted = Counter(r['record_id'] for r in conn.execute(
        "SELECT DISTINCT record_id, actor FROM events WHERE kind='decision' AND stage='title' AND version=?", (version,))
        if r['actor'] in reviewers)
    return {**json.loads(rows[0]['reason']), 'records': ids, 'complete': all(voted[i] == len(reviewers) for i in ids)}


def start_pilot(database, actor, size, *, seed=None, expected_version):
    """Draw a reproducible title-screening pilot sample both reviewers must finish first."""
    if type(size) is not int or size < 1:
        raise ValueError('Pilot size must be a positive integer')
    if seed is not None and type(seed) is not int:
        raise ValueError('Pilot seed must be an integer')
    with connect(database) as conn:
        review, version = _context(conn)
        _check_version(version, expected_version)
        if actor != review['adjudicator']:
            raise ValueError('Only the adjudicator may start a pilot calibration round')
        if _pilot(conn, version, review['reviewers']):
            raise ValueError('A pilot round already exists for this criteria version')
        if conn.execute("SELECT 1 FROM events WHERE kind='decision' AND stage='title' AND version=?", (version,)).fetchone():
            raise ValueError('Start the pilot before any title decisions in this criteria version')
        ids = [r[0] for r in conn.execute('SELECT id FROM records ORDER BY id')]
        if size > len(ids):
            raise ValueError(f'Pilot size exceeds the {len(ids)} records to screen')
        if seed is None:
            seed = int(sha256(f"{review['id']}:{version}".encode()).hexdigest()[:8], 16)
        sample = sorted(random.Random(seed).sample(ids, size))
        detail = json.dumps({'seed': seed, 'size': size, 'method': 'random.Random(seed).sample(sorted record IDs, size)'})
        for record_id in sample:
            _event(conn, review, version, record_id, 'pilot', 'title', actor, 'sample', detail)
        return sample


def _guided_protocol(conn):
    """True once a guided protocol was saved; legacy and standalone-protocol reviews keep direct criteria revision."""
    if not conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='plan_events'").fetchone():
        return False
    return bool(conn.execute("SELECT 1 FROM plan_events WHERE kind='protocol-save' LIMIT 1").fetchone())


def revise_criteria(database, text, *, expected_version):
    text = _text(text, 'Criteria')
    with connect(database) as conn:
        _, version = _context(conn)
        _check_version(version, expected_version)
        if _guided_protocol(conn):
            raise ValueError('This review has a guided protocol. Amend eligibility in Review protocol, section 1: saving it '
                             'updates the screening criteria, so the two cannot drift apart.')
        digest = sha256(text.encode()).hexdigest()
        if conn.execute('SELECT 1 FROM criteria WHERE sha256=?', (digest,)).fetchone():
            raise ValueError('Criteria text already exists; provide a distinct revision')
        conn.execute('INSERT INTO criteria VALUES (?,?,?,?)', (version + 1, text, digest, now()))
        return version + 1


def _screening_gate(conn):
    from . import review_plan as rp, questions
    state = rp._state(conn)
    origin = json.loads(conn.execute('SELECT origin FROM review').fetchone()[0])
    binding = {'ledger_id': state['ledger_id'], 'question_draft_sha256': questions.digest(state['question_draft']), 'criteria_sha256': state['criteria']['sha256'],
               'protocol_sha256': state['protocol_sha256'], 'question_approval': state['question_approval'],
               'origin_sha256': questions.digest(origin)}
    exceptions = [e for e in state['history'] if e['kind'] == 'screening-exception']
    revoked = {e['content']['target_sequence'] for e in state['history'] if e['kind'] == 'screening-exception-revoked'}
    exception = next((e for e in reversed(exceptions) if e['sequence'] not in revoked and e['content']['binding'] == binding), None)
    return {'allowed': bool(state['final_current'] or exception),
            'basis': 'approved-protocol' if state['final_current'] else 'protocol-deferred' if exception else 'blocked',
            'exception': exception, 'binding': binding,
            'notice': 'Imported search history is not verified. Existing decisions remain readable; new decisions require a current protocol approval or a recorded exception.'}


def screening_access(database, actor=None, rationale=None, *, expected_version=None, expected_binding=None, revoke=None):
    """Inspect access or record an adjudicator's explicit, version-bound deviation."""
    from . import review_plan as rp
    with connect(database) as conn:
        gate = _screening_gate(conn)
        if actor is not None:
            review, version = _context(conn)
            _check_version(version, expected_version)
            if actor != review['adjudicator']:
                raise ValueError('Only the adjudicator may record a protocol-deferred exception')
            if expected_binding != gate['binding']:
                raise ValueError('Screening context changed; reload before recording the exception')
            rationale = _text(rationale, 'Exception rationale')
            if len(rationale) < 20:
                raise ValueError('Explain the protocol deviation in at least 20 characters')
            if revoke is not None:
                if not gate['exception'] or gate['exception']['sequence'] != revoke:
                    raise ValueError('No matching current exception')
                rp._append(conn, 'screening-exception-revoked', actor, {'target_sequence': revoke, 'rationale': rationale})
            else:
                rp._append(conn, 'screening-exception', actor, {'binding': gate['binding'], 'rationale': rationale,
                    'notice': 'Protocol deferred; this exception is a reported deviation, not protocol approval or verification of external search.'})
        return _screening_gate(conn)


def decide(database, record_id, actor, stage, value, reason='', adjudicate=False, *, expected_version):
    if stage not in ('title', 'fulltext') or value not in ('include', 'exclude'):
        raise ValueError('Use title/fulltext and include/exclude')
    reason = reason.strip()
    if value == 'exclude' or adjudicate:
        reason = _text(reason, 'Exclusion reason or adjudication rationale')
    with connect(database) as conn:
        review, version = _context(conn)
        _check_version(version, expected_version)
        if actor not in ([review['adjudicator']] if adjudicate else review['reviewers']):
            raise ValueError('Actor is not assigned to this role')
        if not _screening_gate(conn)['allowed']:
            raise ValueError('Screening blocked: approve the protocol or record an adjudicator protocol-deferred exception')
        events = _events(conn, record_id, version)
        if stage == 'title' and not adjudicate:
            pilot = _pilot(conn, version, review['reviewers'])
            if pilot and not pilot['complete'] and record_id not in pilot['records']:
                raise ValueError('Both reviewers must finish the pilot calibration records before other title screening')
        if stage == 'fulltext':
            if _state(events, 'title', review['reviewers'])[0] != 'include':
                raise ValueError('Resolve title screening to include before full-text eligibility')
            if not any(e['kind'] == 'retrieval' and e['value'] == 'retrieved' for e in events):
                raise ValueError('Full text must be marked retrieved before eligibility')
        if adjudicate and _state(events, stage, review['reviewers'])[0] != 'conflict':
            raise ValueError('Adjudication requires two conflicting reviewer decisions')
        _event(conn, review, version, record_id, 'adjudication' if adjudicate else 'decision', stage, actor, value, reason)


def record_retrieval(database, record_id, actor, value, reason='', *, expected_version):
    if value not in ('retrieved', 'not_retrieved'):
        raise ValueError('Retrieval must be retrieved or not_retrieved')
    reason = _text(reason, 'Reason') if value == 'not_retrieved' else reason.strip()
    with connect(database) as conn:
        review, version = _context(conn)
        _check_version(version, expected_version)
        if actor not in review['reviewers'] + [review['adjudicator']]:
            raise ValueError('Unknown actor')
        events = _events(conn, record_id, version)
        if _state(events, 'title', review['reviewers'])[0] != 'include':
            raise ValueError('Title screening must resolve to include before retrieval')
        if any(e['kind'] == 'retrieval' for e in events):
            raise ValueError('Retrieval is already recorded for this criteria version')
        _event(conn, review, version, record_id, 'retrieval', 'fulltext', actor, value, reason)


def link_study(database, record_id, actor, study_id, *, expected_version):
    study_id = _text(study_id, 'Study ID')
    with connect(database) as conn:
        review, version = _context(conn)
        _check_version(version, expected_version)
        if actor != review['adjudicator']:
            raise ValueError('Only the adjudicator may assign study IDs')
        events = _events(conn, record_id, version)
        if _state(events, 'fulltext', review['reviewers'])[0] != 'include':
            raise ValueError('Study linking requires included full-text eligibility')
        _event(conn, review, version, record_id, 'study', 'fulltext', actor, study_id)


def snapshot(database, reviewer=None):
    with connect(database) as conn:
        review, version = _context(conn)
        if reviewer is not None and reviewer not in review['reviewers']:
            raise ValueError('Unknown reviewer')
        rows, study_ids = [], set()
        pilot = _pilot(conn, version, review['reviewers'])
        pilot_open = pilot is not None and not pilot['complete']
        votes = {'title': {}, 'fulltext': {}}
        for row in conn.execute('SELECT * FROM records ORDER BY id'):
            events = _events(conn, row['id'], version)
            title, title_reason = _state(events, 'title', review['reviewers'])
            fulltext, fulltext_reason = _state(events, 'fulltext', review['reviewers'])
            retrieval = next((e['value'] for e in events if e['kind'] == 'retrieval'), 'pending')
            study_id = next((e['value'] for e in events if e['kind'] == 'study'), None)
            item = {'record_id': row['id'], 'metadata': json.loads(row['metadata'])}
            if reviewer is not None:
                own = [e for e in events if e['kind'] == 'decision' and e['actor'] == reviewer]
                stage = 'title' if not any(e['stage'] == 'title' for e in own) else ('fulltext' if title == 'include' and retrieval == 'retrieved' and not any(e['stage'] == 'fulltext' for e in own) else None)
                if stage == 'title' and pilot_open and row['id'] not in pilot['records']:
                    stage = None
                if stage:
                    rows.append({**item, 'stage': stage, 'pilot': pilot is not None and row['id'] in pilot['records']})
                continue
            for e in events:
                if e['kind'] == 'decision':
                    votes[e['stage']].setdefault(row['id'], {})[e['actor']] = e
            rows.append({**item, 'title': title, 'title_reason': title_reason, 'retrieval': retrieval,
                         'fulltext': fulltext if retrieval == 'retrieved' else 'not_applicable',
                         'fulltext_reason': fulltext_reason, 'study_id': study_id})
            if study_id and fulltext == 'include':
                study_ids.add(study_id)
        if reviewer is not None:
            return {'review_id': review['id'], 'criteria_version': version, 'criteria': dict(conn.execute('SELECT * FROM criteria WHERE version=?', (version,)).fetchone()), 'queue': rows,
                    'pilot_open': pilot_open}
        agreement = {'criteria_version': version, 'note': AGREEMENT_NOTE,
                     'title': stage_agreement(votes['title'], review['reviewers']),
                     'fulltext': stage_agreement(votes['fulltext'], review['reviewers'])}
        if pilot:
            pilot = {**pilot, 'title_agreement': stage_agreement(votes['title'], review['reviewers'], set(pilot['records']))}
        counts = json.loads(review['identification'])
        title_counts = Counter(r['title'] for r in rows)
        eligible = [r for r in rows if r['title'] == 'include']
        assessed = [r for r in eligible if r['retrieval'] == 'retrieved']
        included = [r for r in assessed if r['fulltext'] == 'include']
        prisma = {'identified': counts['identified'], 'identified_by_source': counts.get('identified_by_source', {}), 'duplicates_removed': counts['duplicates_removed'],
                  'records_to_screen': len(rows), 'records_screened': title_counts['include'] + title_counts['exclude'],
                  'title_pending': title_counts['pending'], 'title_conflicts': title_counts['conflict'],
                  'records_excluded': title_counts['exclude'], 'reports_sought': len(eligible),
                  'retrieval_pending': sum(r['retrieval'] == 'pending' for r in eligible),
                  'reports_not_retrieved': sum(r['retrieval'] == 'not_retrieved' for r in eligible),
                  'reports_assessed': len(assessed), 'eligibility_pending': sum(r['fulltext'] == 'pending' for r in assessed),
                  'eligibility_conflicts': sum(r['fulltext'] == 'conflict' for r in assessed),
                  'reports_excluded': sum(r['fulltext'] == 'exclude' for r in assessed),
                  'exclusion_reasons': dict(Counter(r['fulltext_reason'] for r in assessed if r['fulltext'] == 'exclude')),
                  'reports_included': len(included), 'studies_included': len(study_ids),
                  'included_reports_without_study': sum(not r['study_id'] for r in included)}
        method = json.loads(review['origin']).get('deduplication', 'doi-v1')
        prisma['deduplication_method'] = method
        prisma['deduplication_notice'] = ('Matching normalized DOI and exact source/ID' if method == 'doi-or-source-id-v1' else 'Matching normalized DOI' if method == 'doi-v1' else 'Unknown deduplication method') + '; no fuzzy title/author matching. Cross-export records without matching identifiers may remain; counts can overstate distinct reports.'
        prisma['complete'] = not any(prisma[k] for k in ('title_pending', 'title_conflicts', 'retrieval_pending', 'eligibility_pending', 'eligibility_conflicts', 'included_reports_without_study'))
        return {'review_id': review['id'], 'name': review['name'], 'criteria_version': version,
                'criteria': dict(conn.execute('SELECT * FROM criteria WHERE version=?', (version,)).fetchone()),
                'origin': json.loads(review['origin']), 'screening_access': _screening_gate(conn),
                'screening_deviations': [dict(e) | {'content': json.loads(e['content'])} for e in conn.execute("SELECT * FROM plan_events WHERE kind IN ('screening-exception','screening-exception-revoked') ORDER BY sequence")], 'records': rows, 'prisma': prisma,
                'agreement': agreement, 'pilot': pilot,
                'criteria_history': [dict(r) for r in conn.execute('SELECT * FROM criteria ORDER BY version')],
                'events': [dict(e) for e in conn.execute('SELECT * FROM events ORDER BY sequence')]}


def _check_version(actual, expected):
    if type(expected) is not int or actual != expected:
        raise ValueError(f"Stale criteria version: current version is {actual}")
