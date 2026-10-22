"""Regression cases motivated by the S02 real-research defects."""
from copy import deepcopy
from hashlib import sha256
import json

import pytest

from slr.dates import audit_dates
from slr.models import Record, deduplicate
from slr.pipeline import validate_plan
from slr.reporting import write_results, write_json
from slr.screening import verify_run
from slr.search import openalex_record, crossref_record


def record(identifier='same',doi='',reported='2026-10-22',source='openalex'):
    return Record(source=source,source_id=identifier,title='A study',year=2026,doi=doi,
                  provenance=[{'source':source,'source_id':identifier,'publication_date':reported}])


def test_provider_identity_merges_missing_doi_and_retains_all_query_provenance():
    first=record(); second=record()
    second.provenance.append({'query':'different query'})
    assert len(deduplicate(deepcopy([first,second]))[0])==2
    unique,duplicates=deduplicate([first,second],identity=True)
    assert len(unique)==1 and duplicates[0]['basis']=='source-id'
    assert {'query':'different query'} in unique[0].provenance
    assert len(deduplicate([record(),record(source='other')],identity=True)[0])==2


def test_conflicting_dois_and_empty_identifiers_are_not_identity_merged():
    unique,_=deduplicate([record(doi='10.1234/a'),record(doi='10.1234/b')],identity=True)
    assert len(unique)==2
    unique,_=deduplicate([record(),record(doi='10.1234/a'),record(doi='10.1234/b')],identity=True)
    assert len(unique)==2  # A DOI discovered after an initially DOI-free record still constrains identity matching.
    assert len(deduplicate([record(identifier=''),record(identifier='')],identity=True)[0])==2


@pytest.mark.parametrize('method,expected',[(None,2),('doi-or-source-id-v1',1)])
def test_historical_and_new_manifests_verify_with_their_declared_method(tmp_path,method,expected):
    write_results(tmp_path,[record(),record()],identity=bool(method))
    manifest={'status':'complete','files':{p.name:sha256(p.read_bytes()).hexdigest() for p in tmp_path.iterdir()}}
    if method: manifest['deduplication']=method
    write_json(tmp_path/'manifest.json',manifest)
    rows,counts,_=verify_run(tmp_path)
    assert len(rows)==expected and counts['identified']==2


def test_date_window_excludes_only_definitely_outside_and_keeps_uncertainty():
    records=[record(str(i),reported=value) for i,value in enumerate(['2026-10-22','2026-10-23','2026-10','2026','invalid','2026-09','2022-01-01','2021-12-31'])]
    kept,audit=audit_dates(records,'2022-01-01','2026-10-22')
    assert len(kept)==6 and audit['outside_window']==2 and audit['uncertain_dates']==3
    assert audit['checks'][2]['status']=='uncertain-boundary'
    assert audit['checks'][4]['status']=='unknown-or-invalid'


def test_adapters_preserve_date_precision_in_provenance():
    assert openalex_record({'id':'W1','publication_date':'2026-10-22'}).provenance[0]['publication_date']=='2026-10-22'
    assert crossref_record({'DOI':'10.1234/a','published':{'date-parts':[[2026,10]]}}).provenance[0]['publication_date']=='2026-10'


def test_plan_rejects_reversed_or_invalid_dates():
    base={'queries':['q'],'sources':['openalex']}
    with pytest.raises(ValueError):validate_plan({**base,'date_to':'2026-02-30'})
    with pytest.raises(ValueError):validate_plan({**base,'date_to':'2026-W43-4'})
    with pytest.raises(ValueError):validate_plan({**base,'date_from':'2026-10-23','date_to':'2026-10-22'})


def test_software_comparison_verifies_legacy_and_fixed_cohorts(tmp_path):
    from slr.pipeline import compare_sessions
    for name,identity in [('before',False),('after',True)]:
        run=tmp_path/name/'retrieval';run.mkdir(parents=True)
        write_results(run,[record(),record()],identity=identity)
        manifest={'status':'complete','session_id':name,'files':{p.name:sha256(p.read_bytes()).hexdigest() for p in run.iterdir()}}
        if identity:manifest['deduplication']='doi-or-source-id-v1'
        write_json(run/'manifest.json',manifest)
    report=compare_sessions(tmp_path/'before',tmp_path/'after')
    assert report['same_provider_identity_cohort']
    assert report['baseline_repeated_provider_ids']==1 and report['current_repeated_provider_ids']==0
    assert (tmp_path/'after/COMPARISON.md').exists()
