import json
from unittest.mock import MagicMock

import pytest

from slr.imports import import_files, parse_csv, parse_ris
from slr.pubmed import parse_pubmed
from slr.search import SearchError, search
from slr.screening import initialize, verify_run

XML = '''<PubmedArticleSet><PubmedArticle><MedlineCitation><PMID>123</PMID><Article>
<ArticleTitle>AI in <i>education</i></ArticleTitle><Journal><Title>Example Journal</Title>
<JournalIssue><PubDate><MedlineDate>2024 Jan-Feb</MedlineDate></PubDate></JournalIssue></Journal>
<Abstract><AbstractText Label="METHODS">A <b>study</b>.</AbstractText></Abstract>
<AuthorList><Author><LastName>Smith</LastName><ForeName>Ada</ForeName></Author>
<Author><CollectiveName>Example Group</CollectiveName></Author></AuthorList></Article></MedlineCitation>
<PubmedData><ArticleIdList><ArticleId IdType="doi">10.1234/ABC</ArticleId></ArticleIdList></PubmedData>
</PubmedArticle></PubmedArticleSet>'''


def test_pubmed_normalization():
    record = parse_pubmed(XML)[0]
    assert record.source_id == '123' and record.year == 2024
    assert record.title == 'AI in education' and record.doi == '10.1234/abc'
    assert record.abstract == 'METHODS: A study.'
    assert record.authors == ['Ada Smith', 'Example Group']
    assert record.citations is None


def test_pubmed_search_filters_and_raw_pages():
    client = MagicMock()
    client.get.side_effect = [{'esearchresult': {'count': '10', 'idlist': ['123'], 'querytranslation': 'translated'}}, XML]
    records, pages, log = search('pubmed', 'topic', 1, 2020, 2025, client=client)
    assert len(records) == 1 and log['truncated'] and log['query_translation'] == 'translated'
    assert client.get.call_args_list[0].args[1]['mindate'] == '2020/01/01'
    assert pages[1]['xml'] == XML


def test_pubmed_zero_results():
    client = MagicMock()
    client.get.return_value = {'esearchresult': {'count': '0', 'idlist': []}}
    records, pages, log = search('pubmed', 'none', 10, client=client)
    assert not records and not log['truncated'] and client.get.call_count == 1


def test_pubmed_limit_and_malformed_response():
    with pytest.raises(ValueError, match='10000'):
        search('pubmed', 'topic', 10001)
    with pytest.raises(SearchError, match='invalid XML'):
        parse_pubmed('<not-xml')
    client = MagicMock()
    client.get.side_effect = [{'esearchresult': {'count': '1', 'idlist': ['456']}}, XML]
    with pytest.raises(SearchError, match='all requested'):
        search('pubmed', 'topic', 1, client=client)


def test_pubmed_fetch_batching():
    client = MagicMock()
    ids = [str(i) for i in range(1, 102)]
    def get(url, params, **kwargs):
        if 'esearch' in url:
            return {'esearchresult': {'count': '101', 'idlist': ids}}
        articles = ''.join('<PubmedArticle><MedlineCitation><PMID>' + i + '</PMID><Article><ArticleTitle>Test</ArticleTitle></Article></MedlineCitation></PubmedArticle>' for i in params['id'].split(','))
        return '<PubmedArticleSet>' + articles + '</PubmedArticleSet>'
    client.get.side_effect = get
    records, pages, log = search('pubmed', 'topic', 101, client=client)
    assert len(records) == 101 and len(pages) == 3 and not log['truncated']


def test_scopus_and_wos_columns():
    records = parse_csv('Title,DOI,Year,Authors,EID,Cited by\nStudy,10.1234/a,2024,A Smith; B Jones,2-s2.0-1,3\n', 'scopus', 'hash')
    assert records[0].authors == ['A Smith', 'B Jones'] and records[0].citations == 3
    record = parse_csv('Article Title,Publication Year,Source Title,UT\nStudy,2023,Journal,WOS:1\n', 'wos', 'hash')[0]
    assert record.source_id == 'WOS:1' and record.journal == 'Journal'


def test_ris_wrapping_and_multiple_authors():
    record = parse_ris('TY  - JOUR\nTI  - Study\nAU  - Smith, A\nAU  - Jones, B\nAB  - First\n  second\nPY  - 2024/01/01\nDO  - 10.1234/A\nER  -\n', 'scopus', 'hash')[0]
    assert record.year == 2024 and record.abstract == 'First second'
    assert len(record.authors) == 2 and record.doi == '10.1234/a'


@pytest.mark.parametrize('text', ['TY  - JOUR\nTI  - Test', 'TI  - Missing TY\nER  -', 'TY  - JOUR\nER  -'])
def test_invalid_ris_rejected(text):
    with pytest.raises(ValueError):
        parse_ris(text, 'source', 'hash')


@pytest.mark.parametrize('text', ['Wrong header\nStudy\n', 'Title,Year\nStudy,unknown\n', 'Title,Year\nStudy,2020,extra\n', 'Title,title\nA,B\n'])
def test_invalid_csv_rejected(text):
    with pytest.raises(ValueError):
        parse_csv(text, 'source', 'hash')


def test_imported_files_keep_raw_data_and_enter_screening(tmp_path):
    csv = tmp_path / 'source.csv'
    ris = tmp_path / 'source.ris'
    csv.write_text('\ufeffTitle,DOI,Year\nStudy,10.1234/a,2024\n', encoding='utf-8')
    ris.write_text('TY  - JOUR\nTI  - Study\nDO  - 10.1234/a\nER  -\n')
    output = import_files([csv, ris], tmp_path / 'import', 'licensed-export')
    records, counts, manifest = verify_run(output)
    assert counts['identified'] == 2 and counts['duplicates_removed'] == 1
    assert len(records[0]['provenance']) == 2
    assert (output / 'input-001.csv').read_bytes() == csv.read_bytes()
    assert manifest['mode'] == 'import'
    assert initialize(tmp_path / 'review.sqlite', output, 'Imported review', ['a', 'b'], 'c', 'Criteria') == 1


def test_normalized_json_merge_and_roundtrip(tmp_path):
    output = import_files(['Examples/demo_records.json'], tmp_path / 'import', 'demo')
    records, counts, _ = verify_run(output)
    assert len(records) == 2 and counts['identified'] == 3
    output2 = import_files([output / 'records.csv'], tmp_path / 'roundtrip', 'roundtrip')
    assert len(json.loads((output2 / 'records.json').read_text())) == 2
