import json
import pytest
from slr import local_ai, knowledge_ai
from slr.evidence_ai import ModelError


@pytest.mark.parametrize('url',['https://api.example.com','http://example.com:11434','http://127.0.0.1:11434/path','http://a:b@localhost:11434','http://localhost:11434?x=1'])
def test_remote_or_ambiguous_endpoint_rejected(url):
    with pytest.raises(ValueError):local_ai.endpoint(url)


def test_local_route_needs_no_api_key_and_preserves_questions(monkeypatch,tmp_path):
    monkeypatch.delenv('OPENAI_API_KEY',raising=False)
    calls=[]
    def fake(url,body=None,timeout=10):
        calls.append((url,body))
        if url.endswith('/tags'):return {'models':[{'name':'local:test','digest':'sha-test'}]}
        if url.endswith('/show'):return {}
        return {'done':True,'done_reason':'stop','model':'local:test','message':{'content':'{"items":[]}'}}
    monkeypatch.setattr(local_ai,'local_json',fake)
    monkeypatch.setattr(knowledge_ai,'run_packet',lambda *a,**k:pytest.fail('Cloud called'))
    cases=[dict(case_id='X',question='Which methods are used?',cohort='x',discipline='x',anchors=[{'quote':'question'}],paper='SECRET.pdf')]
    plan=knowledge_ai.prepare(cases)
    knowledge_ai.run(plan,'local:test',tmp_path/'run',provider='ollama')
    knowledge_ai.run(plan,'local:test',tmp_path/'run',provider='ollama')
    chats=[b for u,b in calls if u.endswith('/chat')]
    assert len(chats)==1
    assert json.loads(chats[0]['messages'][1]['content'])=={'questions':'Which methods are used?'}
    assert chats[0]['tools']==[] and 'SECRET' not in json.dumps(chats)
    response=json.loads((tmp_path/'run/Q001/response.json').read_text())
    assert response['provider']=='ollama' and response['model_digest']=='sha-test'
    assert knowledge_ai.worksheet(plan,tmp_path/'run')['entries']==[]


@pytest.mark.parametrize('metadata',[{'name':'llama:cloud','digest':'x'},{'name':'llama:local','digest':'x','remote_host':'cloud.example'}])
def test_cloud_backed_model_rejected(monkeypatch,metadata):
    monkeypatch.setattr(local_ai,'local_json',lambda u,*a,**k:{'models':[metadata]} if u.endswith('/tags') else {})
    with pytest.raises(ValueError,match='Cloud-backed'):local_ai.installed_model('http://localhost:11434',metadata['name'])


def test_failed_local_generation_recorded_without_cloud_retry(monkeypatch,tmp_path):
    def fake(url,body=None,timeout=10):
        if url.endswith('/tags'):return {'models':[{'name':'local:test','digest':'x'}]}
        if url.endswith('/show'):return {}
        return {'done':True,'done_reason':'length','message':{'content':'{"items":[]}'}}
    monkeypatch.setattr(local_ai,'local_json',fake)
    plan=knowledge_ai.prepare([dict(case_id='X',question='Which methods?',cohort='x',discipline='x',anchors=[{'quote':'question'}])])
    with pytest.raises(ModelError,match='incomplete'):knowledge_ai.run(plan,'local:test',tmp_path/'run',provider='ollama')
    assert json.loads((tmp_path/'run/Q001/manifest.json').read_text())['status']=='failed'
    assert not (tmp_path/'run/Q001/response.json').exists()
