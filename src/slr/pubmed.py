"""Bounded PubMed ESearch/EFetch adapter using NCBI E-utilities."""
import re
from xml.etree import ElementTree as ET

from .models import Record
from .search import HTTPClient, SearchError

BASE = 'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/'


def _text(node, path):
    found = node.find(path)
    return ''.join(found.itertext()).strip() if found is not None else ''


def parse_pubmed(xml):
    try:
        root = ET.fromstring(xml)
    except ET.ParseError:
        raise SearchError('PubMed returned invalid XML') from None
    if root.tag != 'PubmedArticleSet' or root.find('.//ERROR') is not None:
        raise SearchError('PubMed returned an error or unexpected XML schema')
    records = []
    for item in root:
        # Book records are not silently dropped; their different schema is explicit.
        if item.tag not in ('PubmedArticle', 'PubmedBookArticle'):
            raise SearchError(f'Unsupported PubMed record type: {item.tag}')
        book = item.tag == 'PubmedBookArticle'
        article = item.find('BookDocument' if book else 'MedlineCitation/Article')
        citation = item.find('BookDocument' if book else 'MedlineCitation')
        if article is None or citation is None:
            raise SearchError('PubMed article metadata missing')
        pmid = _text(citation, 'PMID')
        if not pmid:
            raise SearchError('PubMed record has no PMID')
        authors, author_ids = [], []
        for author in article.findall('AuthorList/Author'):
            authors.append(_text(author, 'CollectiveName') or ' '.join(filter(None, [_text(author, 'ForeName') or _text(author, 'Initials'), _text(author, 'LastName')])))
            author_ids.append(next((i.text or '' for i in author.findall('Identifier') if i.get('Source', '').casefold() == 'orcid'), ''))
        keywords = [''.join(k.itertext()).strip() for k in citation.findall('KeywordList/Keyword')]
        references = [r.text or '' for r in item.findall('PubmedData/ReferenceList/Reference/ArticleIdList/ArticleId') if r.get('IdType') == 'doi']
        abstracts = []
        for part in article.findall('Abstract/AbstractText'):
            value = ''.join(part.itertext())
            abstracts.append((part.get('Label', '') + ': ' if part.get('Label') else '') + value)
        date = _text(article, 'Book/PubDate/Year' if book else 'Journal/JournalIssue/PubDate/Year')
        if not date and not book:
            date = _text(article, 'Journal/JournalIssue/PubDate/MedlineDate') or _text(article, 'ArticleDate/Year')
        match = re.search(r'\b(\d{4})\b', date)
        doi = next((a.text or '' for a in item.findall('.//ArticleId') if a.get('IdType') == 'doi'), '')
        records.append(Record(source='pubmed', source_id=pmid, title=_text(article, 'ArticleTitle') or _text(article, 'Book/BookTitle'),
            doi=doi, author_ids=author_ids, keywords=keywords, references=references, abstract=' '.join(abstracts), authors=authors, year=int(match.group(1)) if match else None,
            journal=_text(article, 'Book/BookTitle' if book else 'Journal/Title'), url=f'https://pubmed.ncbi.nlm.nih.gov/{pmid}/'))
    return records


def search_pubmed(query, limit, year_from=None, year_to=None, mailto='', client=None):
    if type(limit) is not int or not 1 <= limit <= 10000:
        raise ValueError('PubMed limit must be 1–10000; partition larger searches by date or use EDirect')
    client = client or HTTPClient(interval=1.0)
    common = {'db': 'pubmed', 'tool': 'slr-workbench'}
    if mailto:
        common['email'] = mailto
    params = {**common, 'term': query, 'retmode': 'json', 'retmax': limit, 'sort': 'pub date'}
    if year_from is not None or year_to is not None:
        params.update(datetype='pdat', mindate=f'{year_from or 1000}/01/01', maxdate=f'{year_to or 9999}/12/31')
    data = client.get(BASE + 'esearch.fcgi', params)
    try:
        result = data['esearchresult']
        if result.get('errorlist') or 'ERROR' in data:
            raise SearchError('PubMed rejected the search query; inspect query syntax')
        total = int(result['count'])
        ids = result['idlist']
        if not isinstance(ids, list) or len(set(ids)) != len(ids) or any(not isinstance(i, str) or not i.isdigit() for i in ids):
            raise ValueError('Invalid PMID list')
        if len(ids) != min(total, limit):
            raise SearchError('PubMed returned an incomplete identifier list')
    except (KeyError, TypeError, ValueError):
        raise SearchError('Unexpected PubMed search response schema') from None
    records, pages = [], [data]
    for start in range(0, len(ids), 100):
        batch = ids[start:start + 100]
        xml = client.get(BASE + 'efetch.fcgi', {**common, 'id': ','.join(batch), 'retmode': 'xml'}, response_format='text')
        found = parse_pubmed(xml)
        if len(found) != len(batch) or {r.source_id for r in found} != set(batch):
            raise SearchError('PubMed fetch did not return all requested PMIDs')
        pages.append({'pmids': batch, 'xml': xml})
        records.extend(found)
    return records, pages, {'source': 'pubmed', 'query': query, 'query_translation': result.get('querytranslation', ''),
        'year_from': year_from, 'year_to': year_to, 'limit': limit, 'available': total,
        'retrieved': len(records), 'truncated': len(records) < total}
