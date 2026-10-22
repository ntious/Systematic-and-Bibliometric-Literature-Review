from copy import deepcopy
from hashlib import sha256
import json
import math
from pathlib import Path
from unittest.mock import patch
from xml.etree import ElementTree as ET

import pytest

from slr.bibliometrics import author_id, descriptive_summary, label_propagation, networks, reference_id
from slr.bibliometrics_cli import analyze
from slr.cli import main, run
from slr.imports import import_files
from slr.models import Record
from slr.pubmed import parse_pubmed
from slr.screening import initialize, verify_run
from slr.search import crossref_record, openalex_record


@pytest.fixture
def records():
    return [Record(**r) for r in json.loads(Path('Examples/bibliometrics_records.json').read_text())]


def edge(graph, a, b):
    return next(e for e in graph['edges'] if {e['source'], e['target']} == {a, b})


def test_hand_calculated_coauthorship_and_keywords(records):
    graphs, coverage = networks(records)
    e = edge(graphs['coauthorship'], 'name:alice example', 'name:bob example')
    assert e['raw_weight'] == 1 and e['weight'] == 0.5
    e = edge(graphs['keywords'], 'ai', 'learning')
    assert e['raw_weight'] == 1 and e['weight'] == 0.5
    assert len(graphs['keywords']['nodes']) == 4
    isolate = next(n for n in graphs['coauthorship']['nodes'] if n['id'] == 'name:dana example')
    assert isolate['degree'] == 0 and isolate['occurrences'] == 1
    assert coverage['pair_events'] == 16


def test_hand_calculated_cocitation_and_coupling(records):
    graphs, _ = networks(records)
    e = edge(graphs['cocitation'], 'doi:10.9000/x', 'doi:10.9000/y')
    assert e['raw_weight'] == 2 and e['weight'] == pytest.approx(2 / math.sqrt(6))
    e = edge(graphs['coupling'], 'D000001', 'D000002')
    assert e['raw_weight'] == 1 and e['weight'] == 0.5
    e = edge(graphs['coupling'], 'D000001', 'D000003')
    assert e['raw_weight'] == 2 and e['weight'] == pytest.approx(2 / math.sqrt(6))
    assert graphs['coupling']['coverage']['records_with_usable_metadata'] == 3


def test_raw_count_normalization_and_thresholds(records):
    graphs, _ = networks(records, normalization='none', min_edge_count=2)
    assert all(not graphs[k]['edges'] for k in ('coauthorship', 'keywords'))
    assert all(e['weight'] == 2 for e in graphs['cocitation']['edges'])
    graphs, _ = networks(records, min_occurrences=3)
    assert not graphs['coauthorship']['nodes']
    assert [n['id'] for n in graphs['cocitation']['nodes']] == ['doi:10.9000/x']


def test_pair_budget_and_invalid_options(records):
    with pytest.raises(ValueError, match='pair events'):
        networks(records, max_pair_events=15)
    with pytest.raises(ValueError, match='Normalization'):
        networks(records, normalization='unknown')
    with pytest.raises(ValueError, match='positive integers'):
        networks(records, min_occurrences=True)


def test_reference_bridging_and_self_link_removal():
    records = [Record('openalex', 'https://openalex.org/W9', doi='10.9000/target', references=['openalex:W9']),
               Record('a', '1', references=['https://openalex.org/W9', '10.9000/shared']),
               Record('b', '2', references=['https://doi.org/10.9000/target', 'doi:10.9000/shared'])]
    graphs, coverage = networks(records)
    assert edge(graphs['coupling'], 'D000002', 'D000003')['raw_weight'] == 2
    assert coverage['documents'][0]['usable_references'] == 0
    assert 'openalex' not in coverage['reference_namespaces']


def test_unknown_references_are_not_guessed():
    records = [Record('a', '1', references=['Smith (2024), title', '10.9000/x']), Record('b', '2', references=['W12'])]
    graphs, coverage = networks(records)
    assert coverage['unresolved_reference_entries'] == 1
    assert not graphs['coupling']['edges']
    assert coverage['reference_namespaces'] == {'doi': 1, 'openalex': 1}


def test_identifier_normalization_and_author_identity():
    assert reference_id('https://doi.org/10.9000/X') == 'doi:10.9000/x'
    assert reference_id('https://api.openalex.org/works/w9') == 'openalex:W9'
    assert reference_id('https://pubmed.ncbi.nlm.nih.gov/123/') == 'pmid:123'
    assert author_id('https://orcid.org/0000-0001-2345-678X') == 'orcid:0000-0001-2345-678X'
    records = [Record('a', '1', authors=['Same Name', 'Same Name'], author_ids=['A1', 'A2'])]
    graphs, _ = networks(records)
    assert len(graphs['coauthorship']['nodes']) == 2
    assert len(graphs['coauthorship']['edges']) == 1


def test_missing_citations_stay_missing_and_provider_separation(records):
    summary = descriptive_summary(records)
    assert summary['missing_years'] == 1
    source = summary['citations_by_source'][0]
    assert source['source'] == 'synthetic-a' and source['records_missing_citations'] == 1
    assert source['citation_sum_known'] == 7 and source['citation_mean_known'] == 3.5
    assert source['corpus_h_index_known'] == 2
    missing = descriptive_summary([Record('a', '1')])['citations_by_source'][0]
    assert missing['citation_sum_known'] is None and missing['corpus_h_index_known'] is None
    assert next(r for r in summary['keyword_years'] if r['year'] == 2022 and r['keyword'] == 'ai')['records'] == 1


def test_clustering_deterministic_disconnected_groups():
    edges = [{'source': 'a', 'target': 'b', 'weight': 1}, {'source': 'c', 'target': 'd', 'weight': 1}]
    labels, info = label_propagation(['e', 'd', 'c', 'b', 'a'], edges)
    assert labels['a'] == labels['b'] and labels['c'] == labels['d']
    assert len({labels['a'], labels['c'], labels['e']}) == 3
    assert info['converged']
    assert (labels, info) == label_propagation(['a', 'b', 'c', 'd', 'e'], list(reversed(edges)))


def test_empty_and_sparse_data():
    graphs, _ = networks([])
    assert all(not g['nodes'] and not g['edges'] for g in graphs.values())
    assert descriptive_summary([])['records'] == 0
    graphs, _ = networks([Record('a', '1')])
    assert all(g['coverage']['records_without_usable_metadata'] == 1 for g in graphs.values())


def test_analysis_exports_provenance_and_graphml(tmp_path):
    folder = analyze(tmp_path / 'analysis', input_path='Examples/bibliometrics_records.json')
    manifest = json.loads((folder / 'manifest.json').read_text())
    assert manifest['status'] == 'complete' and manifest['unique_records'] == 4
    assert all(sha256((folder / name).read_bytes()).hexdigest() == digest for name, digest in manifest['files'].items())
    root = ET.parse(folder / 'coupling.graphml').getroot()
    assert len(root.findall('.//{http://graphml.graphdrawing.org/xmlns}edge')) == 3
    assert json.loads((folder / 'origin.json').read_text())['mode'] == 'standalone-json-unverified'
    assert (folder / 'report.html').is_file()
    with pytest.raises(FileExistsError):
        analyze(folder, input_path='Examples/bibliometrics_records.json')


def test_duplicate_doi_audited_without_input_mutation(tmp_path, records):
    rows = [r.to_dict() for r in records] + [records[0].to_dict()]
    path = tmp_path / 'input.json'
    path.write_text(json.dumps(rows))
    folder = analyze(tmp_path / 'analysis', input_path=path)
    assert len(json.loads((folder / 'duplicates.json').read_text())) == 1
    assert len(json.loads((folder / 'input.json').read_text())) == 5
    assert json.loads(path.read_text()) == rows


def test_old_retrieval_snapshot_compatible(tmp_path):
    run_folder = tmp_path / 'run'
    run('configs/example_review.toml', run_folder, 'Examples/demo_records.json')
    # Recreate the normalized schema emitted before 0.3.0, with matching hashes.
    for name in ('records.json', 'retrieved.json'):
        path = run_folder / name
        rows = json.loads(path.read_text())
        for row in rows:
            for key in ('author_ids', 'keywords', 'references', 'reference_count'):
                row.pop(key)
        path.write_text(json.dumps(rows))
    path = run_folder / 'manifest.json'
    manifest = json.loads(path.read_text())
    manifest['files'] = {name: sha256((run_folder / name).read_bytes()).hexdigest() for name in manifest['files']}
    path.write_text(json.dumps(manifest))
    verify_run(run_folder)
    initialize(tmp_path / 'old.sqlite', run_folder, 'Old review', ['a', 'b'], 'c', 'Criteria')
    output = analyze(tmp_path / 'analysis', run_folder=run_folder)
    assert json.loads((output / 'manifest.json').read_text())['status'] == 'complete'


def test_incomplete_screening_requires_explicit_override(tmp_path):
    run_folder = tmp_path / 'run'
    run('configs/example_review.toml', run_folder, 'Examples/demo_records.json')
    db = tmp_path / 'review.sqlite'
    initialize(db, run_folder, 'Review', ['a', 'b'], 'c', 'Criteria')
    with pytest.raises(ValueError, match='incomplete'):
        analyze(tmp_path / 'blocked', database=db)
    assert not (tmp_path / 'blocked').exists()
    output = analyze(tmp_path / 'provisional', database=db, allow_incomplete=True)
    assert json.loads((output / 'summary.json').read_text())['records'] == 0
    assert not json.loads((output / 'origin.json').read_text())['screening_complete']
    assert 'PROVISIONAL: screening incomplete' in (output / 'report.html').read_text()


def test_metadata_survives_adapters_and_import_roundtrip(tmp_path):
    record = openalex_record({'id': 'W1', 'authorships': [{'author': {'id': 'A1', 'display_name': 'A'}}],
        'keywords': [{'display_name': 'AI'}], 'referenced_works': ['W2']})
    assert record.references == ['W2'] and record.keywords == ['AI'] and record.author_ids == ['A1']
    record = crossref_record({'DOI': '10.9000/a', 'reference': [{'DOI': '10.9000/b'}, {'unstructured': 'Unknown'}], 'references-count': 2})
    assert record.references == ['10.9000/b'] and record.reference_count == 2 and not record.keywords
    folder = import_files(['Examples/bibliometrics_records.json'], tmp_path / 'import', 'synthetic')
    for suffix in ('csv', 'ris'):
        roundtrip = import_files([folder / ('records.' + suffix)], tmp_path / suffix, 'roundtrip')
        record = Record(**json.loads((roundtrip / 'records.json').read_text())[0])
        assert record.keywords == ['AI', 'Learning', 'AI'] and record.references == ['10.9000/x', '10.9000/y']


def test_figures_failure_marks_output_failed(tmp_path):
    with patch('slr.bibliometrics_figures.check_available'), patch('slr.bibliometrics_figures.render_figures', side_effect=ValueError('render failed')):
        with pytest.raises(ValueError, match='render failed'):
            analyze(tmp_path / 'failed', input_path='Examples/bibliometrics_records.json', figures=True)
    assert json.loads((tmp_path / 'failed/manifest.json').read_text())['status'] == 'failed'


def test_cli_invalid_metadata_has_no_partial_output(tmp_path):
    path = tmp_path / 'bad.json'
    path.write_text('[{"source":"a","source_id":"1","authors":"not-an-array"}]')
    with pytest.raises(SystemExit) as error:
        main(['analyze', '--input', str(path), '--output', str(tmp_path / 'out')])
    assert error.value.code == 1 and not (tmp_path / 'out').exists()


def test_metadata_validation():
    with pytest.raises(ValueError, match='align'):
        Record('a', '1', authors=['A', 'B'], author_ids=['A1'])
    with pytest.raises(ValueError, match='reference_count'):
        Record('a', '1', reference_count=-1)
    with pytest.raises(ValueError, match='Citation counts'):
        descriptive_summary([Record('a', '1', citations=-1)])


def test_real_figures_respect_display_limit_without_truncating_graph(tmp_path):
    pytest.importorskip('matplotlib')
    folder = analyze(tmp_path / 'figures', input_path='Examples/bibliometrics_records.json', figures=True, max_figure_nodes=2)
    views = json.loads((folder / 'figures.json').read_text())
    coauthorship = next(v for v in views if v['figure'] == 'coauthorship')
    assert len(coauthorship['displayed_node_ids']) == 2 and coauthorship['nodes_omitted'] == 2
    assert len(json.loads((folder / 'coauthorship.json').read_text())['nodes']) == 4
    for view in views:
        ET.parse(folder / (view['figure'] + '.svg'))
        assert (folder / (view['figure'] + '.png')).stat().st_size > 1000
    assert len(views) == 6


def test_pubmed_extended_metadata():
    xml = '''<PubmedArticleSet><PubmedArticle><MedlineCitation><PMID>1</PMID><Article>
    <ArticleTitle>Test</ArticleTitle><AuthorList><Author><LastName>Example</LastName>
    <Identifier Source="ORCID">0000-0001-2345-678X</Identifier></Author></AuthorList></Article>
    <KeywordList><Keyword>AI</Keyword></KeywordList></MedlineCitation><PubmedData><ReferenceList>
    <Reference><ArticleIdList><ArticleId IdType="doi">10.9000/x</ArticleId></ArticleIdList></Reference>
    </ReferenceList></PubmedData></PubmedArticle></PubmedArticleSet>'''
    record = parse_pubmed(xml)[0]
    assert record.keywords == ['AI'] and record.references == ['10.9000/x']
    assert record.author_ids == ['0000-0001-2345-678X']
