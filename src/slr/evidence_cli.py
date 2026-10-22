"""Prepare, inspect and review source-grounded evidence without changing screening."""
import argparse
from hashlib import sha256
from html import escape
import json
from pathlib import Path
import sqlite3

from . import __version__
from . import evidence as e
from .reporting import write_csv, write_json, export_records
from .models import Record


def md(value):
    value = str(value).replace('\r', ' ').replace('\n', ' ')
    for char in ('\\', '*', '_', '[', ']', '(', ')', '#', '!', '<', '>', '`'):
        value = value.replace(char, '\\' + char)
    return value


def export_evidence(database, output):
    state = e.snapshot(database)
    folder = Path(output)
    folder.mkdir(parents=True, exist_ok=False)
    manifest = {'status': 'running', 'created_utc': e.now(), 'version': __version__}
    write_json(folder / 'manifest.json', manifest)
    try:
        write_json(folder / 'evidence.json', state)
        write_json(folder / 'coverage.json', state['coverage'])
        write_json(folder / 'framework.json', state['framework'])
        export_records(folder, [Record(**r['metadata']) for r in state['records']])
        approved = [p for p in state['proposals'] if p['state'] == 'approve' and not p['checks']['flags']]
        sources = {s['id']: s for s in state['sources']}
        records = {r['id']: r for r in state['records']}
        batches = {b['id']: b for b in state['batches']}
        rows = []
        for p in approved:
            record = records.get(p['record_id'], {})
            rows.append({'evidence_id': p['id'], 'record_id': p['record_id'], 'study_id': record.get('study_id'),
                'task': p['task'], 'key': p['item']['key'], 'status': p['item']['status'], 'value': p['item']['value'],
                'uncertainty': p['item']['uncertainty'], 'rationale': p['item']['rationale'],
                'anchors': json.dumps(p['checks']['anchors'], ensure_ascii=False),
                'evidence_ids': json.dumps(p['item']['evidence_ids']),
                'producer': json.dumps(batches[p['batch_id']]['producer'], ensure_ascii=False),
                'reviewer': p['reviews'][-1]['actor'], 'review_rationale': p['reviews'][-1]['rationale']})
        fields = ['evidence_id', 'record_id', 'study_id', 'task', 'key', 'status', 'value', 'uncertainty', 'rationale', 'anchors', 'evidence_ids', 'producer', 'reviewer', 'review_rationale']
        write_csv(folder / 'evidence.csv', fields, rows)
        label = 'COMPLETE' if state['complete'] else 'INCOMPLETE / HISTORICAL' if not state['scope_current'] else 'INCOMPLETE'
        lines = ['# Evidence synthesis working draft', '', f'Status: {label}. This is a structured digest of human-approved items, not an automatic scientific synthesis.',
                 f"Screening review {state['scope']['snapshot']['review_id']}, criteria version {state['scope']['snapshot']['criteria_version']}.",
                 f"Extraction framework: {state['framework']['id']}; appraisal framework: {state['framework']['appraisal']['id']}.",
                 'Only the supplied sources were checked. Not reported means not reported in those sources; it is not proof of absence in the full paper.', '']
        for record in state['records']:
            lines += [f"## {record['id']} — {md(record['metadata'].get('title', ''))}", f"Study: {record['study_id']}", '']
            lines += [f"Bibliographic identity: DOI {md(record['metadata'].get('doi') or 'unknown')}; {md(record['metadata'].get('source', ''))} / {md(record['metadata'].get('source_id', ''))}.", '']
            for p in approved:
                if p['record_id'] != record['id']:
                    continue
                item = p['item']
                value = item['value'] if item['status'] == 'reported' else 'Not reported in supplied sources'
                lines += [f"- {p['task']}/{item['key']}: {md(value)} [E{p['id']}] (uncertainty: {item['uncertainty']})"]
                for anchor in p['checks']['anchors']:
                    source = sources[anchor['source_id']]
                    lines += [f"  - Source {source['id']} ({source['kind']}), supplied page {anchor['page']}, characters {anchor['start']}–{anchor['end']}: {md(anchor['quote'])}"]
            missing = [r for r in state['coverage'] if r['record_id'] == record['id'] and r['proposal_id'] is None]
            if missing:
                lines += ['- Unreviewed fields/domains: ' + ', '.join(r['task'] + '/' + r['key'] for r in missing)]
            lines.append('')
        hypotheses = [p for p in approved if p['task'] == 'gaps']
        lines += ['## Hypotheses requiring independent validation', '']
        for p in hypotheses:
            lines += [f"- Hypothesis E{p['id']}: {md(p['item']['value'])} (based on approved evidence IDs {p['item']['evidence_ids']}; uncertainty: {p['item']['uncertainty']})"]
        if not hypotheses:
            lines.append('No human-reviewed hypotheses.')
        lines += ['', '## Review coverage', f"Pending proposals: {state['pending']}; active flagged proposals: {state['flagged']}; screening scope current: {state['scope_current']}.",
                  'Proposal IDs and source quotations are traceable in evidence.json. Text matching checks quote occurrence, not semantic entailment; reviewer confirmation supplies the latter.', '']
        draft = '\n'.join(lines)
        (folder / 'synthesis.md').write_text(draft, encoding='utf-8')
        cards = evidence_cards(approved, sources)
        html = '<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Evidence review</title><style>body{font:16px/1.6 system-ui;max-width:1100px;margin:40px auto;padding:0 20px}pre{white-space:pre-wrap;overflow-wrap:anywhere}</style><h1>Evidence review</h1><p><a href="evidence.csv">Approved evidence table</a> · <a href="evidence.json">Complete history</a> · <a href="coverage.json">Field coverage</a></p><pre>' + escape(draft) + '</pre><h2>Approved items and source links</h2>' + cards + '</html>'
        (folder / 'report.html').write_text(html, encoding='utf-8')
        for source in state['sources']:
            (folder / f"source-{source['id']}.txt").write_text('\f'.join(source['pages']), encoding='utf-8')
        manifest.update(status='complete', evidence_complete=state['complete'], scope_current=state['scope_current'],
                        approved_items=len(approved), pending=state['pending'], flagged=state['flagged'],
                        files={p.name: sha256(p.read_bytes()).hexdigest() for p in sorted(folder.iterdir()) if p.name != 'manifest.json'})
        write_json(folder / 'manifest.json', manifest)
    except Exception:
        manifest['status'] = 'failed'
        write_json(folder / 'manifest.json', manifest)
        raise
    return {'output': str(folder), 'complete': state['complete'], 'approved_items': len(approved), 'pending': state['pending'], 'flagged': state['flagged']}


def evidence_cards(approved, sources):
    cards = []
    for proposal in approved:
        item = proposal['item']
        value = item['value'] if item['status'] == 'reported' else 'Not reported in supplied sources'
        title = 'Hypothesis requiring independent validation' if proposal['task'] == 'gaps' else proposal['task'] + '/' + item['key']
        cards.append(f'<article id="E{proposal["id"]}" style="border-top:1px solid #cbd5e1;padding:16px 0"><h3>E{proposal["id"]}: {escape(title)}</h3><p>{escape(value)}</p>')
        cards.append('<p>Uncertainty: ' + escape(item['uncertainty']) + '. Reviewer: ' + escape(proposal['reviews'][-1]['actor']) + '.</p>')
        for anchor in proposal['checks']['anchors']:
            source = sources[anchor['source_id']]
            cards.append(f'<p><a href="source-{source["id"]}.txt">{escape(source["label"])}</a> ({source["kind"]}), supplied page {anchor["page"]}, characters {anchor["start"]}–{anchor["end"]}.</p><blockquote>{escape(anchor["quote"])}</blockquote>')
        if item['evidence_ids']:
            cards.append('<p>Supporting evidence: ' + ', '.join(f'<a href="#E{i}">E{i}</a>' for i in item['evidence_ids']) + '</p>')
        cards.append('</article>')
    return ''.join(cards)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    init = sub.add_parser('init')
    init.add_argument('--screening-db', required=True)
    init.add_argument('--framework', required=True)
    source = sub.add_parser('add-source')
    source.add_argument('--record', required=True)
    source.add_argument('--file', required=True)
    source.add_argument('--kind', choices=['fulltext', 'abstract', 'excerpt'], required=True)
    source.add_argument('--label', required=True)
    prepare = sub.add_parser('prepare')
    prepare.add_argument('--task', choices=e.TASKS, required=True)
    prepare.add_argument('--record')
    prepare.add_argument('--max-chars', type=int, default=60000)
    manual = sub.add_parser('propose')
    manual.add_argument('--task', choices=e.TASKS, required=True)
    manual.add_argument('--record')
    manual.add_argument('--actor', required=True)
    manual.add_argument('--file', required=True)
    imported = sub.add_parser('import-ai')
    imported.add_argument('--file', required=True)
    ai = sub.add_parser('run-ai', help='Send a saved prompt/source packet to OpenAI; requires OPENAI_API_KEY')
    ai.add_argument('--request', required=True, type=int)
    ai.add_argument('--model', required=True)
    ai.add_argument('--max-output-tokens', type=int, default=4096)
    ai.add_argument('--output', required=True)
    review = sub.add_parser('review')
    review.add_argument('--proposal', type=int, required=True)
    review.add_argument('--actor', required=True)
    review.add_argument('--decision', choices=['approve', 'reject'], required=True)
    review.add_argument('--rationale', required=True)
    review.add_argument('--revision', type=int, required=True)
    review.add_argument('--support-confirmed', action='store_true')
    sub.add_parser('status')
    export = sub.add_parser('export')
    export.add_argument('--output', required=True)
    for command in sub.choices.values():
        command.add_argument('--db', required=True)
    args = parser.parse_args(argv)
    def load(path):
        return json.loads(Path(path).read_text(encoding='utf-8'))
    try:
        if args.command == 'init':
            result = {'included_reports': e.initialize(args.db, args.screening_db, load(args.framework))}
        elif args.command == 'add-source':
            result = {'source_id': e.add_source(args.db, args.record, args.file, args.kind, args.label)}
        elif args.command == 'prepare':
            result = e.prepare(args.db, args.task, args.record, max_chars=args.max_chars)
        elif args.command == 'propose':
            result = {'proposal_ids': e.submit(args.db, args.task, args.record, load(args.file), {'method': 'manual', 'actor': args.actor})}
        elif args.command == 'import-ai':
            result = {'proposal_ids': e.import_ai(args.db, load(args.file))}
        elif args.command == 'run-ai':
            from .evidence_ai import run_openai
            envelope = run_openai(args.db, args.request, args.model, args.output, max_output_tokens=args.max_output_tokens)
            result = {'response_file': str(Path(args.output) / 'response.json'), 'response_id': envelope.get('response_id'),
                      'imported': False, 'next': 'Inspect the saved output, then use import-ai; all imported items remain pending human review'}
        elif args.command == 'review':
            result = {'revision': e.review(args.db, args.proposal, args.actor, args.decision, args.rationale,
                support_confirmed=args.support_confirmed, revision=args.revision)}
        elif args.command == 'export':
            result = export_evidence(args.db, args.output)
        else:
            result = e.snapshot(args.db)
    except (ValueError, TypeError, OSError, KeyError, sqlite3.DatabaseError) as exc:
        parser.exit(1, f'slr evidence: {exc}\n')
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0
