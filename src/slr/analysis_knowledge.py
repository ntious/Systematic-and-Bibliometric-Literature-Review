"""Local analysis knowledge graph and provisional recommendation service.

No model calls, no statistical execution, no automatic approvals or review DB writes.
"""
import argparse
from contextlib import closing
from hashlib import sha256
import json
from pathlib import Path
import re
import sqlite3

from .analysis_catalogue import INTENTS, METHODS, SOURCES, VERSION

SCHEMA = 'litatlas-analysis-knowledge-v1'


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'))


def seed():
    nodes, edges = [], []
    for identifier, title, url, locator, scope in SOURCES:
        nodes.append({'id': 'source:' + identifier, 'kind': 'source', 'data': dict(
            title=title, url=url, locator=locator, scope=scope, accessed='2026-10-23',
            access_basis='source metadata and identified sections; no full article redistribution')})
    for identifier, (label, cues) in INTENTS.items():
        nodes.append({'id': 'intent:' + identifier, 'kind': 'intent', 'data': dict(label=label, cues=cues,
                      status='local_unvalidated_hypothesis', language='en')})
    vocabulary = set()
    for item in METHODS:
        method_id = 'method:' + item['id']
        nodes.append({'id': method_id, 'kind': 'method', 'data': item})
        edges.append(dict(subject=method_id, predicate='documented_in', object='source:' + item['source'],
                          status='source_link_requires_curation', locator=item['locator']))
        for intent in item['intents']:
            edges.append(dict(subject='intent:' + intent, predicate='candidate_method', object=method_id,
                              status='local_unvalidated_hypothesis', locator='local design rule; not asserted by the cited source'))
        for predicate, key in [('requires_field', 'required_fields'), ('requires_human_check', 'human_checks'), ('produces', 'outputs')]:
            for value in item[key]:
                target = predicate + ':' + value
                if target not in vocabulary:
                    nodes.append(dict(id=target, kind=predicate, data={'label': value}))
                    vocabulary.add(target)
                edges.append(dict(subject=method_id, predicate=predicate, object=target,
                                  status='local_eligibility_checklist_requires_review', locator=item['locator']))
    return {'schema': SCHEMA, 'version': VERSION, 'nodes': sorted(nodes, key=lambda n: n['id']),
            'edges': sorted(edges, key=canonical)}


def validate(graph):
    if graph.get('schema') != SCHEMA or graph.get('version') != VERSION:
        raise ValueError('Unsupported knowledge schema/version')
    nodes = graph['nodes']
    ids = {node['id'] for node in nodes}
    if len(ids) != len(nodes):
        raise ValueError('Duplicate knowledge identifier')
    by_id = {node['id']: node for node in nodes}
    for edge in graph['edges']:
        if edge['subject'] not in ids or edge['object'] not in ids:
            raise ValueError('Dangling knowledge relation')
    for node in nodes:
        if node['kind'] == 'method':
            item = node['data']
            if not item['required_fields'] or not item['human_checks']:
                raise ValueError('Method lacks explicit prerequisites')
            if 'source:' + item['source'] not in by_id:
                raise ValueError('Method lacks source provenance')
            if item['execution_status'] != 'not_integrated':
                raise ValueError('This knowledge service has no execution adapters')
    return graph


def initialize(database):
    graph = validate(seed())
    path = Path(database)
    path.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive reservation also prevents accidentally using a screening/evidence ledger.
    with path.open('xb'):
        pass
    try:
        with closing(sqlite3.connect(path)) as conn:
            conn.execute('PRAGMA foreign_keys=ON')
            with conn:
                conn.execute('CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL)')
                conn.execute('CREATE TABLE nodes (id TEXT PRIMARY KEY, kind TEXT NOT NULL, data TEXT NOT NULL)')
                conn.execute('CREATE TABLE edges (subject TEXT REFERENCES nodes(id), predicate TEXT, object TEXT REFERENCES nodes(id), data TEXT NOT NULL, PRIMARY KEY(subject,predicate,object))')
                conn.executemany('INSERT INTO metadata VALUES (?,?)', [('schema', SCHEMA), ('version', VERSION), ('sha256', sha256(canonical(graph).encode()).hexdigest())])
                conn.executemany('INSERT INTO nodes VALUES (?,?,?)', [(n['id'], n['kind'], canonical(n['data'])) for n in graph['nodes']])
                conn.executemany('INSERT INTO edges VALUES (?,?,?,?)', [(e['subject'], e['predicate'], e['object'], canonical(e)) for e in graph['edges']])
    except Exception:
        path.unlink(missing_ok=True)
        raise
    return graph


def load(database):
    path = Path(database).resolve(strict=True)
    with closing(sqlite3.connect(path.as_uri() + '?mode=ro', uri=True)) as conn:
        metadata = dict(conn.execute('SELECT key,value FROM metadata'))
        graph = dict(schema=metadata['schema'], version=metadata['version'],
                     nodes=[dict(id=i, kind=k, data=json.loads(d)) for i, k, d in conn.execute('SELECT id,kind,data FROM nodes ORDER BY id')],
                     edges=sorted([json.loads(row[0]) for row in conn.execute('SELECT data FROM edges')], key=canonical))
    validate(graph)
    if sha256(canonical(graph).encode()).hexdigest() != metadata['sha256']:
        raise ValueError('Knowledge database content hash mismatch')
    return graph


def recommend(graph, question, *, intents=None, available_fields=None, human_checks=None, requested_method=None):
    """Return explainable candidates only, never approvals or executable analyses.

    Fields are researcher-declared names, not verified data; checks are self-reports.
    Unknown/negated wording is not interpreted reliably: confirmation is always required.
    """
    validate(graph)
    if not isinstance(question, str) or not question.strip() or len(question) > 20000:
        raise ValueError('Question must be nonempty text of at most 20000 characters')
    by_id = {node['id']: node for node in graph['nodes']}
    intent_nodes = {n['id'].split(':', 1)[1]: n['data'] for n in graph['nodes'] if n['kind'] == 'intent'}
    text = question.casefold()
    hints = []
    for identifier, item in intent_nodes.items():
        matched = [cue for cue in item['cues'] if re.search(r'(?<!\w)' + re.escape(cue.casefold()) + r'(?!\w)', text)]
        if matched:
            hints.append(dict(intent=identifier, matched_phrases=matched, confirmed=False))
    confirmed = intents is not None
    chosen = set(intents if confirmed else [h['intent'] for h in hints])
    if not chosen <= intent_nodes.keys():
        raise ValueError('Unknown intent; choose a catalogue intent or request clarification')
    fields = set(available_fields or [])
    checks = set(human_checks or [])
    known_fields = {n['data']['label'] for n in graph['nodes'] if n['kind'] == 'requires_field'}
    known_checks = {n['data']['label'] for n in graph['nodes'] if n['kind'] == 'requires_human_check'}
    if not fields <= known_fields or not checks <= known_checks:
        raise ValueError('Unknown field or human-check identifier; inspect the catalogue')
    candidates = []
    methods = [n['data'] for n in graph['nodes'] if n['kind'] == 'method']
    for method in sorted(methods, key=lambda m: m['id']):
        matched = sorted(chosen.intersection(method['intents']))
        if method['id'] != requested_method and not matched:
            continue
        missing = sorted(set(method['required_fields']) - fields)
        unresolved = sorted(set(method['human_checks']) - checks)
        state = 'needs_intent_confirmation' if not confirmed else ('needs_prerequisite_review' if missing or unresolved else 'candidate_requires_methodologist_review')
        candidates.append(dict(method=method, matched_intents=matched, requested=method['id'] == requested_method,
                               state=state, missing_fields=missing, unresolved_human_checks=unresolved,
                               intent_fit='candidate' if matched else 'not_established',
                               execution_allowed=False, source=by_id['source:' + method['source']]['data']))
    supported_request = requested_method is None or any(m['id'] == requested_method for m in methods)
    return dict(schema=SCHEMA, catalogue_version=graph['version'], catalogue_sha256=sha256(canonical(graph).encode()).hexdigest(),
                question=question, tentative_intents=hints, confirmed_intents=sorted(chosen) if confirmed else [],
                declared_fields=sorted(fields), declared_checks=sorted(checks), candidates=candidates,
                requested_method=requested_method, requested_method_known=supported_request,
                execution_allowed=False, approval_recorded=False,
                notice='Provisional English phrase hints; ambiguity and negation need human review. Declared fields/checks do not verify actual data. No model calls or analysis execution. Empty suggestions do not imply no suitable method exists.')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    init = sub.add_parser('init', help='Create a new dedicated local knowledge database')
    init.add_argument('--db', required=True)
    show = sub.add_parser('catalogue', help='Print the graph, including sources and prerequisites')
    show.add_argument('--db', required=True)
    query = sub.add_parser('recommend', help='Print provisional candidates; never run or approve analyses')
    query.add_argument('--db', required=True)
    query.add_argument('--question', required=True)
    query.add_argument('--intent', action='append', help='Researcher-confirmed intent ID; repeat as needed')
    query.add_argument('--field', action='append', default=[], help='Declared available field ID')
    query.add_argument('--check', action='append', default=[], help='Declared completed human-check ID')
    query.add_argument('--method', help='Explicit requested catalogue method ID')
    args = parser.parse_args(argv)
    try:
        if args.command == 'init':
            graph = initialize(args.db)
            result = dict(schema=SCHEMA, version=VERSION, methods=sum(n['kind'] == 'method' for n in graph['nodes']),
                          sources=sum(n['kind'] == 'source' for n in graph['nodes']))
        else:
            graph = load(args.db)
            result = graph if args.command == 'catalogue' else recommend(graph, args.question, intents=args.intent,
                        available_fields=args.field, human_checks=args.check, requested_method=args.method)
    except (ValueError, OSError, sqlite3.Error, KeyError, TypeError) as exc:
        parser.exit(1, f'slr knowledge: {exc}\n')
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0
