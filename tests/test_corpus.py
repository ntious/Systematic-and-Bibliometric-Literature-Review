"""Hand-calculated corpus/venue summaries and external-metric provenance checks."""
import base64
import csv
from hashlib import sha256
import io
import json
from pathlib import Path
import zipfile

import pytest

from slr.corpus import corpus_summary, parse_venue_metrics
from slr.dashboard import Workspace
from slr.models import Record
from slr.search import openalex_record, crossref_record
from slr.imports import parse_csv
from slr.bibliometrics_cli import analyze

METRICS='''journal,issn,venue_id,year,citescore,snip,sjr,quartile,category,publisher,h_index,metric_source,retrieved_date
Journal A,1234-5679,,2022,9.5,2.019,1.197,Q1,Information Systems,Synthetic Publisher,122,Fictional provider fixture,2023-06-01
Journal B,,,2022,*,*,0.2,,Demonstration,Example Press,0,Fictional provider fixture,2023-06-01
'''


def records():
    return [Record(source='openalex',source_id='W1',journal='Journal A',venue_id='https://openalex.org/S1',issns=['1234-5679'],publisher='Captured Publisher',
                   authors=['Alice'],author_ids=['https://orcid.org/0000-0000-0000-000X'],affiliations=['Institute A'],affiliation_ids=['I1'],
                   keywords=['AI','Security'],countries=['US'],subject_areas=['Computing'],subject_taxonomy='OpenAlex fields',citations=5),
            Record(source='crossref',source_id='two',journal='JOURNAL A',issns=['1234-5679'],authors=['Alice'],author_ids=['https://orcid.org/0000-0000-0000-000X'],
                   affiliations=['Institute A variant'],affiliation_ids=['I1'],keywords=['security','Deep learning'],countries=['GB'],
                   subject_areas=['Computing'],subject_taxonomy='OpenAlex fields',citations=0),
            Record(source='crossref',source_id='three',journal='Journal B',authors=['Bob'],subject_areas=['Computing'],subject_taxonomy='Other taxonomy')]


def test_hand_calculated_totals_coverage_and_venue_identity_bridge():
    result=corpus_summary(records())
    assert result['totals']=={'papers':3,'authors':2,'sources':2,'affiliations':1,'keywords':3,'subject_areas':2,'citations':5,'countries':2}
    assert result['coverage']['citations']=={'records':2,'total':3}
    assert result['venues'][0]['publications']==2
    assert result['venues'][0]['venue_ids']==['https://openalex.org/S1']
    assert result['keyword_occurrences']==4


def test_missing_is_not_zero_and_empty_corpus_has_known_zero():
    result=corpus_summary([Record(source='test',source_id='one')])
    assert result['totals']['papers']==1
    assert all(value is None for key,value in result['totals'].items() if key!='papers')
    assert all(value==0 for value in corpus_summary([])['totals'].values())


def test_external_metrics_keep_year_provider_na_and_corpus_tp_separate():
    result=corpus_summary(records(),parse_venue_metrics(METRICS),year=2022)
    first,second=result['venues']
    assert first['publications']==2 and first['external_metrics']['h_index']==122
    assert first['external_metrics']['year']==2022 and first['external_metrics']['metric_source']=='Fictional provider fixture'
    assert first['metric_match']=='issn' and first['publisher']=='Synthetic Publisher'
    assert second['external_metrics']['statuses']['citescore']=='not-applicable'
    assert second['external_metrics']['h_index']==0
    assert corpus_summary(records(),parse_venue_metrics(METRICS),year=2025)['venues'][0]['external_metrics'] is None


def test_multiple_categories_remain_ambiguous_until_selected():
    rows=parse_venue_metrics(METRICS)
    rows.append({**rows[0],'category':'Other category','quartile':'Q3'})
    assert corpus_summary(records(),rows,year=2022)['venues'][0]['metric_match']=='ambiguous'
    selected=corpus_summary(records(),rows,year=2022,category='Other category')['venues'][0]
    assert selected['external_metrics']['quartile']=='Q3'


@pytest.mark.parametrize('changed',[METRICS.replace('9.5','nan'),METRICS.replace('2022','2022.5'),METRICS.replace('Information Systems',''),METRICS.replace(',122,',',1.5,'),METRICS.replace('2023-06-01','not-a-date')])
def test_invalid_metric_snapshot_is_rejected(changed):
    with pytest.raises(ValueError):parse_venue_metrics(changed)


def test_provider_adapters_and_csv_preserve_affiliations_countries_and_subjects():
    row=openalex_record({'id':'W1','primary_location':{'source':{'id':'S1','display_name':'Journal A','issn':['1234-5679'],'host_organization_name':'Example publisher'}},
        'authorships':[{'author':{'display_name':'Alice'},'institutions':[{'id':'I1','ror':'https://ror.org/example','display_name':'Institute A','country_code':'US'}]}],
        'topics':[{'field':{'display_name':'Computing'}}]})
    assert row.affiliations==['Institute A'] and row.countries==['US'] and row.subject_areas==['Computing']
    imported=parse_csv('title,affiliations,affiliation_ids,countries,subject areas,subject taxonomy,issn,publisher\nA study,Institute A,I1,US,Computing,ASJC,1234-5679,Example\n','import','abc')[0]
    assert imported.affiliation_ids==['I1'] and imported.subject_taxonomy=='ASJC'
    assert crossref_record({'publisher':'Example','author':[{'given':'A','affiliation':[{'name':'Institute A'}]}]}).affiliations==['Institute A']


def test_cli_exports_all_venues_and_metric_provenance(tmp_path):
    path=tmp_path/'input.json';path.write_text(json.dumps([r.to_dict() for r in records()]))
    metrics=tmp_path/'metrics.csv';metrics.write_text(METRICS)
    analyze(tmp_path/'analysis',input_path=path,venue_metrics=metrics,metric_year=2022)
    rows=list(csv.DictReader((tmp_path/'analysis/publication-venues.csv').open()))
    assert len(rows)==2 and rows[0]['TP']=='2' and rows[0]['h_index']=='122'
    assert rows[1]['citescore']=='*'
    manifest=json.loads((tmp_path/'analysis/manifest.json').read_text())
    assert 'venue-metrics-input.csv' in manifest['files']
    assert 'Top 10 publication venues' in (tmp_path/'analysis/report.html').read_text()


def test_workspace_metrics_import_is_atomic_and_export_is_scope_bound(tmp_path):
    workspace=Workspace(tmp_path/'workspace')
    try:
        entry=workspace.create({'name':'Synthetic metrics test','question':'Example question','criteria':'Example criteria','reviewers':['A','B'],'adjudicator':'C'})
        data=json.dumps([r.to_dict() for r in records()]).encode()
        workspace.import_uploads(entry['id'],{'source':'Synthetic fixture','files':[{'name':'records.json','base64':base64.b64encode(data).decode()}]})
        workspace.import_venue_metrics(entry['id'],{'name':'metrics.csv','base64':base64.b64encode(METRICS.encode()).decode()})
        previous=workspace.entry(entry['id'])['venue_metrics']
        with pytest.raises(ValueError):workspace.import_venue_metrics(entry['id'],{'name':'metrics.csv','base64':base64.b64encode(b'bad\n').decode()})
        assert workspace.entry(entry['id'])['venue_metrics']==previous
        report=workspace.corpus_analysis(entry['id'],year=2022)
        assert report['totals']['papers']==3 and report['metric_import']['sha256']==sha256(METRICS.encode()).hexdigest()
        assert workspace.corpus_analysis(entry['id'],scope='included')['totals']['papers']==0
        with zipfile.ZipFile(io.BytesIO(workspace.export_corpus(entry['id'],year=2022))) as archive:
            rows=list(csv.DictReader(io.StringIO(archive.read('publication-venues.csv').decode())))
            assert rows[0]['metric_source']=='Fictional provider fixture'
            assert len(json.loads(archive.read('input-records.json')))==3
        (tmp_path/'workspace'/Path(previous).name/'input.csv').write_text('tampered')
        with pytest.raises(ValueError,match='hash mismatch'):workspace.corpus_analysis(entry['id'])
    finally:workspace.executor.shutdown(wait=True)


def test_blank_metadata_labels_remain_missing_not_zero():
    r=Record(source="test",source_id="blank",authors=[" "],affiliations=[""],countries=[" "],subject_areas=[""])
    result=corpus_summary([r])
    assert all(result["totals"][k] is None for k in ("authors","affiliations","countries","subject_areas"))
