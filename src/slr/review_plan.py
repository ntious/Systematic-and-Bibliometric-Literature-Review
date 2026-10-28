"""Human-approved protocol sections and version-bound pilot/main retrieval.

Trusted local actor labels are not authenticated identities. Standalone retrieval
remains an unbound research utility; it does not establish protocol approval.
"""
from hashlib import sha256
import json
from pathlib import Path
from uuid import uuid4

from . import protocol, questions
from .screening import connect, now, verify_run

SECTIONS = {
    'eligibility': {'label': 'Eligibility and publication period', 'fields': ['eligibility', 'publication_period']},
    'sources': {'label': 'Information sources', 'fields': ['information_sources']},
    'search': {'label': 'Keywords and source-specific queries', 'fields': ['keywords', 'search_strategy', 'searches']},
    'screening': {'label': 'Screening procedure', 'fields': ['selection_process', 'screening']},
    'extraction': {'label': 'Extraction fields and procedure', 'fields': ['data_items', 'data_collection_process', 'extraction']},
    'appraisal': {'label': 'Critical appraisal', 'fields': ['risk_of_bias']},
    'synthesis': {'label': 'Synthesis plan', 'fields': ['synthesis', 'meta_bias', 'confidence']},
}
SOURCES = {
    'openalex': {'label': 'OpenAlex', 'note': 'Metadata only. Provider-specific search syntax; cursor pagination may require an API key.'},
    'crossref': {'label': 'Crossref', 'note': 'Metadata only. Free-text search; Boolean expressions are not portable.'},
    'pubmed': {'label': 'PubMed', 'note': 'Metadata only. Use PubMed query syntax. Larger searches need partitioning.'},
}
PILOT_MAX = 100
NA_SECTIONS = ('extraction', 'appraisal', 'synthesis')


def _tables(conn):
    for statement in protocol.PROTOCOL_TABLES:
        conn.execute(statement)
    conn.execute('''CREATE TABLE IF NOT EXISTS plan_events
        (sequence INTEGER PRIMARY KEY, kind TEXT NOT NULL, actor TEXT NOT NULL,
         content TEXT NOT NULL, created_utc TEXT NOT NULL)''')
    for action in ('UPDATE', 'DELETE'):
        conn.execute(f'''CREATE TRIGGER IF NOT EXISTS immutable_plan_{action.lower()}
            BEFORE {action} ON plan_events BEGIN SELECT RAISE(ABORT,'append-only plan'); END''')


def _events(conn):
    return [dict(r) | {'content': json.loads(r['content'])} for r in conn.execute('SELECT * FROM plan_events ORDER BY sequence')]


def _append(conn, kind, actor, content):
    return conn.execute('INSERT INTO plan_events(kind,actor,content,created_utc) VALUES (?,?,?,?)',
                        (kind, actor, questions.canonical(content), now())).lastrowid


def _context(conn):
    _tables(conn)
    q = questions._state(questions._rows(conn))
    approval = q['approved']['content'] if q['approved'] else None
    row = conn.execute('SELECT * FROM protocol ORDER BY version DESC LIMIT 1').fetchone()
    doc = json.loads(row['content']) if row else {}
    criteria = dict(conn.execute('SELECT * FROM criteria ORDER BY version DESC LIMIT 1').fetchone())
    return q, approval, row, doc, criteria


def _section_hash(section, doc, criteria):
    payload = {f: doc.get(f) for f in SECTIONS[section]['fields']}
    if section in ('eligibility', 'search'):
        payload['criteria_sha256'] = criteria['sha256']
    if section == 'search':
        payload['publication_period'] = doc.get('publication_period')
    if section == 'sources':
        payload['search_adapters'] = sorted(s.get('adapter', '') for s in doc.get('searches', []))
    return questions.digest(payload)


def _required(doc, section):
    def filled(path):
        return protocol._filled(protocol.get(doc, path))
    required = {
        'eligibility': ['eligibility.study_characteristics', 'eligibility.report_characteristics',
                        'publication_period.from', 'publication_period.to', 'publication_period.basis'],
        'sources': ['information_sources'], 'search': ['searches'],
        'screening': ['selection_process'], 'extraction': ['data_items', 'data_collection_process'],
        'appraisal': ['risk_of_bias'], 'synthesis': ['synthesis.criteria'],
    }[section]
    missing = [p for p in required if not filled(p)]
    if section == 'synthesis' and not (filled('synthesis.methods') or filled('synthesis.non_quantitative')):
        missing.append('synthesis.methods or synthesis.non_quantitative')
    if missing:
        raise ValueError('Complete: ' + ', '.join(missing))


def check_query(query):
    quoted=False
    escaped=False
    stack=[]
    for char in query:
        if escaped:
            escaped=False
            continue
        if char=='\\':
            escaped=True
        elif char=='"':
            quoted=not quoted
        elif not quoted:
            if char in '([':stack.append(char)
            elif char in ')]':
                if not stack or stack.pop()!=('(' if char==')' else '['):
                    raise ValueError('Unbalanced query parentheses or brackets; check source-specific syntax')
    if quoted or stack:
        raise ValueError('Unbalanced query quotes, parentheses or brackets; check source-specific syntax')


def executable(doc):
    """Validate executable fields; no provider-semantic query validation is claimed."""
    protocol.validate(doc)
    period = doc.get('publication_period', {})
    if not all(period.get(k) for k in ('from', 'to', 'basis')) or period['from'] > period['to']:
        raise ValueError('Confirm a valid publication period and its basis')
    selected = []
    for source in doc.get('information_sources', []):
        kind = source.get('kind')
        if not source.get('name', '').strip() or kind not in ('automated', 'manual-import', 'manual-search'):
            raise ValueError('Each source needs a name and automated/manual-import/manual-search capability')
        if kind == 'automated':
            if source.get('adapter') not in SOURCES:
                raise ValueError('Unsupported automated source. Document it as a manual search and import its export.')
            selected.append(source['adapter'])
        elif source.get('adapter'):
            raise ValueError('Manual sources must not specify an automated adapter')
    if len(selected) != len(set(selected)):
        raise ValueError('Automated sources must be unique')
    searches = doc.get('searches', [])
    if len(searches) > 3 or sorted(s.get('adapter','') for s in searches) != sorted(selected):
        raise ValueError('Provide exactly one search configuration for each automated source')
    if not selected:
        raise ValueError('This search workflow needs an automated source; manual-only intake is a separate path')
    from .pipeline import validate_plan
    tasks = []
    for search in searches:
        plan = {'sources': [search['adapter']], 'queries': search.get('queries'),
                'max_records_per_source': search.get('max_records_per_source'),
                'date_from': period['from'], 'date_to': period['to'],
                'year_from': int(period['from'][:4]), 'year_to': int(period['to'][:4])}
        validate_plan(plan)
        for query in plan['queries']:check_query(query)
        tasks.append(plan)
    return {'tasks': sorted(tasks, key=lambda t: t['sources'][0])}


def _strategy(plan):
    result = json.loads(questions.canonical(plan))
    for task in result['tasks']:
        task.pop('max_records_per_source')
    return questions.digest(result)


def _state(conn, *, legacy_framework_replay=False):
    q, qa, row, doc, criteria = _context(conn)
    events = _events(conn)
    revoked = {r['content']['target_sequence'] for r in events if r['kind'] == 'revocation'}
    sections = {}
    for key, spec in SECTIONS.items():
        h = _section_hash(key, doc, criteria)
        approvals = [r for r in events if r['kind'] in ('section-approval', 'section-not-applicable') and r['content']['section'] == key]
        latest = approvals[-1] if approvals else None
        valid = bool(latest and qa and latest['content']['question_approval'] == qa
                     and latest['content']['section_sha256'] == h and latest['sequence'] not in revoked)
        sections[key] = spec | {'sha256': h, 'approval': latest, 'current': valid}
    final = next((r for r in reversed(events) if r['kind'] == 'final-approval'), None)
    frameworks_current = (not qa or not q['current'] or doc.get('objectives', {}).get('framework_records', []) == q['current']['content']['draft'].get('framework_maps', []))
    if qa and q['current'] and q['current']['content']['draft'].get('framework_maps'):
        frameworks_current = frameworks_current and not any(k in doc.get('objectives', {}) for k in ('framework','elements'))
    if legacy_framework_replay:
        frameworks_current = True
    objectives_current = bool(frameworks_current and qa and q['current'] and doc.get('objectives', {}).get('question') == '\n'.join(q['current']['content']['draft']['questions']))
    final_current = bool(objectives_current and final and row and qa and all(v['current'] for v in sections.values())
        and final['content']['protocol_version'] == row['version'] and final['content']['protocol_sha256'] == row['sha256']
        and final['content']['criteria_sha256'] == criteria['sha256'] and final['content']['question_approval'] == qa
        and final['sequence'] not in revoked
        and all(final['content']['section_events'][k] == sections[k]['approval']['sequence'] for k in sections))
    origin=json.loads(conn.execute('SELECT origin FROM review').fetchone()[0])
    authorization=origin.get('authorization')
    if authorization:
        binding=authorization.get('binding',{})
        corpus_status='approved strategy · current' if (final_current and binding.get('protocol_sha256')==row['sha256'] and binding.get('question_approval')==qa and binding.get('criteria_sha256')==criteria['sha256']) else 'approved strategy · historical version'
    elif origin.get('mode')=='empty-review':
        corpus_status='No main corpus captured yet'
    elif origin.get('mode')=='import':
        corpus_status='Imported records · external search history not verified'
    else:
        corpus_status='Existing corpus · not bound to an approved protocol'
    ledger_id=conn.execute('SELECT id FROM review').fetchone()[0]
    return {'ledger_id':ledger_id,'corpus_provenance':corpus_status,'revision': events[-1]['sequence'] if events else 0, 'protocol_version': row['version'] if row else 0,
            'protocol_sha256': row['sha256'] if row else None, 'protocol': doc,
            'objectives_current': objectives_current, 'question_approval': qa, 'question_draft': q['current']['content']['draft'] if q['current'] else None,
            'criteria': criteria, 'sections': sections, 'final_approval': final, 'final_current': final_current,
            'history': events, 'source_capabilities': SOURCES, 'pilot_max': PILOT_MAX,
            'legacy_unbound': not events, 'notice': 'Actor names are trusted local labels. Old corpora are not retrospectively approved.'}


def state(database):
    with connect(database) as conn:
        return _state(conn)


def _actor(conn, body, current):
    actor = questions.text(body.get('actor'), 'Actor', 200)
    people = conn.execute('SELECT reviewers,adjudicator FROM review').fetchone()
    if actor not in json.loads(people['reviewers']) + [people['adjudicator']]:
        raise ValueError('Actor is not assigned to this review')
    if type(body.get('expected_revision')) is not int or body['expected_revision'] != current['revision']:
        raise ValueError('Protocol approval history changed. Reload before saving or approving.')
    if type(body.get('expected_protocol_version')) is not int or body['expected_protocol_version'] != current['protocol_version']:
        raise ValueError('Protocol changed. Reload before saving or approving.')
    if 'expected_question_approval' not in body or body['expected_question_approval']!=current['question_approval']:
        raise ValueError('Approved questions changed. Reload and review them before continuing.')
    if body.get('expected_criteria_sha256')!=current['criteria']['sha256']:
        raise ValueError('Screening criteria changed. Reload before continuing.')
    return actor


def eligibility_text(doc):
    value=doc.get('eligibility',{})
    study=value.get('study_characteristics','').strip()
    report=value.get('report_characteristics','').strip()
    return 'Study characteristics:\n'+study+'\n\nReport characteristics:\n'+report if study and report else None


def sync_eligibility(conn,doc,previous=None):
    """Make the protocol's eligibility the executable criteria; return what changed, or None.

    `previous` is the saved protocol before this change. A replaced criteria version that did not come from that
    protocol (initial, legacy or historical out-of-protocol text) is reported as such rather than silently dropped.
    """
    value=eligibility_text(doc)
    current=conn.execute('SELECT * FROM criteria ORDER BY version DESC LIMIT 1').fetchone()
    if not value or value==current['text']:
        return None
    digest=sha256(value.encode()).hexdigest()
    # Same wording may legitimately return after an amendment; versions stay append-only.
    conn.execute('INSERT INTO criteria VALUES (?,?,?,?)',(current['version']+1,value,digest,now()))
    change={'from_version':current['version'],'to_version':current['version']+1,'replaced_sha256':current['sha256']}
    if eligibility_text(previous or {})!=current['text']:
        change['replaced_criteria_not_from_protocol']=True
    return change


def criteria_impact(change):
    text = f" Screening criteria moved from version {change['from_version']} to {change['to_version']}; all records return to title screening."
    if change.get('replaced_criteria_not_from_protocol'):
        text += f" Version {change['from_version']} was not taken from the saved protocol and is now superseded; it stays in the criteria history."
    return text


def mutate(database, body):
    with connect(database) as conn:
        current = _state(conn)
        actor = _actor(conn, body, current)
        action = body.get('action')
        if action == 'save':
            doc = protocol.validate(body.get('protocol'))
            # Context belongs to the approved question ledger, never an AI override.
            if current['question_approval']:
                original = current['question_draft']
                doc.setdefault('objectives', {})['question'] = '\n'.join(original['questions'])
                doc = protocol.bind_question_frameworks(conn, doc)
            old = current['protocol']
            changed = [k for k in SECTIONS if {f: old.get(f) for f in SECTIONS[k]['fields']} != {f: doc.get(f) for f in SECTIONS[k]['fields']}]
            amendment = None if not current['protocol_version'] else {
                'description': questions.text(body.get('description'), 'Amendment description', 2000),
                'rationale': questions.text(body.get('rationale'), 'Amendment rationale', 2000)}
            criteria_change = sync_eligibility(conn, doc, old)
            version = protocol.save_in_connection(conn, doc, actor, expected_version=current['protocol_version'], amendment=amendment)
            content = {'protocol_version': version, 'changed_sections': changed,
                'impact': 'Changed sections and final approval need review. Eligibility/period changes also affect search approval. Earlier runs remain historical.'}
            if criteria_change:
                content['criteria_change'] = criteria_change
                content['impact'] += criteria_impact(criteria_change)
            _append(conn, 'protocol-save', actor, content)
        elif action in ('approve-section', 'not-applicable'):
            section = body.get('section')
            if section not in SECTIONS:
                raise ValueError('Unknown protocol section')
            if not current['question_approval'] or not current['protocol_version']:
                raise ValueError('Approve the current topic/questions and save a protocol before section approval')
            content = {'section': section, 'protocol_version': current['protocol_version'],
                       'section_sha256': current['sections'][section]['sha256'], 'question_approval': current['question_approval']}
            if action == 'not-applicable':
                if section not in NA_SECTIONS:
                    raise ValueError('Eligibility, sources, search and screening cannot be not applicable')
                rationale = questions.text(body.get('rationale'), 'Not-applicable rationale', 2000)
                if len(rationale) < 20:
                    raise ValueError('Explain why this section is not applicable in at least 20 characters')
                content['rationale'] = rationale
            else:
                _required(current['protocol'], section)
                if section=='eligibility' and eligibility_text(current['protocol'])!=current['criteria']['text']:
                    raise ValueError('The screening criteria differ from this eligibility section. Save the protocol to make '
                                     'its eligibility the screening criteria (the change is recorded), then approve.')
                if section in ('eligibility', 'sources', 'search'):
                    executable(current['protocol'])
            _append(conn, 'section-not-applicable' if action == 'not-applicable' else 'section-approval', actor, content)
        elif action == 'approve-final':
            if not current['objectives_current']:
                raise ValueError('Save the protocol to carry the approved questions into it.')
            if not current['question_approval'] or not all(v['current'] for v in current['sections'].values()):
                raise ValueError('Approve the current topic/questions and all seven protocol sections first')
            plan = executable(current['protocol'])
            _append(conn, 'final-approval', actor, {'protocol_version': current['protocol_version'],
                'protocol_sha256': current['protocol_sha256'], 'question_approval': current['question_approval'],
                'criteria_sha256': current['criteria']['sha256'],
                'section_events': {k:v['approval']['sequence'] for k,v in current['sections'].items()},
                'executable_plan_sha256': questions.digest(plan), 'strategy_sha256': _strategy(plan)})
        elif action == 'revoke':
            target = body.get('target_sequence')
            allowed = ('section-approval','section-not-applicable','final-approval','pilot-review')
            if not any(r['sequence'] == target and r['kind'] in allowed for r in current['history']):
                raise ValueError('Choose an approval or pilot review to revoke')
            _append(conn, 'revocation', actor, {'target_sequence': target, 'rationale': questions.text(body.get('rationale'), 'Revocation rationale', 2000)})
        elif action == 'pilot-review':
            run = next((r for r in current['history'] if r['kind']=='pilot-run' and r['content']['run_id']==body.get('run_id')), None)
            if not run or run['content']['status'] != 'complete' or not current['final_current']:
                raise ValueError('A completed pilot and current final protocol approval are required')
            # Reject review of a pilot from different questions/criteria/strategy.
            if run['content']['binding'] != _binding(current, strategy_only=True):
                raise ValueError('This pilot belongs to a different approved question or search strategy')
            decision = body.get('decision')
            if decision not in ('approve-strategy','revise'):
                raise ValueError('Approve the strategy or request revision')
            # A review rests on results that started through the governed service and still verify now.
            _, counts, _ = _verify_pilot(current['history'], run)
            _append(conn, 'pilot-review', actor, {'run_id': run['content']['run_id'], 'binding': run['content']['binding'],
                'decision': decision, 'notes': questions.text(body.get('notes'), 'Pilot review notes', 4000),
                'verified_manifest_sha256': run['content']['manifest_sha256'], 'verified_identified': counts['identified']})
        else:
            raise ValueError('Unknown protocol action')
        return _state(conn)


def _binding(current, *, strategy_only=False):
    plan = executable(current['protocol'])
    content = {'question_approval': current['question_approval'], 'criteria_sha256': current['criteria']['sha256'],
               'strategy_sha256': _strategy(plan)}
    if not strategy_only:
        content.update(protocol_version=current['protocol_version'], protocol_sha256=current['protocol_sha256'],
                       executable_plan_sha256=questions.digest(plan), final_sequence=current['final_approval']['sequence'])
    return content


def authorize(database, body, kind):
    if kind not in ('pilot', 'main'):
        raise ValueError('Unknown search kind')
    with connect(database) as conn:
        current = _state(conn)
        actor = _actor(conn, body, current)
        if not current['final_current']:
            raise ValueError('Search requires current final protocol approval, bound to the approved questions')
        binding = _binding(current)
        if kind == 'main':
            revoked = {r['content']['target_sequence'] for r in current['history'] if r['kind']=='revocation'}
            review = next((r for r in reversed(current['history']) if r['kind']=='pilot-review' and r['content']['binding']==_binding(current,strategy_only=True)), None)
            if not review or review['content']['decision']!='approve-strategy' or review['sequence'] in revoked:
                raise ValueError('Review and approve a completed pilot strategy before the main search')
        plan = executable(current['protocol'])
        if kind == 'pilot':
            limit = body.get('pilot_limit')
            if type(limit) is not int or not 1 <= limit <= PILOT_MAX:
                raise ValueError(f'Pilot limit must be 1–{PILOT_MAX} records per query/source')
            for task in plan['tasks']:
                task['max_records_per_source'] = min(limit, task['max_records_per_source'])
        ledger_id = conn.execute('SELECT id FROM review').fetchone()[0]
        content = {'run_id': uuid4().hex, 'kind':kind, 'binding':binding, 'plan':plan,
                   'review_id':ledger_id, 'pilot_review_sequence': review['sequence'] if kind=='main' else None}
        seq = _append(conn, kind+'-authorization', actor, content)
        return content | {'sequence':seq}


def check_authorization(database, authorization):
    with connect(database) as conn:
        return _check_authorization(conn,authorization)


def _check_authorization(conn, authorization):
    current = _state(conn)
    expected = next((r for r in current['history'] if r['sequence']==authorization.get('sequence')
                     and r['kind']==authorization.get('kind','')+'-authorization'), None)
    if not expected or expected['content'] != {k:v for k,v in authorization.items() if k!='sequence'}:
        raise ValueError('Search authorization does not match this review')
    if not current['final_current'] or authorization['binding'] != _binding(current):
        raise ValueError('Approved protocol changed; this search authorization is historical')
    if authorization['kind']=='main':
        review = next((r for r in current['history'] if r['sequence']==authorization['pilot_review_sequence']), None)
        revoked = {r['content']['target_sequence'] for r in current['history'] if r['kind']=='revocation'}
        latest = next((r for r in reversed(current['history']) if r['kind']=='pilot-review' and r['content']['binding']==_binding(current,strategy_only=True)),None)
        if not review or review['sequence'] in revoked or review != latest or review['content']['decision']!='approve-strategy':
            raise ValueError('Pilot strategy approval is no longer current')
    if any(r['kind']==authorization['kind']+'-run' and r['content']['run_id']==authorization['run_id'] for r in current['history']):
        raise ValueError('This search authorization has already completed; authorize a new run')
    return authorization['plan']


def record_run(database, authorization, folder, status, *, error=''):
    with connect(database) as conn:
        current = _state(conn)
        event = next((r for r in current['history'] if r['sequence']==authorization['sequence'] and r['kind']==authorization['kind']+'-authorization'), None)
        if not event:
            raise ValueError('Search authorization not found')
        manifest = Path(folder)/'manifest.json'
        _append(conn, authorization['kind']+'-run', event['actor'], {'run_id':authorization['run_id'],
            'authorization_sequence':authorization['sequence'], 'binding':{
                k:v for k,v in authorization['binding'].items() if k in ('question_approval','criteria_sha256','strategy_sha256')},
            'path':str(Path(folder).resolve()), 'manifest_sha256':sha256(manifest.read_bytes()).hexdigest() if manifest.exists() else None,
            'status':status,'error':error})


def run_authorized(database, authorization, output, progress=None):
    """Only this service produces protocol-bound runs; pilots never register corpora."""
    from .pipeline import run_plan, SessionJournal
    from .models import Record
    from .reporting import write_json, write_results
    plan = check_authorization(database, authorization)
    with connect(database) as conn:
        _tables(conn)
        events=_events(conn)
        if any(r['kind']=='run-start' and r['content']['authorization_sequence']==authorization['sequence'] for r in events):
            raise ValueError('This authorization was already started; explicitly authorize a new run')
        _append(conn,'run-start','pipeline',{'authorization_sequence':authorization['sequence'],'run_id':authorization['run_id']})
    root = Path(output)
    root.mkdir(parents=True, exist_ok=False)
    journal = SessionJournal(root, authorization)
    records, searches = [], []
    try:
        for i, task in enumerate(plan['tasks']):
            check_authorization(database, authorization)
            run = run_plan(task, root/f'source-{i+1}', progress=progress, before_request=lambda:check_authorization(database, authorization))
            _,_,manifest = verify_run(run)
            if manifest.get('search_outcome')=='partial':
                raise ValueError('A source/query failed; inspect the session before approving a pilot or registering results')
            records.extend(Record(**r) for r in json.loads((Path(run)/'retrieved.json').read_text()))
            searches.extend(manifest['searches'])
        check_authorization(database, authorization)
        folder = root/'retrieval'
        folder.mkdir()
        write_results(folder, records, identity=True)
        write_json(folder/'manifest.json', {'status':'complete','mode':'approved-'+authorization['kind'],
            'config':plan,'searches':searches,'authorization':authorization,'deduplication':'doi-or-source-id-v1',
            'files':{p.name:sha256(p.read_bytes()).hexdigest() for p in folder.iterdir()}})
        verify_run(folder)
        journal.data['status']='complete'
        journal.record('approved retrieval','info','Verified results retained; human review is still required',evidence='retrieval/manifest.json')
        return folder
    except Exception as exc:
        journal.data['status']='failed'
        journal.record('approved retrieval','error',str(exc),remedy='Review the saved source sessions, amend the strategy if needed and explicitly authorize a new run.')
        raise


def copy_history(source, destination):
    """Preserve protocol and plan ledgers during a corpus replacement."""
    with connect(source) as conn:
        _tables(conn)
        protocols = [dict(r) for r in conn.execute('SELECT * FROM protocol ORDER BY version')]
        events = _events(conn)
        criteria = [dict(r) for r in conn.execute('SELECT * FROM criteria ORDER BY version')]
    with connect(destination) as conn:
        _tables(conn)
        if conn.execute('SELECT 1 FROM protocol').fetchone() or _events(conn):
            raise ValueError('Destination already has protocol/plan history')
        first = conn.execute('SELECT sha256 FROM criteria WHERE version=1').fetchone()[0]
        if first != criteria[0]['sha256']:
            raise ValueError('Destination initial criteria must match original criteria')
        for r in criteria[1:]:
            conn.execute('INSERT INTO criteria VALUES (?,?,?,?)', (r['version'],r['text'],r['sha256'],r['created_utc']))
        for r in protocols:
            conn.execute('INSERT INTO protocol VALUES (?,?,?,?,?,?,?,?)', tuple(r[k] for k in ('version','criteria_version','content','sha256','actor','amendment','changed_sections','created_utc')))
        for r in events:
            conn.execute('INSERT INTO plan_events VALUES (?,?,?,?,?)', (r['sequence'],r['kind'],r['actor'],questions.canonical(r['content']),r['created_utc']))


def _verify_pilot(history, row):
    """Re-check a recorded pilot: governed start, unchanged manifest and artifacts bound to this run."""
    content = row['content']
    if not any(r['kind'] == 'run-start' and r['content'].get('authorization_sequence') == content.get('authorization_sequence')
               and r['content'].get('run_id') == content['run_id'] for r in history):
        raise ValueError('This pilot did not start through the governed retrieval service')
    path = Path(content['path'])
    try:
        if sha256((path/'manifest.json').read_bytes()).hexdigest() != content['manifest_sha256']:
            raise ValueError('Pilot manifest changed; inspect original session artifacts')
        records, counts, manifest = verify_run(path)
    except OSError:
        raise ValueError('Pilot results are no longer available at the recorded location') from None
    authorization = manifest.get('authorization') or {}
    if (manifest.get('mode') != 'approved-pilot' or authorization.get('run_id') != content['run_id']
            or authorization.get('sequence') != content.get('authorization_sequence')):
        raise ValueError('Pilot results do not belong to this pilot authorization')
    return records, counts, manifest


def inspect_pilots(database, run_id=None):
    """Read only recorded pilot results, checking the saved manifest and artifacts.

    A run that no longer verifies is reported as unavailable instead of failing the whole listing.
    """
    current=state(database)
    previews=[]
    for row in current['history']:
        if row['kind']!='pilot-run' or (run_id is not None and row['content']['run_id']!=run_id):continue
        value=dict(row['content'])
        if value['status']=='complete':
            try:
                records,counts,manifest=_verify_pilot(current['history'],row)
            except ValueError as exc:
                value.update(recorded_status='complete',status='unavailable',
                             error=f'{exc}. This pilot cannot be reviewed; authorize a new pilot if needed.')
            else:
                value.update(counts=counts,sample=records[:12],searches=manifest['searches'],config=manifest['config'])
        previews.append(value)
    if run_id is not None and not previews:raise ValueError('Pilot run is not recorded in this review')
    return previews
