"""Explicit, ISSN-verified journal-metric retrieval from official provider APIs.

Credentials stay in headers. Never infer a quartile or substitute a metric year.
"""
import csv
from datetime import date
import io
import os
import re
from urllib.parse import quote

from .corpus import issn_key, parse_venue_metrics
from .search import HTTPClient, SearchError

COLUMNS = ['journal','issn','year','citescore','snip','sjr','quartile','quartile_basis',
           'category','publisher','h_index','metric_source','retrieved_date','source_url']
PROVIDERS = {'elsevier': 'ELSEVIER_API_KEY', 'clarivate': 'CLARIVATE_API_KEY'}


def as_list(value):
    return value if isinstance(value,list) else [value] if isinstance(value,dict) else []


def csv_snapshot(rows):
    buffer=io.StringIO()
    writer=csv.DictWriter(buffer,fieldnames=COLUMNS)
    writer.writeheader();writer.writerows(rows)
    text=buffer.getvalue()
    parse_venue_metrics(text)  # reject invalid numeric/provider data before publication
    return text


def elsevier_rows(payload, issn, year):
    entries=as_list(payload.get('serial-metadata-response',{}).get('entry'))
    matches=[e for e in entries if issn in {issn_key(e.get('prism:issn') or ''),issn_key(e.get('prism:eIssn') or '')}]
    if len(matches)!=1:raise ValueError('No unique exact ISSN match in Elsevier response')
    e=matches[0]
    row={'journal':e.get('dc:title',''),'issn':issn,'year':year,'metric_source':'Elsevier Scopus Serial Title API',
         'retrieved_date':date.today().isoformat(),'source_url':'https://api.elsevier.com/content/serial/title/issn/'+issn,
         'publisher':e.get('dc:publisher','')}
    for name,field in [('SNIP','snip'),('SJR','sjr')]:
        values=[v.get('$') for v in as_list((e.get(name+'List') or {}).get(name)) if str(v.get('@year'))==str(year)]
        if len(values)>1:raise ValueError('Ambiguous provider metric year')
        if values and values[0] is not None:row[field]=values[0]
    info=e.get('citeScoreYearInfoList') or {}
    if str(info.get('citeScoreCurrentMetricYear'))==str(year):row['citescore']=info.get('citeScoreCurrentMetric','')
    # Tracker values are provisional, not annual CiteScores. SJR is not a quartile.
    if not any(str(row.get(k,'')) for k in ('citescore','snip','sjr')):
        raise ValueError('No annual metrics returned for the requested year')
    return [row]


def clarivate_rows(report, journal, issn, year, identifier):
    if report.get('year')!=year or report.get('suppressed'):
        raise ValueError('Requested JCR year unavailable or suppressed')
    ranks=as_list((report.get('ranks') or {}).get('jif'))
    rows=[]
    for rank in ranks:
        if rank.get('quartile') not in ('Q1','Q2','Q3','Q4') or not rank.get('category'):continue
        category=rank['category']+((' / '+rank['edition']) if rank.get('edition') else '')
        rows.append({'journal':journal.get('name',''),'issn':issn,'year':year,'quartile':rank['quartile'],
                     'quartile_basis':'JCR JIF','category':category,'metric_source':'Clarivate Journal Citation Reports API',
                     'retrieved_date':date.today().isoformat(),
                     'source_url':'https://api.clarivate.com/apis/wos-journals/v1/journals/'+quote(identifier,safe='')+'/reports/year/'+str(year)})
    if not rows:raise ValueError('No category-specific JCR JIF quartiles returned for the requested year')
    return rows


def retrieve(venues, provider, year, *, client=None, progress=None):
    """Return validated rows and a redacted per-venue audit. Caller persists it."""
    if provider not in PROVIDERS:raise ValueError('Choose Elsevier or Clarivate')
    if type(year) is not int or not 1997<=year<=date.today().year:raise ValueError('Choose a metric year from 1997 through the current year')
    key=os.getenv(PROVIDERS[provider],'').strip()
    if not key:raise ValueError('Configure '+PROVIDERS[provider]+' on the dashboard server; approved provider access is required')
    client=client or HTTPClient(interval=1,retries=1,timeout=15)
    headers={'Accept':'application/json',('X-ELS-APIKey' if provider=='elsevier' else 'X-ApiKey'):key}
    if provider=='elsevier' and os.getenv('ELSEVIER_INSTTOKEN'):headers['X-ELS-Insttoken']=os.environ['ELSEVIER_INSTTOKEN']
    rows=[];audit=[]
    for index,venue in enumerate(venues):
        if progress:progress(index,len(venues))
        item={'venue':venue['name'],'issns':venue['issns'],'status':'unavailable','attempts':[]}
        for issn in venue['issns']:
            try:
                if provider=='elsevier':
                    payload=client.get('https://api.elsevier.com/content/serial/title/issn/'+issn,{'view':'ENHANCED','date':str(year)},headers=headers)
                    found=elsevier_rows(payload,issn,year)
                else:
                    base='https://api.clarivate.com/apis/wos-journals/v1/journals'
                    hits=client.get(base,{'q':issn,'jcrYear':year,'limit':2},headers=headers)
                    if len(hits.get('hits',[]))!=1:raise ValueError('No unique JCR search match')
                    identifier=hits['hits'][0]['id']
                    journal=client.get(base+'/'+quote(identifier,safe=''),{},headers=headers)
                    if issn not in {issn_key(journal.get('issn') or ''),issn_key(journal.get('eIssn') or '')}:
                        raise ValueError('JCR ISSN verification failed')
                    payload=client.get(base+'/'+quote(identifier,safe='')+'/reports/year/'+str(year),{},headers=headers)
                    found=clarivate_rows(payload,journal,issn,year,identifier)
                csv_snapshot(found)
                rows.extend(found);item.update(status='retrieved',rows=len(found));break
            except (ValueError, SearchError) as exc:
                # Only application-generated, credential-free messages are admitted.
                safe=str(exc) if isinstance(exc,SearchError) else 'Unmatched ISSN, unavailable year or invalid provider metric data'
                item['attempts'].append({'issn':issn,'error':safe})
            except Exception:
                # Avoid serializing arbitrary transport/provider exceptions or payloads containing secrets.
                item['attempts'].append({'issn':issn,'error':'Lookup failed, unmatched, unavailable year, access denied or invalid provider data'})
        if not venue['issns']:item['reason']='No valid ISSN supplied; title-only lookup skipped'
        audit.append(item)
    return rows,audit


def scimago_snapshot(text, year, retrieved_date):
    """Normalize SCImago's semicolon-delimited Download data export.

    Category quartiles are retained separately. A best quartile is explicitly
    labelled across categories, never attributed to every listed category.
    """
    if type(year) is not int or not 1997<=year<=date.today().year:
        raise ValueError('Choose a metric year from 1997 through the current year')
    date.fromisoformat(retrieved_date)
    reader=csv.DictReader(io.StringIO(text.lstrip('\ufeff')),delimiter=';')
    if not {'Title','Issn','SJR','SJR Best Quartile','H index'}<=set(reader.fieldnames or []):
        raise ValueError('Expected a SCImago Download data CSV with Title, Issn, SJR, SJR Best Quartile and H index')
    rows=[]
    for original in reader:
        if None in original or any(v is None for v in original.values()):raise ValueError('Malformed SCImago CSV row')
        identifiers=sorted({issn_key(i) for i in re.split(r'[,; ]+',original['Issn']) if issn_key(i)})
        if not identifiers:continue
        categories=[]
        for category in original.get('Categories','').split(';'):
            match=re.fullmatch(r'\s*(.+?)\s*\((Q[1-4])\)\s*',category)
            if match:categories.append((match[1],match[2],'SJR'))
        best=original['SJR Best Quartile'].strip()
        if not categories:
            categories=[('Best across reported categories',best,'SJR best quartile')] if best in ('Q1','Q2','Q3','Q4') else [('', '', '')]
        for issn in identifiers:
            for category,quartile,basis in categories:
                rows.append({'journal':original['Title'],'issn':issn,'year':year,
                    'sjr':original['SJR'].strip().replace(',','.'),'h_index':original['H index'].strip(),
                    'quartile':quartile,'quartile_basis':basis,'category':category,
                    'publisher':original.get('Publisher',''),'metric_source':'SCImago Journal & Country Rank',
                    'retrieved_date':retrieved_date,'source_url':'https://www.scimagojr.com/journalrank.php'})
    if not rows:raise ValueError('No valid ISSN-bearing rows in SCImago CSV')
    return csv_snapshot(rows)
