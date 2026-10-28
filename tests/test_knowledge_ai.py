import json

import pytest

from slr import knowledge_ai as ai
from slr import evidence_ai
from slr.knowledge_evaluation import write_bundle


def cases():
    return [dict(case_id='P1',question='Which methods are used?',cohort='core',discipline='x',
                 anchors=[{'quote':'Which methods are used?'}],paper='SECRET_TITLE.pdf',observed_methods=['SECRET_LABEL'])]


def proposal():
    return {'items':[dict(method_name='Category counts',rationale='Describe methods',required_data=['Coded method categories'],inappropriate_when='Categories overlap without handling',uncertainty='medium')]}


def test_provider_packet_excludes_metadata_and_labels():
    plan=ai.prepare(cases())
    packet=plan['packets'][0]['packet']
    assert set(packet)=={'instructions','questions','response_schema'}
    assert packet['questions']==cases()[0]['question']
    assert 'SECRET' not in json.dumps(packet)
    ai.validate_plan(plan)


@pytest.mark.parametrize('field',['questions','instructions','response_schema'])
def test_plan_tampering_rejected(field):
    plan=ai.prepare(cases());plan['packets'][0]['packet'][field]='changed'
    with pytest.raises(ValueError,match='binding'):ai.validate_plan(plan)


def test_missing_key_makes_no_request_or_run_dir(monkeypatch,tmp_path):
    monkeypatch.delenv('OPENAI_API_KEY',raising=False)
    monkeypatch.setattr(ai,'run_packet',lambda *a,**k:pytest.fail('Network attempted'))
    with pytest.raises(ValueError,match='no model calls'):ai.run(ai.prepare(cases()),'test',tmp_path/'run')
    assert not (tmp_path/'run').exists()


def test_completed_run_resumes_without_repeating_model_calls(monkeypatch,tmp_path):
    monkeypatch.setenv('OPENAI_API_KEY','test-only')
    plan=ai.prepare(cases());calls=[]
    def fake(packet,model,folder,**kwargs):
        calls.append(packet)
        envelope=dict(request_sha256=packet['request_sha256'],requested_model=model,output=proposal())
        write_bundle(folder,{'response.json':envelope})
        manifest=folder/'manifest.json';m=json.loads(manifest.read_text());m['status']='complete';manifest.write_text(json.dumps(m))
        return envelope
    monkeypatch.setattr(ai,'run_packet',fake)
    ai.run(plan,'test',tmp_path/'run');ai.run(plan,'test',tmp_path/'run')
    assert len(calls)==1
    sheet=ai.worksheet(plan,tmp_path/'run')
    assert sheet['entries'][0]['researcher_judgment']=='pending'
    assert sheet['entries'][0]['mapped_method_ids']==[]
    with pytest.raises(ValueError,match='different experiment'):ai.run(plan,'other',tmp_path/'run')


def test_invalid_output_rejected():
    for value in ({'items':[{}]},{'items':[proposal()['items'][0]]*7},{'items':[],'extra':True}):
        with pytest.raises(ValueError):ai.validate_output(value)
    assert ai.validate_output({'items':[]})=={'items':[]}


def test_actual_adapter_sends_questions_only_and_no_tools(monkeypatch,tmp_path):
    monkeypatch.setenv('OPENAI_API_KEY','test-only')
    captured=[]
    class Response:
        def __enter__(self):return self
        def __exit__(self,*a):pass
        def read(self):return json.dumps({'status':'completed','model':'test','output':[{'type':'message','content':[{'type':'output_text','text':json.dumps(proposal())}]}]}).encode()
    def fake(request,timeout):
        captured.append(json.loads(request.data));return Response()
    monkeypatch.setattr(evidence_ai,'urlopen',fake)
    plan=ai.prepare(cases());ai.run(plan,'test',tmp_path/'run')
    body=captured[0]
    assert json.loads(body['input'])=={'questions':cases()[0]['question']}
    assert body['tools']==[] and body['store'] is False
    assert 'SECRET' not in json.dumps(body)


def test_failed_call_is_not_retried(monkeypatch,tmp_path):
    monkeypatch.setenv('OPENAI_API_KEY','test-only')
    plan=ai.prepare(cases());root=tmp_path/'run';root.mkdir()
    (root/'experiment.json').write_text(json.dumps(dict(plan_sha256=ai.digest(plan),model='test',max_output_tokens=2048)))
    folder=root/'Q001';folder.mkdir();(folder/'manifest.json').write_text('{"status":"failed"}')
    monkeypatch.setattr(ai,'run_packet',lambda *a,**k:pytest.fail('Retried'))
    with pytest.raises(ValueError,match='inspect usage'):ai.run(plan,'test',root)


def test_three_arm_comparison_keeps_semantic_mapping_pending(monkeypatch,tmp_path):
    from slr.analysis_knowledge import seed
    from slr.knowledge_evaluation import predict
    monkeypatch.setenv('OPENAI_API_KEY','test-only')
    plan=ai.prepare(cases())
    class Response:
        def __enter__(self):return self
        def __exit__(self,*a):pass
        def read(self):return json.dumps({'status':'completed','model':'test','output':[{'type':'message','content':[{'type':'output_text','text':json.dumps(proposal())}]}]}).encode()
    monkeypatch.setattr(evidence_ai,'urlopen',lambda *a,**kw:Response())
    ai.run(plan,'test',tmp_path/'run')
    annotations=[dict(case_id='P1',observed_method_ids=['category-counts'],annotator='provisional',anchors=[{'quote':'counts'}])]
    baseline=predict(seed(),cases())
    comparison=ai.compare(plan,tmp_path/'run',baseline,annotations)
    result=comparison['comparison.json']
    assert result['ontology_updated'] is False
    assert result['ai_agreement_status']=='pending_review'
    assert result['rows'][0]['ai_proposals'][0]['proposal']['method_name']=='Category counts'
    assert result['rows'][0]['reported_methods']['observed_method_ids']==['category-counts']
    # Extra source fields in cases cannot alter provider input, but must invalidate baseline binding.
    baseline['cases_sha256']='other'
    with pytest.raises(ValueError,match='exactly'):ai.compare(plan,tmp_path/'run',baseline,annotations)
    path=tmp_path/'run'/'Q001'/'response.json';path.write_text('{}')
    with pytest.raises(ValueError,match='hash'):ai.worksheet(plan,tmp_path/'run')


def test_continue_mode_counts_failures_separately_and_never_retries(monkeypatch,tmp_path):
    monkeypatch.setenv('OPENAI_API_KEY','test-only')
    data=cases();second=dict(data[0],case_id='P2',question='Which outcomes are reported?');data.append(second)
    plan=ai.prepare(data);calls=[]
    def fake(packet,model,folder,**kwargs):
        calls.append(packet['request_id'])
        if packet['request_id']=='Q001':
            folder.mkdir();(folder/'manifest.json').write_text(json.dumps(dict(status='failed',request_sha256=packet['request_sha256'],requested_model=model,provider='openai')))
            raise ValueError('Required explanation was empty')
        result=dict(provider='openai',request_sha256=packet['request_sha256'],requested_model=model,output=proposal())
        write_bundle(folder,{'response.json':result})
        p=folder/'manifest.json';m=json.loads(p.read_text());m['status']='complete';p.write_text(json.dumps(m))
        return result
    monkeypatch.setattr(ai,'run_packet',fake)
    ai.run(plan,'test',tmp_path/'run',continue_on_error=True)
    ai.run(plan,'test',tmp_path/'run',continue_on_error=True)
    assert calls==['Q001','Q002']
    summary=json.loads((tmp_path/'run/run-summary.json').read_text())
    assert summary['status']=='partial' and summary['failed_requests']==['Q001'] and summary['completed_requests']==['Q002']
    sheet=ai.worksheet(plan,tmp_path/'run')
    assert len(sheet['failed_requests'])==1
    assert {e['case_id'] for e in sheet['entries']}=={'P2'}


def test_failed_request_cannot_be_substituted_in_comparison(tmp_path):
    plan=ai.prepare(cases());root=tmp_path/'run';root.mkdir()
    (root/'experiment.json').write_text(json.dumps(dict(plan_sha256=ai.digest(plan),model='test',max_output_tokens=2048)))
    folder=root/'Q001';folder.mkdir();(folder/'manifest.json').write_text(json.dumps(dict(status='failed',request_sha256='other-request',requested_model='test')))
    with pytest.raises(ValueError,match='Failed request binding'):
        ai.worksheet(plan,root)
