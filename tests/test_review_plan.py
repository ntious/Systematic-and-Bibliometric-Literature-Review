from copy import deepcopy
import json
from pathlib import Path

import pytest

from slr import questions, protocol, review_plan as rp, protocol_ai as pa
from slr.dashboard import Workspace
from conftest import governed_pilot


@pytest.fixture
def review(tmp_path):
    w=Workspace(tmp_path/'workspace')
    e=w.create(dict(name='Synthetic review',question='How are interventions evaluated?',criteria='Include empirical evaluations',reviewers=['A','B'],adjudicator='C'))
    yield w,e,e['screening_db']
    w.executor.shutdown(wait=True)


def document():
    return dict(title='Synthetic protocol',eligibility={'study_characteristics':'Include empirical studies; exclude opinion','report_characteristics':'English reports'},
      publication_period={'from':'2020-01-01','to':'2026-10-24','basis':'Researcher selected the intended scope'},
      information_sources=[{'name':'Crossref','kind':'automated','adapter':'crossref'}],
      searches=[{'adapter':'crossref','queries':['synthetic learning'],'max_records_per_source':10}],
      selection_process='Two reviewers screen independently; adjudicator resolves conflicts',
      data_items='Study design, context, outcomes and limitations',data_collection_process='Extract and independently verify',
      risk_of_bias='Design-appropriate appraisal with independent judgments',
      synthesis={'criteria':'Group by comparable settings and study designs','non_quantitative':'Structured narrative synthesis'})


def body(db,**kw):
    state=rp.state(db)
    return dict(actor='A',expected_revision=state['revision'],expected_protocol_version=state['protocol_version'],expected_question_approval=state['question_approval'],expected_criteria_sha256=state['criteria']['sha256'],**kw)


def mutate(db,action,**kw):
    return rp.mutate(db,body(db,action=action,**kw))


def approved(db):
    questions.mutate(db,dict(actor='A',expected_revision=0,action='save',topic='Synthetic research',questions=['How are interventions evaluated?']))
    questions.mutate(db,dict(actor='A',expected_revision=1,action='approve'))
    mutate(db,'save',protocol=document())
    for section in rp.SECTIONS:mutate(db,'approve-section',section=section)
    return mutate(db,'approve-final')


def test_manual_version_binding_and_question_changes(review):
    _,_,db=review
    state=approved(db)
    assert state['final_current']
    assert not any(r['kind'].startswith('ai-') for r in state['history'])
    q=questions.state(db)
    questions.mutate(db,dict(actor='A',expected_revision=q['revision'],action='save',topic='Changed topic',questions=['New question?']))
    assert not rp.state(db)['final_current']
    assert not any(s['current'] for s in rp.state(db)['sections'].values())
    with pytest.raises(ValueError,match='current final'):
        rp.authorize(db,body(db,pilot_limit=5),'pilot')


def test_section_and_final_invalidation_are_content_bound(review):
    _,_,db=review
    approved(db)
    doc=rp.state(db)['protocol'];doc['risk_of_bias']='Revised appraisal procedure'
    result=mutate(db,'save',protocol=doc,description='Appraisal update',rationale='Clarify the procedure')
    assert not result['final_current'] and not result['sections']['appraisal']['current']
    assert result['sections']['search']['current']
    mutate(db,'approve-section',section='appraisal')
    assert mutate(db,'approve-final')['final_current']
    # WA-02: criteria change only through an eligibility amendment once a guided protocol exists.
    doc=rp.state(db)['protocol'];doc['eligibility']['study_characteristics']='Revised empirical scope'
    result=mutate(db,'save',protocol=doc,description='Eligibility update',rationale='Narrow the empirical scope')
    assert not result['final_current'] and not result['sections']['eligibility']['current'] and not result['sections']['search']['current']


def test_stale_approval_and_na_rationale_and_bad_sources(review):
    _,_,db=review
    approved(db)
    old=body(db,action='approve-final')
    mutate(db,'not-applicable',section='appraisal',rationale='No primary empirical studies are assessed in this review')
    with pytest.raises(ValueError,match='history changed'):
        rp.mutate(db,old)
    with pytest.raises(ValueError,match='cannot be not applicable'):
        mutate(db,'not-applicable',section='sources',rationale='This is not relevant to the review')
    with pytest.raises(ValueError,match='20 characters'):
        mutate(db,'not-applicable',section='synthesis',rationale='No')
    doc=document();doc['information_sources'][0]['adapter']='scopus';doc['searches'][0]['adapter']='scopus'
    with pytest.raises(ValueError,match='Unsupported automated'):
        rp.executable(doc)
    with pytest.raises(ValueError,match='bound'):
        rp.authorize(db,body(db,pilot_limit=101),'pilot')


def fake_pilot(db,tmp_path):
    return governed_pilot(db,body(db,pilot_limit=5),tmp_path/'pilot')[0]


def test_pilot_completion_needs_human_review_and_revocation_blocks_main(review,tmp_path):
    _,_,db=review
    approved(db)
    pilot=fake_pilot(db,tmp_path)
    with pytest.raises(ValueError,match='Review and approve'):
        rp.authorize(db,body(db),'main')
    mutate(db,'pilot-review',run_id=pilot['run_id'],decision='approve-strategy',notes='Sample fits the intended question and scope')
    auth=rp.authorize(db,body(db),'main')
    assert rp.check_authorization(db,auth)['tasks'][0]['max_records_per_source']==10
    reviewevent=[r for r in rp.state(db)['history'] if r['kind']=='pilot-review'][-1]
    mutate(db,'revoke',target_sequence=reviewevent['sequence'],rationale='Need to check missing relevant work')
    with pytest.raises(ValueError,match='no longer current'):
        rp.check_authorization(db,auth)


def test_history_survives_corpus_replacement_with_protocol_and_criteria(review):
    import base64
    w,e,db=review
    approved(db)
    before=rp.state(db)
    records=[{'source':'synthetic','source_id':'1','title':'Synthetic evaluation'}]
    w.import_uploads(e['id'],{'source':'synthetic','files':[{'name':'records.json','base64':base64.b64encode(json.dumps(records).encode()).decode()}]})
    current=rp.state(w.entry(e['id'])['screening_db'])
    assert current['history']==before['history'] and current['protocol']==before['protocol'] and current['final_current']


def request(db,section='appraisal'):
    return pa.request(db,body(db,section=section),{'mode':'local','provider':'ollama','model':'test'})


def envelope(packet,items):
    return dict(provider='ollama',requested_model='test',model='test',request_id=packet['request_id'],request_sha256=packet['request_sha256'],output={'items':items})


def test_protocol_ai_is_section_scoped_and_never_approves(review):
    _,_,db=review
    approved(db)
    packet=request(db)
    assert packet['packet']['prompt_version']==pa.VERSION
    assert packet['packet']['allowed_fields']==['risk_of_bias']
    assert 'publication_period' not in packet['packet']['section_draft']
    item=dict(field='risk_of_bias',value='Revised appraisal instructions',rationale='Clarify the judgments')
    pa.record(db,envelope(packet,[item]))
    state=rp.state(db)
    assert state['final_current']
    seq=state['history'][-1]['sequence']
    result=pa.decide(db,body(db,proposal_sequence=seq,index=0,decision='accept'))
    assert not result['final_current'] and result['protocol']['risk_of_bias']=='Revised appraisal instructions'
    assert result['history'][-1]['kind']=='ai-decision'
    assert result['history'][-1]['content']['previous_value']==document()['risk_of_bias']


def test_invalid_and_stale_ai_and_failure_preserve_draft(review):
    _,_,db=review
    approved(db)
    packet=request(db)
    with pytest.raises(ValueError,match='Invalid or repeated'):
        pa.record(db,envelope(packet,[dict(field='publication_period',value={},rationale='Guess dates')]))
    pa.record(db,envelope(packet,[dict(field='risk_of_bias',value='Candidate',rationale='Clarify')]))
    seq=rp.state(db)['history'][-1]['sequence']
    doc=rp.state(db)['protocol'];doc['title']='Changed title'
    mutate(db,'save',protocol=doc,description='Title edit',rationale='Clearer title')
    with pytest.raises(ValueError,match='changed since'):
        pa.decide(db,body(db,proposal_sequence=seq,index=0,decision='accept'))
    before=rp.state(db)
    pa.failure(db,packet['request_id'],'Synthetic timeout')
    after=rp.state(db)
    assert after['protocol']==before['protocol'] and after['protocol_version']==before['protocol_version']


def test_search_route_refuses_unapproved_and_raw_override(review):
    w,e,db=review
    with pytest.raises(ValueError,match='current final'):
        w.plan_run(e['id'],body(db,pilot_limit=5),'pilot')
    approved(db)
    with pytest.raises(ValueError,match='approved protocol'):
        w.search(e['id'],body(db,query='bypass'))
    with pytest.raises(ValueError,match='Review and approve'):
        w.search(e['id'],body(db))


def test_stale_question_and_criteria_tabs_cannot_reapprove(review):
    _,_,db=review
    approved(db)
    old=body(db,action='approve-section',section='synthesis')
    q=questions.state(db)
    questions.mutate(db,dict(actor='A',expected_revision=q['revision'],action='save',topic='New topic',questions=['New question?']))
    q=questions.state(db)
    questions.mutate(db,dict(actor='A',expected_revision=q['revision'],action='approve'))
    with pytest.raises(ValueError,match='Approved questions changed'):
        rp.mutate(db,old)
    current=body(db,action='approve-section',section='synthesis')
    # A criteria version written outside the protocol (as in historical ledgers) still invalidates a stale view.
    import sqlite3
    from hashlib import sha256
    with sqlite3.connect(db) as conn:
        version=conn.execute('SELECT MAX(version) FROM criteria').fetchone()[0]
        conn.execute('INSERT INTO criteria VALUES (?,?,?,?)',(version+1,'New criteria',sha256(b'New criteria').hexdigest(),'2026-10-25T00:00:00+00:00'))
    with pytest.raises(ValueError,match='Screening criteria changed'):
        rp.mutate(db,current)


def test_source_specific_queries_and_limits_are_not_cross_product(review):
    _,_,db=review
    approved(db)
    doc=rp.state(db)['protocol']
    doc['information_sources'].append({'name':'PubMed','kind':'automated','adapter':'pubmed'})
    doc['searches'].append({'adapter':'pubmed','queries':['distinct pubmed query'],'max_records_per_source':27})
    tasks=rp.executable(doc)['tasks']
    assert tasks[0]['queries']==['synthetic learning'] and tasks[0]['max_records_per_source']==10
    assert tasks[1]['queries']==['distinct pubmed query'] and tasks[1]['max_records_per_source']==27


def test_editing_eligibility_revises_screening_without_deleting_decisions(review):
    from slr import screening
    w,e,db=review
    approved(db)
    old=rp.state(db)
    doc=old['protocol'];doc['eligibility']['report_characteristics']='English and French reports'
    result=mutate(db,'save',protocol=doc,description='Language amendment',rationale='Extend the report scope')
    assert result['criteria']['version']==old['criteria']['version']+1
    assert 'French' in screening.snapshot(db)['criteria']['text']
    assert not result['sections']['eligibility']['current'] and not result['sections']['search']['current']


def test_unauthorized_registration_and_stale_generation_are_blocked(review,tmp_path):
    from slr.cli import run
    from slr.reporting import write_json
    w,e,db=review
    folder=tmp_path/'unbound'
    run('configs/example_review.toml',folder,'Examples/demo_records.json')
    path=folder/'manifest.json'
    manifest=json.loads(path.read_text());manifest['mode']='live';write_json(path,manifest)
    with pytest.raises(ValueError,match='approved main search'):
        w._replace_corpus(e,__import__('slr.screening',fromlist=['snapshot']).snapshot(db),folder,tmp_path/'registration')
    approved(db)
    stale=body(db,section='appraisal')
    q=questions.state(db)
    questions.mutate(db,dict(actor='A',expected_revision=q['revision'],action='save',topic='Another topic',questions=['Another question?']))
    q=questions.state(db)
    questions.mutate(db,dict(actor='A',expected_revision=q['revision'],action='approve'))
    with pytest.raises(ValueError,match='Approved questions changed'):
        pa.request(db,stale,{'mode':'local','provider':'ollama','model':'test'})


@pytest.mark.parametrize('query',['("unterminated', 'term[Title', '(a OR b]', '"unfinished'])
def test_malformed_query_structure_is_refused(query):
    with pytest.raises(ValueError,match='Unbalanced'):
        rp.check_query(query)


def test_protocol_ai_caps_unique_fields_and_rejects_duplicates(review):
    _,_,db=review
    approved(db)
    packet=request(db)
    assert packet['packet']['response_schema']['properties']['items']['maxItems']==1
    item=dict(field='risk_of_bias',value='Appraise design limitations',rationale='Clarify the procedure')
    version=rp.state(db)['protocol_version']
    with pytest.raises(ValueError,match='Invalid or repeated'):
        pa.record(db,envelope(packet,[item,item]))
    assert rp.state(db)['protocol_version']==version and rp.state(db)['final_current']


def test_text_ai_edits_preserve_human_lineage(review):
    _,_,db=review
    approved(db)
    packet=request(db)
    pa.record(db,envelope(packet,[dict(field='risk_of_bias',value='Candidate appraisal',rationale='Clarify the procedure')]))
    seq=rp.state(db)['history'][-1]['sequence']
    result=pa.decide(db,body(db,proposal_sequence=seq,index=0,decision='edit',value='Researcher-defined appraisal procedure'))
    assert result['protocol']['risk_of_bias']=='Researcher-defined appraisal procedure'
    assert result['history'][-1]['content']['decision']=='edit'
    assert not result['final_current']


def test_protocol_cloud_consent_checked_before_request_is_recorded(review):
    w,e,db=review
    approved(db)
    w.ai.config={'mode':'cloud','provider':'openai','model':'test'}
    before=rp.state(db)
    with pytest.raises(ValueError,match='Confirm sending'):
        w.plan_action(e['id'],body(db,action='ai-request',section='appraisal',selected_provider='openai',selected_model='test'))
    assert rp.state(db)['revision']==before['revision']


def test_run_fails_closed_when_protocol_changes_during_retrieval(review,monkeypatch):
    import threading
    w,e,db=review
    approved(db)
    from slr.cli import run as fixture_run
    started,release=threading.Event(),threading.Event()
    def delayed(config,output):
        started.set()
        assert release.wait(10)
        return fixture_run(config,output,'Examples/demo_records.json')
    monkeypatch.setattr('slr.cli.run',delayed)
    job=w.plan_run(e['id'],body(db,pilot_limit=5),'pilot')
    assert started.wait(5)
    try:
        doc=rp.state(db)['protocol'];doc['title']='Revised during retrieval'
        w.plan_action(e['id'],body(db,action='save',protocol=doc,description='Revise title',rationale='Test a stale running authorization'))
    finally:
        release.set()
    w.executor.shutdown(wait=True)
    assert w.jobs[job['id']]['status']=='failed'
    assert w.state(e['id'])['counts']['identified']==0
    assert rp.state(db)['history'][-1]['kind']=='pilot-run'
    assert rp.state(db)['history'][-1]['content']['status']=='failed'


def test_unchanged_ai_suggestion_records_decision_without_fake_amendment(review):
    _,_,db=review
    approved(db)
    before=rp.state(db)
    packet=request(db)
    pa.record(db,envelope(packet,[dict(field='risk_of_bias',value=before['protocol']['risk_of_bias'],rationale='Current wording is suitable')]))
    seq=rp.state(db)['history'][-1]['sequence']
    result=pa.decide(db,body(db,proposal_sequence=seq,index=0,decision='accept'))
    assert result['protocol_version']==before['protocol_version'] and result['final_current']
    assert result['history'][-1]['content']['unchanged'] is True


@pytest.mark.parametrize('before_approval',[False,True])
def test_final_requires_saved_approved_questions(review,before_approval):
    _,_,db=review
    if before_approval:
        doc=document();doc['objectives']={'question':'Unapproved question?'}
        mutate(db,'save',protocol=doc)
        questions.mutate(db,dict(actor='A',expected_revision=0,action='save',topic='Synthetic',questions=['Approved question?']))
        questions.mutate(db,dict(actor='A',expected_revision=1,action='approve'))
    else:
        approved(db)
        revision=questions.state(db)['revision']
        questions.mutate(db,dict(actor='A',expected_revision=revision,action='save',topic='Synthetic',questions=['Different question?']))
        questions.mutate(db,dict(actor='A',expected_revision=revision+1,action='approve'))
    for section in rp.SECTIONS:mutate(db,'approve-section',section=section)
    assert not rp.state(db)['objectives_current']
    with pytest.raises(ValueError,match='carry the approved questions'):mutate(db,'approve-final')
    mutate(db,'save',protocol=rp.state(db)['protocol'],description='Synchronize approved questions',rationale='Carry the current approved questions into the saved protocol.')
    assert mutate(db,'approve-final')['final_current']
