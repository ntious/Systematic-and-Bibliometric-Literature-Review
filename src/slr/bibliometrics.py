"""Deterministic full-count bibliometric graphs with explicit metadata coverage."""
from collections import Counter, defaultdict
from itertools import combinations
import math
import re
import unicodedata

from .models import normalize_doi, plain_text

KINDS = ('coauthorship', 'keywords', 'cocitation', 'coupling')


def term_key(value):
    return ' '.join(unicodedata.normalize('NFKC', plain_text(value)).casefold().split())


def reference_id(value):
    """Resolve explicit identifiers only; never guess from unstructured citations."""
    value = value.strip()
    doi = normalize_doi(value)
    if doi:
        return 'doi:' + doi
    match = re.fullmatch(r'(?:https?://(?:api\.)?openalex\.org/(?:works/)?|openalex:)?(W\d+)', value, re.I)
    if match:
        return 'openalex:' + match.group(1).upper()
    match = re.fullmatch(r'(?:pmid:|https?://pubmed\.ncbi\.nlm\.nih\.gov/)(\d+)/?', value, re.I)
    return 'pmid:' + match.group(1) if match else ''


def author_id(value):
    value = value.strip()
    match = re.fullmatch(r'(?:https?://orcid\.org/|orcid:)?(\d{4}-\d{4}-\d{4}-\d{3}[\dX])', value, re.I)
    if match:
        return 'orcid:' + match.group(1).upper()
    match = re.fullmatch(r'(?:https?://(?:api\.)?openalex\.org/(?:authors/)?|openalex:)?(A\d+)', value, re.I)
    return 'openalex:' + match.group(1).upper() if match else ''


def _aliases(records):
    aliases = {}
    for record in records:
        ids = {reference_id(record.doi)}
        for source in [{'source': record.source, 'source_id': record.source_id}] + record.provenance:
            value = str(source.get('source_id', ''))
            if source.get('source') == 'pubmed' and value.isdigit():
                value = 'pmid:' + value
            ids.add(reference_id(value))
        ids.discard('')
        canonical = 'doi:' + record.doi if record.doi else min(ids, default='')
        for identifier in ids:
            if identifier in aliases and aliases[identifier] != canonical:
                raise ValueError(f'Ambiguous reference identity: {identifier}')
            aliases[identifier] = canonical
    return aliases


def label_propagation(node_ids, edges, iterations=100):
    """Sorted asynchronous weighted voting, retaining current labels on ties."""
    adjacency = {node: {} for node in node_ids}
    for edge in edges:
        a, b = edge['source'], edge['target']
        adjacency[a][b] = adjacency[b][a] = edge['weight']
    labels = {node: node for node in node_ids}
    converged = False
    passes = 0
    for passes in range(1, iterations + 1):
        changes = 0
        for node in sorted(node_ids):
            scores = defaultdict(float)
            for neighbor, weight in sorted(adjacency[node].items()):
                scores[labels[neighbor]] += weight
            if not scores:
                continue
            best = max(scores.values())
            winners = sorted(label for label, score in scores.items() if math.isclose(score, best, rel_tol=1e-12, abs_tol=1e-12))
            chosen = labels[node] if labels[node] in winners else winners[0]
            if chosen != labels[node]:
                labels[node] = chosen
                changes += 1
        if not changes:
            converged = True
            break
    groups = {label: index for index, label in enumerate(sorted(set(labels.values())), 1)}
    return {node: groups[label] for node, label in labels.items()}, {'algorithm': 'sorted-asynchronous-weighted-label-propagation',
        'max_iterations': iterations, 'iterations': passes, 'converged': converged, 'clusters': len(groups)}


def networks(records, *, min_occurrences=1, min_edge_count=1, normalization='cosine', max_pair_events=2000000):
    if any(type(v) is not int or v < 1 for v in (min_occurrences, min_edge_count, max_pair_events)):
        raise ValueError('Thresholds and max_pair_events must be positive integers')
    if normalization not in ('none', 'cosine'):
        raise ValueError('Normalization must be none or cosine')
    aliases = _aliases(records)
    doc_ids = [f'D{i:06d}' for i in range(1, len(records) + 1)]
    authors, keywords, refs, labels = [], [], [], {}
    invalid_refs = 0
    id_authors = 0
    for record in records:
        team = set()
        for index, name in enumerate(record.authors):
            identifier = author_id(record.author_ids[index]) if record.author_ids else ''
            if not identifier and not term_key(name):
                continue
            key = identifier or 'name:' + term_key(name)
            if identifier:
                id_authors += 1
            team.add(key)
            labels[key] = min(labels.get(key, name or key), name or key)
        authors.append(team)
        terms = {term_key(k) for k in record.keywords if term_key(k)}
        keywords.append(terms)
        reference_set = set()
        for raw in record.references:
            identifier = reference_id(raw)
            if not identifier:
                invalid_refs += 1
                continue
            reference_set.add(aliases.get(identifier, identifier))
        # A report cannot be its own cited reference; provider self-links are removed.
        own_ids = {reference_id(record.doi), reference_id(record.source_id)}
        if record.source == 'pubmed':
            own_ids.add('pmid:' + record.source_id)
        own_ids = {aliases.get(i, i) for i in own_ids if i}
        reference_set -= own_ids
        refs.append(reference_set)
    # Check work before materializing pair events; failure never silently trims data.
    inverse = defaultdict(set)
    for doc, references in zip(doc_ids, refs):
        for reference in references:
            inverse[reference].add(doc)
    pair_events = sum(len(group) * (len(group) - 1) // 2 for groups in (authors, keywords, refs, list(inverse.values())) for group in groups)
    if pair_events > max_pair_events:
        raise ValueError(f'Analysis needs {pair_events} pair events, exceeding max_pair_events={max_pair_events}; use a smaller corpus or explicitly raise the budget')
    results = {}
    for kind, groups in [('coauthorship', authors), ('keywords', keywords), ('cocitation', refs), ('coupling', list(inverse.values()))]:
        frequency = Counter(node for group in groups for node in group)
        if kind == 'coupling':
            frequency = Counter({doc: len(references) for doc, references in zip(doc_ids, refs) if references})
        pairs = Counter(pair for group in groups for pair in combinations(sorted(group), 2))
        nodes = sorted(node for node, frequency_ in frequency.items() if frequency_ >= min_occurrences)
        retained = set(nodes)
        edges = []
        for (a, b), count in sorted(pairs.items()):
            if count < min_edge_count or a not in retained or b not in retained:
                continue
            weight = count / math.sqrt(frequency[a] * frequency[b]) if normalization == 'cosine' else float(count)
            edges.append({'source': a, 'target': b, 'raw_weight': count, 'weight': weight})
        cluster_ids, clustering = label_propagation(nodes, edges)
        degree, strength = Counter(), Counter()
        for edge in edges:
            for node in (edge['source'], edge['target']):
                degree[node] += 1
                strength[node] += edge['weight']
        document_labels = {doc: record.title or doc for doc, record in zip(doc_ids, records)}
        node_labels = labels if kind == 'coauthorship' else document_labels if kind == 'coupling' else {}
        usable_groups = refs if kind in ('cocitation', 'coupling') else authors if kind == 'coauthorship' else keywords
        covered = sum(bool(group) for group in usable_groups)
        results[kind] = {'kind': kind, 'nodes': [{'id': node, 'label': node_labels.get(node, node), 'occurrences': frequency[node],
                          'cluster': cluster_ids[node], 'degree': degree[node], 'strength': strength[node]} for node in nodes],
            'edges': edges, 'coverage': {'records_total': len(records), 'records_with_usable_metadata': covered,
                'records_without_usable_metadata': len(records) - covered, 'nodes_before_thresholds': len(frequency),
                'nodes_retained': len(nodes), 'edges_retained': len(edges)}, 'clustering': clustering,
            'methods': {'counting': 'binary incidence per report; full pair counting', 'normalization': normalization,
                'denominator': 'sqrt(reference_count_i * reference_count_j)' if kind == 'coupling' else 'sqrt(document_frequency_i * document_frequency_j)',
                'min_occurrences': min_occurrences, 'min_edge_count': min_edge_count,
                'frequency_unit': 'unique usable references' if kind == 'coupling' else 'reports',
                'threshold_order': 'node frequency and raw edge count, then normalization, then clustering'}}
    return results, {'pair_events': pair_events, 'max_pair_events': max_pair_events,
        'unresolved_reference_entries': invalid_refs, 'usable_reference_entries': sum(map(len, refs)),
        'author_entries_with_identifiers': id_authors, 'reference_namespaces': dict(Counter(r.split(':', 1)[0] for group in refs for r in group)),
        'documents': [{'id': doc, 'source': r.source, 'source_id': r.source_id, 'doi': r.doi, 'title': r.title,
                       'usable_references': len(group), 'reported_reference_count': r.reference_count}
                      for doc, r, group in zip(doc_ids, records, refs)]}


def descriptive_summary(records):
    years, missing_years = Counter(), 0
    sources = defaultdict(list)
    keyword_years = Counter()
    for record in records:
        if record.year is not None:
            if type(record.year) is not int or not 1000 <= record.year <= 9999:
                raise ValueError('Publication years must be four-digit integers or null')
            years[record.year] += 1
            for keyword in {term_key(k) for k in record.keywords if term_key(k)}:
                keyword_years[(record.year, keyword)] += 1
        else:
            missing_years += 1
        if record.citations is not None and (type(record.citations) is not int or record.citations < 0):
            raise ValueError('Citation counts must be nonnegative integers or null')
        sources[record.source].append(record.citations)
    citation_summary = []
    for source, counts in sorted(sources.items()):
        known = sorted((c for c in counts if c is not None), reverse=True)
        h_index = max((i for i, count in enumerate(known, 1) if count >= i), default=0) if known else None
        citation_summary.append({'source': source, 'records': len(counts), 'records_with_citations': len(known),
            'records_missing_citations': len(counts) - len(known), 'citation_sum_known': sum(known) if known else None,
            'citation_mean_known': sum(known) / len(known) if known else None, 'corpus_h_index_known': h_index})
    return {'records': len(records), 'missing_years': missing_years,
        'publications_by_year': [{'year': y, 'records': n} for y, n in sorted(years.items())],
        'citations_by_source': citation_summary,
        'keyword_years': [{'year': year, 'keyword': keyword, 'records': count} for (year, keyword), count in sorted(keyword_years.items())]}
