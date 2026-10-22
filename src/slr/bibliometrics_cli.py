"""Export reproducible bibliometric networks, coverage and optional figures."""
import argparse
from datetime import datetime, timezone
from hashlib import sha256
from html import escape
import json
from pathlib import Path
import sqlite3

from . import __version__
from .bibliometrics import descriptive_summary, networks
from .models import Record, deduplicate
from .reporting import write_csv, write_json
from .screening import snapshot, verify_run

NOTICES = [
    'Results describe the captured report corpus, not all literature or research quality.',
    'Missing metadata is not evidence that authors, keywords, references or citations are absent.',
    'Author names without identifiers can conflate homonyms or split variants; no automatic name disambiguation.',
    'DOI/OpenAlex/PMID references are bridged only by explicit identities in the input corpus; unmatched namespaces stay separate.',
    'Keywords use Unicode NFKC, whitespace normalization and case folding; no stemming, synonyms or abstract-derived terms.',
    'Citation summaries stay separate by retained-record provider; missing counts are never treated as zero.',
    'Communities are deterministic weighted label-propagation groups, not validated topics or research-gap findings.',
    'Duplicate DOI metadata keeps the first input record; alternate fields are retained in input.json rather than merged.'
]


def analyze(output, *, input_path=None, run_folder=None, database=None, allow_incomplete=False,
            min_occurrences=1, min_edge_count=1, normalization='cosine', max_pair_events=2000000,
            figures=False, max_figure_nodes=40):
    if sum(value is not None for value in (input_path, run_folder, database)) != 1:
        raise ValueError('Choose exactly one JSON input, retrieval run, or screening database')
    if type(max_figure_nodes) is not int or not 1 <= max_figure_nodes <= 100:
        raise ValueError('max_figure_nodes must be between 1 and 100')
    if run_folder is not None:
        rows, _, manifest = verify_run(run_folder)
        origin = {'mode': 'verified-retrieval-run', 'manifest': manifest,
                  'manifest_sha256': sha256((Path(run_folder) / 'manifest.json').read_bytes()).hexdigest()}
    elif database is not None:
        state = snapshot(database)
        if not state['prisma']['complete'] and not allow_incomplete:
            raise ValueError('Screening is incomplete; use allow_incomplete explicitly for a provisional included subset')
        rows = [r['metadata'] for r in state['records'] if r['fulltext'] == 'include']
        origin = {'mode': 'screening-included-reports', 'review_id': state['review_id'], 'criteria_version': state['criteria_version'],
                  'screening_complete': state['prisma']['complete'], 'snapshot': state}
    else:
        raw = Path(input_path).read_bytes()
        rows = json.loads(raw)
        if not isinstance(rows, list):
            raise ValueError('Input must be a JSON array of normalized records')
        origin = {'mode': 'standalone-json-unverified', 'filename': Path(input_path).name, 'sha256': sha256(raw).hexdigest()}
    records = [Record(**row) for row in rows]
    input_snapshot = [r.to_dict() for r in records]
    unique, duplicates = deduplicate(records)
    summary = descriptive_summary(unique)
    graphs, diagnostics = networks(unique, min_occurrences=min_occurrences, min_edge_count=min_edge_count,
                                   normalization=normalization, max_pair_events=max_pair_events)
    if figures:
        from .bibliometrics_figures import check_available
        check_available()
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    manifest = {'status': 'running', 'version': __version__, 'started_utc': datetime.now(timezone.utc).isoformat()}
    write_json(output / 'manifest.json', manifest)
    try:
        write_json(output / 'input.json', input_snapshot)
        write_json(output / 'records.json', [r.to_dict() for r in unique])
        write_json(output / 'duplicates.json', duplicates)
        write_json(output / 'origin.json', origin)
        write_json(output / 'summary.json', summary)
        write_json(output / 'coverage.json', diagnostics)
        settings = {'min_occurrences': min_occurrences, 'min_edge_count': min_edge_count, 'normalization': normalization,
                    'max_pair_events': max_pair_events, 'counting': 'full', 'figures': figures, 'max_figure_nodes': max_figure_nodes}
        write_json(output / 'methods.json', {'settings': settings, 'notices': NOTICES,
                   'networks': {kind: graph['methods'] for kind, graph in graphs.items()},
                   'clustering': {kind: graph['clustering'] for kind, graph in graphs.items()},
                   'definitions': {'coauthorship': 'Shared reports between author identities.',
                       'keywords': 'Shared reports between observed normalized keywords.',
                       'cocitation': 'Input reports citing both references.',
                       'coupling': 'Unique usable references shared by two input reports.'}})
        write_csv(output / 'publications_by_year.csv', ['year', 'records'], summary['publications_by_year'])
        write_csv(output / 'keyword_years.csv', ['year', 'keyword', 'records'], summary['keyword_years'])
        write_csv(output / 'citations_by_source.csv', ['source', 'records', 'records_with_citations', 'records_missing_citations', 'citation_sum_known', 'citation_mean_known', 'corpus_h_index_known'], summary['citations_by_source'])
        write_csv(output / 'documents.csv', ['id', 'source', 'source_id', 'doi', 'title', 'usable_references', 'reported_reference_count'], diagnostics['documents'])
        for kind, graph in graphs.items():
            write_json(output / f'{kind}.json', graph)
            write_csv(output / f'{kind}-nodes.csv', ['id', 'label', 'occurrences', 'cluster', 'degree', 'strength'], graph['nodes'])
            write_csv(output / f'{kind}-edges.csv', ['source', 'target', 'raw_weight', 'weight'], graph['edges'])
            _graphml(output / f'{kind}.graphml', graph)
        views = []
        if figures:
            from .bibliometrics_figures import render_figures
            views = render_figures(output, graphs, summary, max_nodes=max_figure_nodes, scope_note=_scope_note(origin))
        write_json(output / 'figures.json', views)
        _html(output, summary, graphs, origin, figures)
        manifest.update(status='complete', finished_utc=datetime.now(timezone.utc).isoformat(),
                        input_records=len(records), unique_records=len(unique), duplicates_removed=len(duplicates),
                        settings=settings, files={p.name: sha256(p.read_bytes()).hexdigest() for p in sorted(output.iterdir()) if p.name != 'manifest.json'})
        if figures:
            import matplotlib
            manifest['figure_runtime'] = {'matplotlib': matplotlib.__version__}
        write_json(output / 'manifest.json', manifest)
    except Exception:
        manifest['status'] = 'failed'
        write_json(output / 'manifest.json', manifest)
        raise
    return output


def _graphml(path, graph):
    from xml.etree.ElementTree import Element, SubElement, ElementTree
    ns = 'http://graphml.graphdrawing.org/xmlns'
    root = Element('graphml', xmlns=ns)
    for name, target, kind in [('label', 'node', 'string'), ('occurrences', 'node', 'int'), ('cluster', 'node', 'int'), ('weight', 'edge', 'double'), ('raw_weight', 'edge', 'int')]:
        SubElement(root, 'key', id=name, attrib={'for': target, 'attr.name': name, 'attr.type': kind})
    body = SubElement(root, 'graph', edgedefault='undirected')
    for row in graph['nodes']:
        node = SubElement(body, 'node', id=row['id'])
        for key in ('label', 'occurrences', 'cluster'):
            SubElement(node, 'data', key=key).text = str(row[key])
    for row in graph['edges']:
        edge = SubElement(body, 'edge', source=row['source'], target=row['target'])
        for key in ('weight', 'raw_weight'):
            SubElement(edge, 'data', key=key).text = str(row[key])
    ElementTree(root).write(path, encoding='utf-8', xml_declaration=True)


def _scope_note(origin):
    if origin['mode'] == 'screening-included-reports':
        return 'Screening-included reports' if origin['screening_complete'] else 'PROVISIONAL: screening incomplete; currently included reports'
    if origin['mode'] == 'standalone-json-unverified':
        return 'Standalone input; upstream selection unverified'
    return 'Retrieved/imported corpus; screening not applied'


def _html(folder, summary, graphs, origin, figures):
    parts = ['<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Bibliometric analysis</title>',
             '<style>body{font:16px/1.6 system-ui;max-width:1100px;margin:40px auto;padding:0 20px;color:#172033}img{width:100%;height:auto}table{border-collapse:collapse}td,th{padding:8px;border:1px solid #cbd5e1}pre{white-space:pre-wrap}</style>',
             '<h1>Bibliometric analysis</h1>', '<p><strong>' + escape(_scope_note(origin)) + '</strong></p>', f'<p>{summary["records"]} reports. Input scope: {escape(origin["mode"])}. Missing publication year: {summary["missing_years"]}.</p>',
             '<p>Inspect <a href="methods.json">methods and settings</a>, <a href="coverage.json">coverage</a>, and <a href="origin.json">input provenance</a> before interpreting results.</p>',
             '<h2>Limitations</h2><ul>' + ''.join('<li>' + escape(n) + '</li>' for n in NOTICES) + '</ul>',
             '<h2>Networks</h2><table><tr><th>Network</th><th>Coverage (reports)</th><th>Nodes</th><th>Edges</th><th>Data</th></tr>']
    for kind, graph in graphs.items():
        c = graph['coverage']
        parts.append(f'<tr><td>{kind}</td><td>{c["records_with_usable_metadata"]}/{c["records_total"]}</td><td>{len(graph["nodes"])}</td><td>{len(graph["edges"])}</td><td><a href="{kind}.json">JSON</a> / <a href="{kind}.graphml">GraphML</a></td></tr>')
    parts.append('</table><h2>Citations by retained-record provider</h2><pre>' + escape(json.dumps(summary['citations_by_source'], indent=2)) + '</pre>')
    if figures:
        for kind in list(graphs) + ['publications_by_year', 'keyword_years']:
            parts.append(f'<h2>{escape(kind.replace("_", " ").title())}</h2><img src="{kind}.svg" alt="{kind} figure">')
    else:
        parts.append('<p>Figures were not requested. Re-run into a new directory with --figures after installing the analysis extra.</p>')
    parts.append('<p>Every figure has data/settings alongside it. Full network exports include all retained nodes; figures may display a limited subset.</p></html>')
    (folder / 'report.html').write_text('\n'.join(parts), encoding='utf-8')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    inputs = parser.add_mutually_exclusive_group(required=True)
    inputs.add_argument('--input', help='Normalized JSON record array (unverified upstream provenance)')
    inputs.add_argument('--run', help='Completed, hash-verified retrieval/import directory')
    inputs.add_argument('--db', help='Screening database; analyze included reports')
    parser.add_argument('--output', required=True)
    parser.add_argument('--allow-incomplete', action='store_true')
    parser.add_argument('--min-occurrences', type=int, default=1)
    parser.add_argument('--min-edge-count', type=int, default=1)
    parser.add_argument('--normalization', choices=['none', 'cosine'], default='cosine')
    parser.add_argument('--max-pair-events', type=int, default=2000000)
    parser.add_argument('--figures', action='store_true', help='Write Matplotlib SVG/PNG figures; requires analysis extra')
    parser.add_argument('--max-figure-nodes', type=int, default=40)
    args = parser.parse_args(argv)
    try:
        output = analyze(args.output, input_path=args.input, run_folder=args.run, database=args.db,
            allow_incomplete=args.allow_incomplete, min_occurrences=args.min_occurrences,
            min_edge_count=args.min_edge_count, normalization=args.normalization, max_pair_events=args.max_pair_events,
            figures=args.figures, max_figure_nodes=args.max_figure_nodes)
    except (ValueError, TypeError, OSError, KeyError, sqlite3.DatabaseError) as exc:
        parser.exit(1, f'slr analyze: {exc}\n')
    print(f'Bibliometric artifacts written to {output}')
    return 0
