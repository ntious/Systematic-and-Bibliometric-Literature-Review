"""Covered-corpus totals and venue productivity, separate from external journal metrics."""
from collections import Counter, defaultdict
import csv
from datetime import date
import io
import math
import re
from urllib.parse import urlsplit

from .bibliometrics import author_id, descriptive_summary, term_key


def issn_key(value):
    raw = value.replace('-', '').strip().upper()
    return raw[:4]+'-'+raw[4:] if re.fullmatch(r'\d{7}[\dX]', raw) else ''


def parse_venue_metrics(text):
    reader=csv.DictReader(io.StringIO(text.lstrip('\ufeff')))
    if not reader.fieldnames or len(set(reader.fieldnames))!=len(reader.fieldnames):
        raise ValueError('Venue metrics need unique CSV headers')
    required={'year','metric_source','retrieved_date'}
    if not required <= set(reader.fieldnames):
        raise ValueError('Venue metrics require year, metric_source and retrieved_date columns')
    rows=[]
    for index,row in enumerate(reader,2):
        if None in row or any(v is None for v in row.values()):
            raise ValueError(f'Metric row {index} does not match its header')
        row={k:v.strip() for k,v in row.items()}
        if not any(row.get(k) for k in ('venue_id','issn','journal')):
            raise ValueError(f'Metric row {index} needs a venue ID, ISSN or journal name')
        if row.get('issn') and not issn_key(row['issn']):
            raise ValueError(f'Invalid ISSN in metric row {index}')
        if not re.fullmatch(r'\d{4}',row['year']) or not 1000<=int(row['year'])<=9999:
            raise ValueError(f'Invalid metric year in row {index}')
        if not row['metric_source'] or date.fromisoformat(row['retrieved_date']).isoformat()!=row['retrieved_date']:
            raise ValueError('Metric provider and YYYY-MM-DD retrieval date are required')
        row['year']=int(row['year'])
        row['issn']=issn_key(row.get('issn',''))
        statuses={}
        for field in ('citescore','snip','sjr','h_index'):
            raw=row.get(field,'')
            if raw.casefold() in ('*','n/a','na','not applicable'):
                row[field]=None;statuses[field]='not-applicable'
            elif not raw:
                row[field]=None;statuses[field]='missing'
            else:
                try: number=float(raw)
                except ValueError: raise ValueError(f'Invalid {field} in metric row {index}') from None
                if not math.isfinite(number) or number<0 or (field=='h_index' and not number.is_integer()):
                    raise ValueError(f'Invalid {field} in metric row {index}')
                row[field]=int(number) if field=='h_index' else number
                statuses[field]='reported'
        if row.get('quartile') and row['quartile'] not in ('Q1','Q2','Q3','Q4','*','N/A'):
            raise ValueError('Quartile must be Q1–Q4, *, N/A or blank')
        if row.get('quartile','').startswith('Q') and not row.get('category'):
            raise ValueError('A reported quartile requires its subject category')
        url=row.get('source_url','')
        if url:
            parts=urlsplit(url)
            if parts.scheme!='https' or not parts.hostname or parts.username or parts.password or parts.query or parts.fragment:
                raise ValueError('Metric source_url must be an HTTPS link without credentials, query or fragment')
        if row.get('quartile_basis','') not in ('','SJR','SJR best quartile','JCR JIF','JCR JCI','CiteScore'):
            raise ValueError('Choose SJR, JCR JIF, JCR JCI or CiteScore as quartile_basis')
        row['statuses']=statuses
        rows.append(row)
    if not rows: raise ValueError('Venue-metrics CSV contains no records')
    return rows


def corpus_summary(records, metrics=None, *, year=None, category=None):
    records=list(records)
    base=descriptive_summary(records)  # also validates years/citation counts
    n=len(records)
    authors,affiliations,keywords,countries,subjects=set(),set(),set(),set(),set()
    coverage=Counter();taxonomy=defaultdict(set)
    author_identified=author_named=keyword_occurrences=0
    parents={}
    def find(key):
        parents.setdefault(key,key)
        if parents[key]!=key:parents[key]=find(parents[key])
        return parents[key]
    def keys(r):
        return (['id:'+r.venue_id] if r.venue_id else [])+['issn:'+issn_key(i) for i in r.issns if issn_key(i)]
    for r in records:
        identifiers=keys(r)
        for key in identifiers:
            a,b=find(identifiers[0]),find(key)
            parents[max(a,b)]=min(a,b)
    title_ids=defaultdict(set)
    for r in records:
        explicit=find(keys(r)[0]) if keys(r) else ''
        if r.journal and explicit:title_ids[term_key(r.journal)].add(explicit)
    venues={}
    for r in records:
        for i,name in enumerate(r.authors):
            raw=r.author_ids[i].strip() if r.author_ids else ''
            key=(author_id(raw) or 'provider:'+r.source+':'+raw) if raw else 'name:'+term_key(name)
            if raw:author_identified+=1
            elif term_key(name):author_named+=1
            if raw or term_key(name):authors.add(key)
        for i,name in enumerate(r.affiliations):
            raw=r.affiliation_ids[i].strip() if r.affiliation_ids else ''
            if raw or term_key(name):affiliations.add('id:'+raw if raw else 'name:'+term_key(name))
        terms={term_key(k) for k in r.keywords if term_key(k)}
        keywords.update(terms);keyword_occurrences+=len(terms)
        countries.update(c.strip().upper() for c in r.countries if c.strip())
        for subject in r.subject_areas:
            if term_key(subject):
                name=r.subject_taxonomy or 'Unspecified taxonomy'
                subjects.add((name,term_key(subject)));taxonomy[name].add(term_key(subject))
        for field,present in [('authors',any(term_key(a) for a in r.authors) or any(i.strip() for i in r.author_ids)),('affiliations',any(term_key(a) for a in r.affiliations) or any(i.strip() for i in r.affiliation_ids)),('keywords',bool(terms)),('countries',any(c.strip() for c in r.countries)),('subject_areas',any(term_key(a) for a in r.subject_areas)),('citations',r.citations is not None),('sources',bool(r.journal or r.venue_id or any(issn_key(v) for v in r.issns)))]:
            coverage[field]+=bool(present)
        if not (r.journal or r.venue_id or any(issn_key(v) for v in r.issns)):continue
        name=r.journal or r.venue_id or next(i for i in r.issns if issn_key(i))
        key=find(keys(r)[0]) if keys(r) else ''
        if not key:
            candidates=title_ids[term_key(r.journal)]
            key=next(iter(candidates)) if len(candidates)==1 else 'name:'+term_key(name)
        v=venues.setdefault(key,{'key':key,'name':name,'publications':0,'venue_ids':set(),'issns':set(),'publishers':set(),'names':set()})
        v['publications']+=1;v['names'].add(term_key(name));v['venue_ids'].update([r.venue_id] if r.venue_id else [])
        v['issns'].update(issn_key(i) for i in r.issns if issn_key(i))
        if r.publisher:v['publishers'].add(r.publisher)
    metrics=metrics or []
    years=sorted({r['year'] for r in metrics},reverse=True)
    if year is not None and (type(year) is not int or not 1000<=year<=9999):raise ValueError('Invalid metric year')
    selected=year if year is not None else (years[0] if years else None)
    selected_rows=[r for r in metrics if r['year']==selected and (not category or r.get('category')==category)]
    names_count=Counter(name for v in venues.values() for name in v['names'])
    matched_ids=set();ranked=[]
    for rank,v in enumerate(sorted(venues.values(),key=lambda v:(-v['publications'],term_key(v['name']),v['key'])),1):
        candidates=[]
        for index,m in enumerate(selected_rows):
            if m.get('venue_id'):match=m['venue_id'] in v['venue_ids'];basis='venue-id'
            elif m.get('issn'):match=m['issn'] in v['issns'];basis='issn'
            else:match=term_key(m.get('journal','')) in v['names'] and names_count[term_key(m.get('journal',''))]==1;basis='exact-normalized-name'
            if match:
                signature={k:value for k,value in m.items() if k!='issn'}
                if not any({k:value for k,value in old.items() if k!='issn'}==signature for _,old,_ in candidates):
                    candidates.append((index,m,basis))
                matched_ids.add(index)
        metric=candidates[0][1] if len(candidates)==1 else None
        if len(candidates)==1:matched_ids.add(candidates[0][0])
        ranked.append({'rank':rank,'key':v['key'],'name':v['name'],'publications':v['publications'],
            'venue_ids':sorted(v['venue_ids']),'issns':sorted(v['issns']),
            'publisher':metric.get('publisher') or '; '.join(sorted(v['publishers'])) if metric else '; '.join(sorted(v['publishers'])),
            'external_metrics':metric,'metric_match':candidates[0][2] if metric else 'ambiguous' if candidates else 'unavailable'})
    def observed(value,field):return value if coverage[field] or not n else None
    totals={'papers':n,'authors':observed(len(authors),'authors'),'sources':observed(len(venues),'sources'),
            'affiliations':observed(len(affiliations),'affiliations'),'keywords':observed(len(keywords),'keywords'),
            'subject_areas':observed(len(subjects),'subject_areas'),'countries':observed(len(countries),'countries'),
            'citations':sum(r.citations for r in records if r.citations is not None) if coverage['citations'] or not n else None}
    return {'totals':totals,'coverage':{field:{'records':coverage[field],'total':n} for field in ('authors','sources','affiliations','keywords','subject_areas','citations','countries')},
            'author_entries_with_ids':author_identified,'author_entries_name_only':author_named,'keyword_occurrences':keyword_occurrences,
            'subject_taxonomies':[{'taxonomy':t,'areas':len(values)} for t,values in sorted(taxonomy.items())],
            'citations_by_provider':base['citations_by_source'],'venues':ranked,
            'metric_year':selected,'metric_years':years,'metric_categories':sorted({r.get('category','') for r in metrics if r.get('category')}),
            'unmatched_metric_rows':len(selected_rows)-len(matched_ids),'missing_venue_records':n-coverage['sources'],
            'notices':['Totals describe the selected retained report corpus, not all literature or distinct underlying studies.',
                       'Authors and affiliations use explicit IDs when supplied, otherwise normalized names; names are not disambiguated and ID/name variants may split identities.',
                       'Keywords are unique normalized terms; keyword occurrences count per-report incidence. Subject areas remain separated by reported taxonomy.',
                       'Countries are reported affiliation-country labels/codes, not author nationality. Missing metadata is not zero.',
                       'Citations sum the available retained-record provider counts; providers and capture dates differ. See provider subtotals; missing counts are not zero.',
                       'TP is corpus publication count. CiteScore, SNIP, SJR, quartile and reported venue H-index are imported external snapshots, not calculated from this corpus.',
                       'No fuzzy venue-name matching. Ambiguous external rows remain unresolved; choose a category or correct identifiers.']}


def export_corpus(report, folder):
    """Export every ranked venue, not only the UI's top ten."""
    from pathlib import Path
    from .reporting import write_csv, write_json
    folder=Path(folder)
    write_json(folder/'corpus-summary.json',report)
    write_csv(folder/'corpus-summary.csv',['measure','observed_total','records_with_metadata','corpus_records'],
              [{'measure':k,'observed_total':v,'records_with_metadata':report['coverage'].get(k,{}).get('records',report['totals']['papers']),'corpus_records':report['totals']['papers']} for k,v in report['totals'].items()])
    columns=['rank','venue','TP','citescore','snip','sjr','quartile','publisher','h_index','year','category','metric_source','retrieved_date','source_url','quartile_basis','match']
    rows=[]
    for v in report['venues']:
        row={'rank':v['rank'],'venue':v['name'],'TP':v['publications'],'publisher':v['publisher'],'match':v['metric_match']}
        m=v['external_metrics'] or {}
        for key in columns[3:]:
            if key in ('publisher','match'):continue
            row[key]='*' if m.get('statuses',{}).get(key)=='not-applicable' else m.get(key)
        rows.append(row)
    write_csv(folder/'publication-venues.csv',columns,rows)
    sources=[]
    for v in report['venues']:
        m=v['external_metrics']
        if m:
            citation=f"{m['metric_source']}, metric year {m['year']}, retrieved {m['retrieved_date']}"
            if m.get('source_url'):citation+=f". {m['source_url']}"
            if m.get('quartile'):citation+=f". Quartile basis: {m.get('quartile_basis') or 'unspecified'}; category: {m.get('category','')}"
            if citation not in sources:sources.append(citation)
    (folder/'metric-sources.md').write_text('# External metric sources\n\n'+'\n'.join(f'[{i}] {s}' for i,s in enumerate(sources,1))+'\n',encoding='utf-8')
    (folder/'corpus-methods.md').write_text('# Corpus summary and venue ranking\n\n'+'\n'.join('- '+n for n in report['notices'])+'\n',encoding='utf-8')
