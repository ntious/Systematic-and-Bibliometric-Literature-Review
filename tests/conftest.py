"""Shared setup for tests of the review-bound retrieval workflow."""
from uuid import uuid4

import pytest
from slr import questions, review_plan as rp
from slr.cli import run as _fixture_run  # captured before any test replaces slr.cli.run


@pytest.fixture
def approved_search(tmp_path):
    def prepare(workspace, entry, queries=None):
        db=entry['screening_db']
        questions.mutate(db,{'actor':'A','expected_revision':0,'action':'save','topic':'Synthetic test','questions':['Does the test work?']})
        questions.mutate(db,{'actor':'A','expected_revision':1,'action':'approve'})
        def body(**kw):
            s=rp.state(db)
            return dict(actor='A',expected_revision=s['revision'],expected_protocol_version=s['protocol_version'],expected_question_approval=s['question_approval'],expected_criteria_sha256=s['criteria']['sha256'],**kw)
        doc=dict(eligibility={'study_characteristics':'Synthetic empirical tests','report_characteristics':'Synthetic reports'},
            publication_period={'from':'2020-01-01','to':'2026-12-31','basis':'Synthetic test scope'},
            information_sources=[{'name':'Crossref','kind':'automated','adapter':'crossref'}],
            searches=[{'adapter':'crossref','queries':queries or ['synthetic'],'max_records_per_source':10}],
            selection_process='Independent screening and adjudication',data_items='Study characteristics',
            data_collection_process='Independent verification',risk_of_bias='Appraise design limitations',
            synthesis={'criteria':'Comparable study designs','non_quantitative':'Narrative synthesis'})
        rp.mutate(db,body(action='save',protocol=doc))
        for section in rp.SECTIONS:rp.mutate(db,body(action='approve-section',section=section))
        rp.mutate(db,body(action='approve-final'))
        pilot,_=governed_pilot(db,body(pilot_limit=5),tmp_path/('approved-pilot-'+uuid4().hex))
        rp.mutate(db,body(action='pilot-review',run_id=pilot['run_id'],decision='approve-strategy',notes='Synthetic test pilot reviewed'))
        return body()
    return prepare


def governed_pilot(db, body, output, records='Examples/demo_records.json'):
    """Run a real pilot through run_authorized offline: only the provider call is replaced by a fixture."""
    auth=rp.authorize(db,body,'pilot')
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr('slr.cli.run',lambda config,folder:_fixture_run(config,folder,records))
        result=rp.run_authorized(db,auth,output)
    rp.check_authorization(db,auth)
    rp.record_run(db,auth,result,'complete')
    return auth,result


def defer_protocol(database):
    """Explicit synthetic-test deviation, using the production gate rather than bypassing it."""
    from slr import screening
    import sqlite3
    with sqlite3.connect(database) as conn:
        actor = conn.execute('SELECT adjudicator FROM review').fetchone()[0]
        version = conn.execute('SELECT MAX(version) FROM criteria').fetchone()[0]
    gate = screening.screening_access(database)
    screening.screening_access(database, actor, 'Synthetic regression fixture: protocol deferred to test downstream screening behaviour.', expected_version=version, expected_binding=gate['binding'])
