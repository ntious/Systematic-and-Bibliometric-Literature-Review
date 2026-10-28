import threading
import pytest
from slr.dashboard import Workspace
from slr import questions


def test_question_job_metadata_and_duplicate_guard(tmp_path,monkeypatch):
    w=Workspace(tmp_path/'workspace');release=threading.Event();entered=threading.Event()
    try:
        e=w.create(dict(name='Synthetic',question='What works?',criteria='Criteria',reviewers=['A','B'],adjudicator='C'))
        questions.mutate(e['screening_db'],dict(action='save',actor='A',expected_revision=0,topic='Synthetic topic',questions=['What works?']))
        w.ai.config=dict(mode='local',provider='ollama',model='synthetic:1')
        def run(packet,*args,**kwargs):
            entered.set();assert release.wait(10)
            return dict(provider='ollama',model='synthetic:1',requested_model='synthetic:1',request_id=packet['request_id'],request_sha256=packet['request_sha256'],output={'items':[]})
        monkeypatch.setattr(w.ai,'run_packet',run)
        body=dict(action='request',mode='refine',actor='A',expected_revision=1,selected_provider='ollama',selected_model='synthetic:1')
        job=w.question_action(e['id'],body)
        assert entered.wait(5)
        assert job['task']=='questions' and job['model']=='synthetic:1'
        revision=questions.state(e['screening_db'])['revision']
        with pytest.raises(ValueError,match='already working'):w.question_action(e['id'],body)
        assert questions.state(e['screening_db'])['revision']==revision
        assert w.ai_jobs()['jobs'][0]['status']=='running'
        assert 'session_report' not in w.ai_jobs()['jobs'][0]
    finally:
        release.set();w.executor.shutdown(wait=True)
    assert w.ai_jobs()['jobs'][0]['status']=='complete'


@pytest.mark.parametrize('task',['questions','protocol','evidence'])
def test_any_running_ai_stage_blocks_overlap_but_not_other_review(tmp_path,task):
    w=Workspace(tmp_path/'workspace')
    try:
        w.jobs['synthetic']=dict(id='synthetic',review_id='one',task=task,status='running',stage='Synthetic AI task')
        with pytest.raises(ValueError,match='already working'):w.guard_ai_job('one')
        w.guard_ai_job('two')
        w.jobs['synthetic']['status']='failed'
        w.guard_ai_job('one')
    finally:w.executor.shutdown(wait=True)
