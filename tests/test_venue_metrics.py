"""Provider contracts, privacy and SCImago import semantics."""
import base64
import json
from pathlib import Path

import pytest

from slr.corpus import corpus_summary, parse_venue_metrics
from slr.models import Record
from slr.venue_metrics import elsevier_rows, clarivate_rows, csv_snapshot, retrieve, scimago_snapshot
from slr.dashboard import Workspace

SCIMAGO='''Rank;Sourceid;Title;Issn;SJR;SJR Best Quartile;H index;Publisher;Categories
1;1;Fictional Journal;"12345679, 23456789";"1,25";Q1;42;Example Press;"Computing (Q1); Security (Q2)"
'''


def test_scimago_category_and_dual_issn_matching():
    rows=parse_venue_metrics(scimago_snapshot(SCIMAGO,2024,'2026-10-22'))
    assert len(rows)==4
    assert {r['category'] for r in rows}=={'Computing','Security'}
    assert all(r['sjr']==1.25 and r['h_index']==42 and r['citescore'] is None for r in rows)
    records=[Record(source='test',source_id='1',journal='Fictional Journal',issns=['1234-5679','2345-6789'])]
    assert corpus_summary(records,rows)['venues'][0]['metric_match']=='ambiguous'
    result=corpus_summary(records,rows,category='Security')['venues'][0]
    assert result['external_metrics']['quartile']=='Q2'
    assert result['external_metrics']['quartile_basis']=='SJR'


def test_scimago_best_quartile_is_not_assigned_to_every_category():
    text=SCIMAGO.replace('Computing (Q1); Security (Q2)','Computing; Security')
    rows=parse_venue_metrics(scimago_snapshot(text,2024,'2026-10-22'))
    assert rows[0]['category']=='Best across reported categories'
    assert rows[0]['quartile_basis']=='SJR best quartile'
    with pytest.raises(ValueError):scimago_snapshot('<html>Blocked</html>',2024,'2026-10-22')


def test_elsevier_exact_year_and_identity_no_tracker_substitution():
    entry={'prism:issn':'1234-5679','dc:title':'Fictional Journal','SNIPList':{'SNIP':[{'@year':'2024','$':'0'}]},
           'SJRList':{'SJR':{'@year':'2024','$':'1.2'}},
           'citeScoreYearInfoList':{'citeScoreCurrentMetricYear':'2024','citeScoreCurrentMetric':'4.5','citeScoreTrackerYear':'2025','citeScoreTracker':'99'}}
    payload={'serial-metadata-response':{'entry':[entry]}}
    rows=parse_venue_metrics(csv_snapshot(elsevier_rows(payload,'1234-5679',2024)))
    assert rows[0]['citescore']==4.5 and rows[0]['snip']==0 and not rows[0].get('quartile')
    with pytest.raises(ValueError,match='requested year'):elsevier_rows(payload,'1234-5679',2025)
    with pytest.raises(ValueError,match='ISSN'):elsevier_rows(payload,'2345-6789',2024)


def test_jcr_quartile_basis_category_and_suppression():
    report={'year':2024,'ranks':{'jif':[{'category':'Security','edition':'SCIE','quartile':'Q2'}]}}
    row=clarivate_rows(report,{'name':'Example'},'1234-5679',2024,'EXAMPLE')[0]
    assert row['quartile_basis']=='JCR JIF' and row['category']=='Security / SCIE'
    assert parse_venue_metrics(csv_snapshot([row]))[0]['quartile']=='Q2'
    with pytest.raises(ValueError):clarivate_rows({**report,'suppressed':True},{},'1234-5679',2024,'EXAMPLE')


def test_provider_key_only_in_headers_and_failures_redacted(monkeypatch):
    monkeypatch.setenv('ELSEVIER_API_KEY','private-test-key')
    class Client:
        def get(self,url,params,headers):
            assert 'private-test-key' not in url+str(params)
            assert headers['X-ELS-APIKey']=='private-test-key'
            raise RuntimeError('private-test-key')
    rows,audit=retrieve([{'name':'Example','issns':['1234-5679']}],'elsevier',2024,client=Client())
    assert not rows and 'private-test-key' not in json.dumps(audit)
    monkeypatch.delenv('ELSEVIER_API_KEY')
    with pytest.raises(ValueError,match='ELSEVIER_API_KEY'):retrieve([],'elsevier',2024)


def test_source_url_cannot_carry_secret_query_or_script():
    base='journal,year,metric_source,retrieved_date,source_url\nExample,2024,Example provider,2026-10-22,'
    for url in ['javascript:alert(1)','https://example.org/?apiKey=secret','https://user:secret@example.org/']:
        with pytest.raises(ValueError):parse_venue_metrics(base+url)


def test_missing_key_job_logs_failure_and_preserves_snapshot(tmp_path,monkeypatch):
    monkeypatch.delenv('ELSEVIER_API_KEY',raising=False)
    ws=Workspace(tmp_path)
    entry=ws.create({'name':'Synthetic','question':'Example','criteria':'Example','reviewers':['A','B'],'adjudicator':'C'})
    ws.import_venue_metrics(entry['id'],{'name':'source.csv','base64':base64.b64encode(b'journal,year,metric_source,retrieved_date\nExample,2024,Example,2026-10-22').decode()})
    previous=ws.entry(entry['id'])['venue_metrics']
    job=ws.fetch_venue_metrics(entry['id'],{'provider':'elsevier','year':2024})
    ws.executor.shutdown(wait=True)
    assert ws.jobs[job['id']]['status']=='failed'
    assert ws.entry(entry['id'])['venue_metrics']==previous
    assert 'ELSEVIER_API_KEY' in Path(job['session_report']).read_text()
