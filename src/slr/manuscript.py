"""Deterministic screening methods drafts from a frozen local ledger."""
import argparse
from contextlib import closing
from hashlib import sha256
from html import escape
import json
from pathlib import Path
import sqlite3
import tempfile

from . import protocol, screening
from .review_cli import agreement_line, flow_svg


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')


def digest(value):
    return sha256(canonical(value)).hexdigest()


def capture(database, run=None):
    """Read through SQLite backup, including committed WAL data; never write the source."""
    path = Path(database).resolve(strict=True)
    with tempfile.TemporaryDirectory(prefix='litatlas-report-') as temporary:
        frozen = Path(temporary) / 'review.sqlite'
        with closing(sqlite3.connect(path.as_uri() + '?mode=ro', uri=True)) as source:
            with closing(sqlite3.connect(frozen)) as target:
                source.backup(target)
        with closing(sqlite3.connect(frozen)) as connection:
            for text, expected in connection.execute('SELECT text, sha256 FROM criteria'):
                if sha256(text.encode('utf-8')).hexdigest() != expected:
                    raise ValueError('Criteria content does not match its recorded hash')
            has_protocol = connection.execute("SELECT 1 FROM sqlite_master WHERE name='protocol'").fetchone()
            if has_protocol:
                for content, expected in connection.execute('SELECT content, sha256 FROM protocol'):
                    if digest(json.loads(content)) != expected:
                        raise ValueError('Protocol content does not match its recorded hash')
        review = screening.snapshot(frozen)
        planned = protocol.state(frozen)
    if sha256(review['criteria']['text'].encode('utf-8')).hexdigest() != review['criteria']['sha256']:
        raise ValueError('Criteria content does not match its recorded hash')
    verification = 'embedded manifest only; retrieval files were not reverified'
    if run is not None:
        _, _, manifest = screening.verify_run(run)
        if manifest != review['origin']:
            raise ValueError('Retrieval run does not match the screening ledger origin')
        verification = 'retrieval files reverified against the embedded manifest'
    return {'schema': 'litatlas-methods-v1', 'screening': review, 'protocol': planned,
            'retrieval_verification': verification}


def render(inputs):
    if inputs.get('schema') != 'litatlas-methods-v1':
        raise ValueError('Unsupported report snapshot schema')
    review = inputs['screening']
    counts = review['prisma']
    claims = []

    def claim(text, pointer, value):
        identifier = f'M{len(claims) + 1:03d}'
        claims.append({'id': identifier, 'text': text, 'pointer': pointer, 'value_sha256': digest(value)})
        safe = text.replace('\\', '\\\\').replace('<', '&lt;').replace('>', '&gt;').replace('\n', ' ').replace('\r', ' ')
        for character in ('*', '_', '[', ']', '`'):
            safe = safe.replace(character, '\\' + character)
        return f'{safe} [{identifier}]'

    mode = review['origin'].get('mode', 'unknown')
    source_text = {'offline-fixture': 'The input was an offline fixture; no database search was executed by this run.',
                   'import': 'The input was an imported reference library; this run does not establish how its search was conducted.'}.get(
                       mode, f'The recorded retrieval mode was {mode}. Search logs and limits require review before claiming comprehensive coverage.')
    lines = ['# Screening methods draft', '',
             '**Human review required.** This draft describes recorded software state; it does not establish methodological quality or checklist compliance.', '',
             claim('Screening is recorded as complete.' if counts['complete'] else 'Screening is incomplete; the counts below are provisional.', '/screening/prisma/complete', counts['complete']), '',
             claim(source_text, '/screening/origin/mode', mode), '',
             claim(f"The ledger identifies {counts['identified']} records and removes {counts['duplicates_removed']} duplicates, leaving {counts['records_to_screen']} records to screen.", '/screening/prisma', counts), '',
             claim(f"Recorded inclusion comprises {counts['reports_included']} reports linked to {counts['studies_included']} studies; {counts['included_reports_without_study']} included reports lack a study link.", '/screening/prisma', counts), '',
             claim(f"The current eligibility criteria are version {review['criteria_version']}. Recorded criteria versions: {len(review['criteria_history'])}.", '/screening/criteria_history', review['criteria_history']), '',
             'Reviewer names are local labels. Paired votes do not authenticate independent people.', '']
    for stage in ('title', 'fulltext'):
        stats = review['agreement'][stage]
        lines += [claim(agreement_line(stage, stats) + (f"; {stats['kappa_undefined_reason']}" if stats['pairs'] and stats.get('kappa_undefined_reason') else ''), f'/screening/agreement/{stage}', stats), '']
    planned = inputs['protocol']
    lines += [claim(f"The ledger contains {planned['version']} saved protocol versions. Protocol declarations describe plans and require comparison with observed practice.", '/protocol/history', planned['history']), '',
              'Retrieval verification: ' + inputs['retrieval_verification'] + '.', '',
              '## Human completion', '',
              'Supply the rationale, objectives, full executed search strategies and search dates, selection procedures, deviations, extraction methods, risk-of-bias assessments, synthesis methods, limitations, funding and registration verification. No evidence findings or AI-written synthesis are generated by this command.', '']
    coverage = [
        {'item': '7', 'topic': 'Search strategy', 'status': 'manual review required', 'pointer': '/screening/origin'},
        {'item': '8', 'topic': 'Selection process', 'status': 'partial ledger evidence', 'pointer': '/screening/events'},
        {'item': '16a', 'topic': 'Study selection', 'status': 'provisional' if not counts['complete'] else 'counts available', 'pointer': '/screening/prisma'},
        {'item': '24c', 'topic': 'Protocol amendments', 'status': 'manual comparison required', 'pointer': '/protocol/history'},
    ]
    provenance = {'schema': inputs['schema'], 'inputs_sha256': digest(inputs), 'claims': claims}
    return {'methods.md': '\n'.join(lines),
            'report-inputs.json': json.dumps(inputs, ensure_ascii=False, indent=2, sort_keys=True) + '\n',
            'report-provenance.json': json.dumps(provenance, ensure_ascii=False, indent=2, sort_keys=True) + '\n',
            'prisma-coverage.json': json.dumps({'notice': 'Selected PRISMA 2020 items only; availability is not compliance. All other items require manual completion.', 'source': 'https://www.prisma-statement.org/prisma-2020', 'items': coverage}, indent=2) + '\n',
            'prisma.svg': flow_svg(counts, review['agreement']),
            'report.html': '<!doctype html><html lang="en"><meta charset="utf-8"><title>Screening methods draft</title><body><pre style="white-space:pre-wrap">' + escape('\n'.join(lines)) + '</pre><a href="prisma.svg">Selection flow</a></body></html>\n'}


def export(inputs, output):
    files = render(inputs)
    destination = Path(output)
    # Reserve a fresh directory; remove only our own files on failure.
    destination.mkdir(parents=True, exist_ok=False)
    written = []
    try:
        for name, content in files.items():
            path = destination / name
            written.append(path)
            path.write_bytes(content.encode('utf-8'))
        manifest = {'status': 'complete', 'review_complete': inputs['screening']['prisma']['complete'],
                    'files': {name: sha256(content.encode('utf-8')).hexdigest() for name, content in files.items()}}
        path = destination / 'manifest.json'
        written.append(path)
        path.write_bytes((json.dumps(manifest, indent=2, sort_keys=True) + '\n').encode('utf-8'))
    except Exception:
        for path in written:
            path.unlink(missing_ok=True)
        destination.rmdir()
        raise
    return destination


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--db', help='Screening SQLite ledger (read only)')
    group.add_argument('--snapshot', help='Previously exported report-inputs.json with companion provenance')
    parser.add_argument('--run', help='Optionally reverify the original retrieval directory')
    parser.add_argument('--output', required=True, help='New private output directory')
    args = parser.parse_args(argv)
    try:
        if args.snapshot:
            if args.run:
                raise ValueError('--run requires --db')
            path = Path(args.snapshot)
            inputs = json.loads(path.read_text(encoding='utf-8'))
            provenance = json.loads((path.parent / 'report-provenance.json').read_text(encoding='utf-8'))
            if digest(inputs) != provenance['inputs_sha256']:
                raise ValueError('Report snapshot hash mismatch')
        else:
            inputs = capture(args.db, args.run)
        folder = export(inputs, args.output)
    except (ValueError, OSError, sqlite3.Error, KeyError, TypeError) as exc:
        parser.exit(1, f'slr report: {exc}\n')
    print(f'Methods draft written to {folder}')
    return 0
