"""Read-only summaries of recorded AI assistance; no prompts or paper text exported."""
from contextlib import closing
import json
from pathlib import Path
import sqlite3


def _open(path):
    conn = sqlite3.connect(Path(path).resolve(strict=True).as_uri() + '?mode=ro', uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def capture(database, evidence_database=None):
    stages = []
    with closing(_open(database)) as conn:
        review_id = conn.execute('SELECT id FROM review').fetchone()[0]
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        for stage, table, request, proposal, decision in [('questions','question_events','request','proposal','decision'),
                ('protocol','plan_events','ai-request','ai-proposal','ai-decision')]:
            rows = [dict(r) | {'content': json.loads(r['content'])} for r in conn.execute(f'SELECT * FROM {table} ORDER BY sequence')] if table in tables else []
            requests = [r for r in rows if r['kind'] == request]
            proposals = [r for r in rows if r['kind'] == proposal]
            decisions = [r for r in rows if r['kind'] == decision]
            models = []
            for r in requests:
                c = r['content']; packet = c['packet']
                envelope = next((p['content']['envelope'] for p in proposals if p['content']['envelope']['request_id'] == packet['request_id']), {})
                models.append({'request_id': packet['request_id'], 'provider': c.get('provider'),
                    'requested_model': c.get('model'), 'returned_model': envelope.get('model'),
                    'model_digest': envelope.get('model_digest'), 'prompt_version': packet['packet'].get('prompt_version'),
                    'request_sha256': packet.get('request_sha256'), 'created_utc': r['created_utc']})
            counts = {k: sum(d['content'].get('decision') == k for d in decisions) for k in ('accept','edit','reject')}
            stages.append({'stage': stage, 'coverage': 'recorded ledger only' if table in tables else 'history unavailable',
                'requests_prepared': len(requests), 'responses_recorded': len(proposals),
                'failures_recorded': sum(r['kind'] in ('failure','ai-failure') for r in rows),
                'proposals': sum(len(r['content']['envelope']['output']['items']) for r in proposals),
                'human_decisions': counts, 'models': models})
    if evidence_database is not None:
        with closing(_open(evidence_database)) as conn:
            scope = json.loads(conn.execute('SELECT scope FROM settings').fetchone()[0])
            if scope['snapshot']['review_id'] != review_id:
                raise ValueError('Evidence ledger belongs to a different review')
            batches = [dict(r) | {'producer': json.loads(r['producer'])} for r in conn.execute('SELECT * FROM batches')]
            for task, label in [('extract','extraction'), ('appraise','appraisal')]:
                ai = [b for b in batches if b['producer'].get('method') == 'ai']
                ids = {b['id'] for b in ai}
                proposals = [dict(r) for r in conn.execute('SELECT id,batch_id FROM proposals WHERE task=?',(task,)) if r['batch_id'] in ids]
                pids = {p['id'] for p in proposals}
                decisions = [dict(r) for r in conn.execute('SELECT proposal_id,decision FROM reviews ORDER BY id') if r['proposal_id'] in pids]
                used = {p['batch_id'] for p in proposals}
                stages.append({'stage': label, 'coverage': 'recorded evidence ledger only', 'proposals':len(proposals),
                    'responses_recorded':len(used), 'requests_prepared':conn.execute('SELECT COUNT(*) FROM requests WHERE task=?',(task,)).fetchone()[0],
                    'human_decisions':{k:sum(d['decision']==k for d in decisions) for k in ('approve','reject')},
                    'models':[{k:b['producer'].get(k) for k in ('provider','model','model_digest','prompt_version','request_sha256')} for b in ai if b['id'] in used]})
    else:
        stages.extend({'stage': stage, 'coverage': 'evidence ledger not supplied; usage unknown'} for stage in ('extraction','appraisal'))
    stages.append({'stage':'analysis-recommendation experiments','coverage':'Separate experiment artifacts are not linked to this review; usage unknown'})
    return {'schema':'litatlas-ai-disclosure-v1','stages':stages,
        'notice':'Researcher verification required. Prepared requests do not prove model execution. Counts describe recorded events, not independent people or complete historical AI use. Missing model digests/prompt versions are unavailable; no identities are inferred.'}


def markdown(value):
    lines = ['## Recorded AI assistance', '', value['notice'], '']
    for s in value['stages']:
        lines.append(f"- {s['stage']}: {s['coverage']}." + (f" Prepared requests: {s['requests_prepared']}; recorded responses: {s['responses_recorded']}; proposals: {s['proposals']}; human decision events: {json.dumps(s['human_decisions'], sort_keys=True)}." if 'requests_prepared' in s else ''))
    lines += ['', 'See ai-disclosure.json for recorded model identities and prompt versions. Verify this draft and describe any AI use outside these ledgers.', '']
    return '\n'.join(lines)
