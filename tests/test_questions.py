import json
import sqlite3

import pytest

from slr import questions
from slr.dashboard import Workspace


@pytest.fixture
def review(tmp_path):
    w = Workspace(tmp_path/'workspace')
    e = w.create({'name':'Learning review','question':'What helps learning?', 'criteria':'Empirical research',
                  'reviewers':['A','B'],'adjudicator':'C'})
    yield w, e, e['screening_db']
    w.executor.shutdown(wait=True)


def change(db, action, **kw):
    return questions.mutate(db, dict(actor='A', expected_revision=questions.state(db)['revision'], action=action, **kw))


def save(db, qs=None):
    return change(db, 'save', topic='Learning', questions=qs if qs is not None else ['What helps learning?'])


def proposal(db):
    result = change(db, 'request', mode='refine', provider='ollama', model='test')
    packet = result['history'][-1]['content']['packet']
    assert packet['packet']['prompt_version'] == questions.PROMPT_VERSION
    assert 'questions' not in packet['packet']  # Not the analysis-recommender task.
    envelope = dict(request_id=packet['request_id'], request_sha256=packet['request_sha256'], provider='ollama',
        requested_model='test', model='test', output={'items':[
          {'field':'question','text':'Which interventions support learning?','rationale':'Clarify intervention scope.'},
          {'field':'topic','text':'Learning interventions','rationale':'Clarify scope.'}]})
    return envelope


def test_manual_approval_invalidation_and_append_only(review):
    w,e,db=review
    save(db)
    approved=change(db,'approve')
    original=approved['current']
    assert approved['approved']['content']['sha256']==questions.digest(original['content']['draft'])
    revised=change(db,'save',topic='Learning',questions=['Which interventions help?'])
    assert revised['approved'] is None and revised['last_approval']
    assert revised['history'][0]['content']['draft']==original['content']['draft']
    with sqlite3.connect(db) as conn, pytest.raises(sqlite3.IntegrityError,match='append-only'):
        conn.execute('DELETE FROM question_events')
    with pytest.raises(ValueError,match='history changed'):
        questions.mutate(db,dict(actor='A',expected_revision=0,action='approve'))
    with pytest.raises(ValueError,match='not assigned'):
        questions.mutate(db,dict(actor='unknown',expected_revision=revised['revision'],action='approve'))


def test_ai_proposals_never_approve_or_replace_and_export_lineage(review):
    w,e,db=review
    save(db)
    change(db,'approve')
    envelope=proposal(db)
    state=questions.record_response(db,envelope)
    assert state['approved'] and len(state['current']['content']['draft']['questions'])==1
    sequence=state['history'][-1]['sequence']
    edited=change(db,'decision',proposal_sequence=sequence,index=0,decision='edit',text='Which learning interventions work in schools?')
    assert edited['approved'] is None
    assert edited['current']['content']['origin']=='ai-edited'
    assert len(edited['current']['content']['draft']['questions'])==2
    change(db,'decision',proposal_sequence=sequence,index=1,decision='reject')
    with pytest.raises(ValueError,match='already has a decision'):
        change(db,'decision',proposal_sequence=sequence,index=1,decision='accept')
    result=questions.disclosure(db)
    assert result['history'][0]['content']['origin']=='researcher'
    assert result['history'][-1]['content']['decision']=='reject'
    import io,zipfile
    archive=zipfile.ZipFile(io.BytesIO(w.export(e['id'])))
    exported=json.loads(archive.read('ai-assistance-and-revision-record.json'))
    assert exported==result


def test_malformed_or_stale_response_and_topic_only(review):
    _,_,db=review
    save(db,[])
    with pytest.raises(ValueError,match='at least one'):
        change(db,'approve')
    with pytest.raises(ValueError,match='requires draft'):
        proposal(db)
    save(db)
    envelope=proposal(db)
    envelope['output']['items'][0]['text']=' '
    before=questions.state(db)['revision']
    with pytest.raises(ValueError,match='Suggested text'):
        questions.record_response(db,envelope)
    assert questions.state(db)['revision']==before
    envelope['output']['items'][0]['text']='A candidate question?'
    state=questions.record_response(db,envelope)
    sequence=state['history'][-1]['sequence']
    change(db,'save',topic='Another topic',questions=['Another question?'])
    with pytest.raises(ValueError,match='Draft changed'):
        change(db,'decision',proposal_sequence=sequence,index=0,decision='accept')
    with pytest.raises(ValueError,match='already recorded'):
        questions.record_response(db,envelope)


def test_dashboard_cloud_consent_and_selection_bound_before_request(review,monkeypatch):
    w,e,db=review
    save(db)
    w.ai.config={'mode':'cloud','provider':'openai','model':'test'}
    body=dict(action='request',actor='A',expected_revision=1,mode='generate',selected_provider='openai',selected_model='test')
    with pytest.raises(ValueError,match='Confirm sending'):
        w.question_action(e['id'],body)
    assert questions.state(db)['revision']==1
    with pytest.raises(ValueError,match='selection changed'):
        w.question_action(e['id'],body|{'allow_external':True,'selected_model':'other'})
    def run(packet,folder,**kwargs):
        return dict(request_id=packet['request_id'],request_sha256=packet['request_sha256'],provider='openai',
                    requested_model='test',model='test',output={'items':[]})
    monkeypatch.setattr(w.ai,'run_packet',run)
    job=w.question_action(e['id'],body|{'allow_external':True})
    w.executor.shutdown(wait=True)
    assert w.jobs[job['id']]['status']=='complete'
    assert questions.state(db)['approved'] is None
    assert questions.state(db)['current']['sequence']==1


def test_import_preserves_review_level_question_approval(review):
    import base64
    w,e,db=review
    save(db)
    change(db,'approve')
    before=questions.disclosure(db)
    rows=[dict(source='synthetic',source_id='1',title='Synthetic learning study')]
    w.import_uploads(e['id'],{'source':'synthetic','files':[{'name':'sample.json','base64':base64.b64encode(json.dumps(rows).encode()).decode()}]})
    newdb=w.entry(e['id'])['screening_db']
    assert newdb != db
    assert questions.disclosure(newdb)==before


def test_failed_generation_retains_draft_and_records_session(review,monkeypatch):
    w,e,db=review
    save(db)
    w.ai.config={'mode':'local','provider':'ollama','model':'test'}
    def failed(*args,**kwargs):
        raise ValueError('Synthetic model unavailable')
    monkeypatch.setattr(w.ai,'run_packet',failed)
    job=w.question_action(e['id'],dict(action='request',actor='A',expected_revision=1,mode='refine',
                          selected_provider='ollama',selected_model='test'))
    w.executor.shutdown(wait=True)
    state=questions.state(db)
    assert state['current']['sequence']==1 and state['approved'] is None
    assert [r['kind'] for r in state['history']]==['draft','request']
    assert w.jobs[job['id']]['status']=='failed'
    from pathlib import Path
    assert 'Synthetic model unavailable' in Path(job['session_report']).read_text()


def test_refinement_can_replace_exact_question_with_history(review):
    _,_,db=review
    save(db)
    envelope=proposal(db)
    state=questions.record_response(db,envelope)
    seq=state['history'][-1]['sequence']
    with pytest.raises(ValueError,match='existing question'):
        change(db,'decision',proposal_sequence=seq,index=0,decision='accept',operation='replace',target_index=5)
    result=change(db,'decision',proposal_sequence=seq,index=0,decision='accept',operation='replace',target_index=0)
    assert result['current']['content']['draft']['questions']==['Which interventions support learning?']
    assert result['history'][-1]['content']['replaced_text']=='What helps learning?'
    assert result['history'][0]['content']['draft']['questions']==['What helps learning?']
