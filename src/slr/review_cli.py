"""Commands for local, human-controlled screening and eligibility."""
import argparse
from hashlib import sha256
from html import escape
import json
from pathlib import Path
import sqlite3
import textwrap

from . import protocol, screening
from .models import Record
from .reporting import export_records, write_csv, write_json


def agreement_line(stage, stats):
    if not stats['pairs']:
        return f'{stage} agreement: no paired decisions'
    kappa = 'undefined' if stats['cohen_kappa'] is None else f"{stats['cohen_kappa']:.2f}"
    return (f"{stage} agreement (n={stats['pairs']}): observed {stats['observed_agreement']:.1%}, "
            f"Cohen's kappa {kappa}, PABAK {stats['pabak']:.2f}")


def flow_svg(counts, agreement=None):
    """Original database-only PRISMA-style rendering; no external assets."""
    c = counts
    reasons = [f'{reason}: {count}' for reason, count in sorted(c['exclusion_reasons'].items())]
    blocks = [
        ['Records identified: ' + str(c['identified'])] + [f'{source}: {count}' for source, count in sorted(c.get('identified_by_source', {}).items())] + ['Duplicates removed: ' + str(c['duplicates_removed'])],
        [f"Records to screen: {c['records_to_screen']}", f"Screening resolved: {c['records_screened']}",
         f"Excluded: {c['records_excluded']}", f"Pending: {c['title_pending']}; conflicts: {c['title_conflicts']}"],
        [f"Reports sought for retrieval: {c['reports_sought']}", f"Not retrieved: {c['reports_not_retrieved']}; retrieval pending: {c['retrieval_pending']}"],
        [f"Reports assessed for eligibility: {c['reports_assessed']}", f"Pending: {c['eligibility_pending']}; conflicts: {c['eligibility_conflicts']}",
         f"Reports excluded: {c['reports_excluded']}"] + reasons,
        [f"Reports included: {c['reports_included']}", f"Studies included: {c['studies_included']}",
         f"Included reports awaiting study links: {c['included_reports_without_study']}"]]
    parts, y = [], 80
    for index, block in enumerate(blocks):
        lines = [line for value in block for line in textwrap.wrap(value, width=82)]
        height = 24 * len(lines) + 24
        if index:
            parts.append(f'<path d="M 400 {y - 30} V {y}" stroke="#334155" marker-end="url(#arrow)"/>')
        parts.append(f'<rect x="35" y="{y}" width="730" height="{height}" rx="8" fill="#eff6ff" stroke="#334155"/>')
        for i, line in enumerate(lines):
            parts.append(f'<text x="55" y="{y + 28 + i * 24}">{escape(line)}</text>')
        y += height + 30
    if agreement:
        for label, stage in (('Title/abstract', 'title'), ('Full-text', 'fulltext')):
            parts.append(f'<text x="35" y="{y + 5}" font-size="13">{escape(agreement_line(label, agreement[stage]))}</text>')
            y += 20
    parts.append(f'<text x="35" y="{y + 5}" font-size="13">Database/register searches only; each retained record represents one report.</text>')
    parts.append(f'<text x="35" y="{y + 25}" font-size="13">Based on PRISMA 2020: Page et al. BMJ 2021;372:n71. doi:10.1136/bmj.n71</text>')
    status = 'Complete' if c['complete'] else 'INCOMPLETE — pending decisions, conflicts, or study links remain'
    return f'<svg xmlns="http://www.w3.org/2000/svg" width="800" height="{y + 55}" viewBox="0 0 800 {y + 55}" role="img" aria-label="Study selection flow"><title>Study selection flow</title><defs><marker id="arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8" fill="#334155"/></marker></defs><rect width="100%" height="100%" fill="white"/><g font-family="sans-serif" font-size="16" fill="#0f172a"><text x="35" y="28">PRISMA 2020-style study selection</text><text x="35" y="54" font-size="14">{escape(status)}</text>{"".join(parts)}</g></svg>\n'


def export_review(database, output):
    data = screening.snapshot(database)
    folder = Path(output)
    folder.mkdir(parents=True, exist_ok=False)
    write_json(folder / 'review.json', data)
    write_json(folder / 'prisma.json', data['prisma'])
    write_json(folder / 'agreement.json', {**data['agreement'], 'pilot': data['pilot']})
    protocol_state = protocol.state(database)
    if protocol_state['version']:
        write_json(folder / 'protocol.json', protocol_state)
    (folder / 'prisma.svg').write_text(flow_svg(data['prisma'], data['agreement']), encoding='utf-8')
    fields = ['record_id', 'article_title', 'title_decision', 'title_reason', 'retrieval', 'fulltext', 'fulltext_reason', 'study_id']
    write_csv(folder / 'screening.csv', fields, [{**{k: row[k] for k in fields if k not in ('article_title', 'title_decision')},
                                                  'article_title': row['metadata']['title'], 'title_decision': row['title']} for row in data['records']])
    included = [Record(**r['metadata']) for r in data['records'] if r['fulltext'] == 'include']
    export_records(folder, included)
    write_json(folder / 'manifest.json', {'review_id': data['review_id'], 'criteria_version': data['criteria_version'],
        'created_utc': screening.now(), 'complete': data['prisma']['complete'],
        'files': {p.name: sha256(p.read_bytes()).hexdigest() for p in sorted(folder.iterdir())}})
    return data['prisma']


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    init = sub.add_parser('init', help='Initialize a new ledger from a completed retrieval run')
    init.add_argument('--run', required=True)
    init.add_argument('--name', required=True)
    init.add_argument('--reviewers', nargs=2, required=True)
    init.add_argument('--adjudicator', required=True)
    init.add_argument('--criteria', required=True, help='UTF-8 inclusion/exclusion criteria file')
    criteria = sub.add_parser('criteria', help='Append revised criteria; all records require a new review')
    criteria.add_argument('--file', required=True)
    for command in ('decide', 'adjudicate'):
        item = sub.add_parser(command)
        item.add_argument('--record', required=True)
        item.add_argument('--actor', required=True)
        item.add_argument('--stage', choices=['title', 'fulltext'], required=True)
        item.add_argument('--decision', choices=['include', 'exclude'], required=True)
        item.add_argument('--reason', default='')
    retrieval = sub.add_parser('retrieve')
    retrieval.add_argument('--record', required=True)
    retrieval.add_argument('--actor', required=True)
    retrieval.add_argument('--status', choices=['retrieved', 'not_retrieved'], required=True)
    retrieval.add_argument('--reason', default='')
    study = sub.add_parser('link-study')
    study.add_argument('--record', required=True)
    study.add_argument('--actor', required=True)
    study.add_argument('--study', required=True)
    pilot = sub.add_parser('pilot', help='Adjudicator draws a reproducible calibration sample both reviewers screen first')
    pilot.add_argument('--actor', required=True)
    pilot.add_argument('--size', required=True, type=int)
    pilot.add_argument('--seed', type=int, help='Random seed; defaults to one derived from the review ID and criteria version')
    sub.add_parser('agreement', help="Inter-rater agreement (Cohen's kappa, PABAK) and pilot round status")
    queue = sub.add_parser('queue', help='Show a reviewer queue without the other reviewer decisions')
    queue.add_argument('--reviewer', required=True)
    sub.add_parser('status', help='Administrative status including conflicts and counts')
    export = sub.add_parser('export')
    export.add_argument('--output', required=True)
    for command, item in sub.choices.items():
        item.add_argument('--db', required=True)
        if command in ('decide', 'adjudicate', 'retrieve', 'link-study', 'criteria', 'pilot'):
            item.add_argument('--version', required=True, type=int, help='Expected current criteria version; stale writes are rejected')
    args = parser.parse_args(argv)
    try:
        if args.command == 'init':
            result = {'records': screening.initialize(args.db, args.run, args.name, args.reviewers, args.adjudicator, Path(args.criteria).read_text(encoding='utf-8'))}
        elif args.command == 'criteria':
            result = {'criteria_version': screening.revise_criteria(args.db, Path(args.file).read_text(encoding='utf-8'), expected_version=args.version)}
        elif args.command in ('decide', 'adjudicate'):
            screening.decide(args.db, args.record, args.actor, args.stage, args.decision, args.reason,
                             adjudicate=args.command == 'adjudicate', expected_version=args.version)
            result = {'saved': True}
        elif args.command == 'retrieve':
            screening.record_retrieval(args.db, args.record, args.actor, args.status, args.reason, expected_version=args.version)
            result = {'saved': True}
        elif args.command == 'link-study':
            screening.link_study(args.db, args.record, args.actor, args.study, expected_version=args.version)
            result = {'saved': True}
        elif args.command == 'pilot':
            result = {'pilot_records': screening.start_pilot(args.db, args.actor, args.size, seed=args.seed, expected_version=args.version)}
        elif args.command == 'agreement':
            data = screening.snapshot(args.db)
            result = {**data['agreement'], 'pilot': data['pilot']}
        elif args.command == 'queue':
            result = screening.snapshot(args.db, reviewer=args.reviewer)
        elif args.command == 'status':
            data = screening.snapshot(args.db)
            result = {k: data[k] for k in ('review_id', 'name', 'criteria_version', 'criteria', 'prisma', 'agreement', 'pilot', 'records')}
        else:
            result = export_review(args.db, args.output)
    except (ValueError, OSError, TypeError, KeyError, sqlite3.DatabaseError) as exc:
        parser.exit(1, f'slr review: {exc}\n')
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0
