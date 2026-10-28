import pytest
from slr import questions,question_frameworks as qf
from slr.dashboard import Workspace


@pytest.fixture
def db(tmp_path):
    w=Workspace(tmp_path/'workspace');e=w.create(dict(name='Framework test',question='What works?',criteria='Criteria',reviewers=['A','B'],adjudicator='C'))
    path=e['screening_db'];questions.mutate(path,dict(action='save',actor='A',expected_revision=0,topic='Synthetic',questions=['What works?']))
    yield path
    w.executor.shutdown(wait=True)


def mapping(key='PCC',index=0):
    return dict(question_index=index,framework=key,rationale='Researcher selected this guide for the stated review purpose.',components={k:dict(status='unreviewed',text='') for k in qf.CATALOG[key]['components']})


def mutate(db,action,**kw):
    return questions.mutate(db,dict(actor='A',expected_revision=questions.state(db)['revision'],action=action,**kw))


def test_mapping_changes_require_approval_and_preserve_sources(db):
    mutate(db,'approve')
    state=mutate(db,'frameworks',maps=[mapping()])
    assert not state['approved']
    value=state['current']['content']['draft']['framework_maps'][0]
    assert value['catalog_version']==qf.VERSION and value['guidance']['sources']
    assert value['components']['concept']['status']=='unreviewed'
    assert 'score' not in value
    mutate(db,'approve')
    assert questions.disclosure(db)['approved']
    with pytest.raises(ValueError,match='unchanged'):mutate(db,'save',topic='Synthetic',questions=['What works?'])
    mutate(db,'save',topic='Synthetic',questions=['What works in a different setting?'])
    assert 'framework_maps' not in questions.state(db)['current']['content']['draft']
    assert any('framework_maps' in r['content'].get('draft',{}) for r in questions.state(db)['history'])


def test_manual_mixed_framework_and_custom_maps(db):
    mutate(db,'save',topic='Synthetic',questions=['First question?','Second question?'])
    state=mutate(db,'frameworks',maps=[mapping('PCC',0),mapping('custom',1)])
    assert [m['framework'] for m in state['current']['content']['draft']['framework_maps']]==['PCC','custom']


@pytest.mark.parametrize('case',['unknown','duplicate','boolean-index','missing-component','unsupported-status','empty-rationale'])
def test_invalid_maps_do_not_change_history(db,case):
    m=mapping()
    if case=='unknown':m['framework']='Invented established guide'
    if case=='boolean-index':m['question_index']=True
    if case=='missing-component':m['components'].pop('context')
    if case=='unsupported-status':m['components']['concept']['status']='scientifically valid'
    if case=='empty-rationale':m['rationale']=''
    maps=[m,m] if case=='duplicate' else [m]
    revision=questions.state(db)['revision']
    with pytest.raises(ValueError):mutate(db,'frameworks',maps=maps)
    assert questions.state(db)['revision']==revision


def test_combined_wording_and_mapping_save_has_one_new_draft(db):
    before=questions.state(db)['revision']
    state=mutate(db,'save',topic='Revised topic',questions=['Revised question?'],maps=[mapping()])
    assert state['revision']==before+1
    assert state['current']['content']['draft']['framework_maps'][0]['question_sha256']


def test_mapping_not_silently_sent_to_generic_ai(db):
    mutate(db,'frameworks',maps=[mapping()])
    state=mutate(db,'request',mode='refine',provider='ollama',model='synthetic')
    assert 'framework_maps' not in state['history'][-1]['content']['packet']['packet']['draft']


def test_reasoning_is_preserved_in_verification_bundle(db,tmp_path):
    from slr import replication
    mutate(db,'frameworks',maps=[mapping()]);mutate(db,'approve')
    folder=replication.create(db,tmp_path/'bundle')
    assert replication.verify(folder)['passed']
    import json
    record=json.loads((folder/'ai-assistance-and-revision-record.json').read_text())
    assert record['current']['content']['draft']['framework_maps'][0]['guidance']['sources']


def test_empty_mapping_does_not_create_a_meaningless_draft(db):
    before=questions.state(db)['revision']
    with pytest.raises(ValueError,match='Choose a guide'):mutate(db,'frameworks',maps=[])
    assert questions.state(db)['revision']==before


def test_v2_literal_support_and_context_are_distinct(db):
    m=mapping(); m['components']['concept']=dict(status='identified',text='Interpretation of works',provenance='question_quote',quote='works')
    state=mutate(db,'frameworks',maps=[m]);record=state['current']['content']['draft']['framework_maps'][0]
    assert record['guidance_sha256']==qf.digest(record['guidance'])
    assert record['entry_version']=='2'
    assert record['components']['concept']['quote']=='works'
    m['components']['context']=dict(status='identified',text='Researcher specifies schools beyond question wording',provenance='researcher_context')
    mutate(db,'frameworks',maps=[m])
    m['components']['concept']['quote']='invented population'
    before=questions.state(db)['revision']
    with pytest.raises(ValueError,match='exact substring'):mutate(db,'frameworks',maps=[m])
    assert questions.state(db)['revision']==before


@pytest.mark.parametrize('value',[
    dict(status='identified',text='Unsupported'),
    dict(status='identified',text='Inferred',provenance='ai_inference'),
    dict(status='identified',text='Context',provenance='researcher_context',quote='works'),
])
def test_provenance_cannot_be_implied_or_ai_confirmed(db,value):
    m=mapping();m['components']['concept']=value
    with pytest.raises(ValueError):mutate(db,'frameworks',maps=[m])


def test_named_custom_no_fit_and_unresolved_states(db):
    m=mapping('custom');m['components']={}
    state=mutate(db,'frameworks',maps=[m])
    assert state['framework_reasoning'][0]['state']=='reasoned'
    m['components']={'Setting':dict(status='missing',text='Setting remains to be specified')}
    state=mutate(db,'frameworks',maps=[m])
    assert state['framework_reasoning'][0]['state']=='reasoned-with-unresolved'
    m['components']['Setting']=dict(status='unreviewed',text='')
    assert mutate(db,'frameworks',maps=[m])['framework_reasoning'][0]['state']=='selected-not-reasoned'
    assert mutate(db,'frameworks',maps=[])['framework_reasoning'][0]['state']=='unmapped'


def test_protocol_uses_exact_mixed_question_maps_and_stales_on_amendment(db):
    from slr import protocol, review_plan as rp
    mutate(db,'save',topic='Mixed purpose',questions=['What works?','How is learning experienced?'])
    mutate(db,'frameworks',maps=[mapping('PCC',0),mapping('SPIDER',1)]);mutate(db,'approve')
    # Even the low-level save cannot retain a conflicting global PICO claim.
    protocol.save(db,dict(objectives=dict(question='What works?\nHow is learning experienced?',framework='PICO',elements={'population':'Invented'})), 'A',expected_version=0)
    doc=protocol.state(db)['protocol'];maps=questions.state(db)['current']['content']['draft']['framework_maps']
    assert doc['objectives']==dict(question='What works?\nHow is learning experienced?',framework_records=maps)
    assert rp.state(db)['objectives_current']
    changed=mapping('PCC',0);changed['rationale']='A revised rationale requiring new approval and protocol synchronization.'
    mutate(db,'frameworks',maps=[changed,mapping('SPIDER',1)]);mutate(db,'approve')
    assert not rp.state(db)['objectives_current']
    assert protocol.state(db)['protocol']['objectives']['framework_records']==maps
    current=rp.state(db)
    rp.mutate(db,dict(action='save',actor='A',expected_revision=current['revision'],expected_protocol_version=1,
        expected_question_approval=current['question_approval'],expected_criteria_sha256=current['criteria']['sha256'],
        protocol=doc,description='Sync framework reasoning',rationale='Use the newly approved question reasoning'))
    assert rp.state(db)['objectives_current']


def test_bundle_preserves_v2_support_and_explicit_reasoning_states(db,tmp_path):
    from slr import replication
    import json
    m=mapping();m['components']['concept']=dict(status='identified',text='Researcher interpretation',provenance='question_quote',quote='works')
    mutate(db,'frameworks',maps=[m]);mutate(db,'approve')
    bundle=replication.create(db,tmp_path/'v2-bundle')
    assert replication.verify(bundle)['passed']
    exported=json.loads((bundle/'ai-assistance-and-revision-record.json').read_text(encoding='utf-8'))
    assert exported['framework_reasoning'][0]['state']=='selected-not-reasoned'
    assert exported['current']['content']['draft']['framework_maps'][0]['components']['concept']['quote']=='works'


def test_legacy_mapping_is_not_retroactively_reasoned(db):
    old={'question_index':0,'question_sha256':__import__('hashlib').sha256(b'What works?').hexdigest(),
         'catalog_version':'question-frameworks-v1','components':{'concept':{'status':'identified','text':'Old statement'}}}
    assert qf.reasoning_state(old)=='legacy-unassessed'
    assert qf.reasoning_records({'questions':['What works?'],'framework_maps':[old]})[0]['state']=='legacy-unassessed'


@pytest.mark.parametrize('key',['PICo','PECO','CoCoPop','PIRD','CIMO','PICOC'])
def test_expanded_guides_are_source_versioned_and_not_compulsory_blocks(db,key):
    state=mutate(db,'frameworks',maps=[mapping(key)])
    m=state['current']['content']['draft']['framework_maps'][0]
    assert m['guidance']['sources'][0]['version']
    assert 'not mandatory' in m['guidance']['search_note']
    assert m['guidance_sha256']==qf.digest(m['guidance'])


def test_v2_bundle_cannot_downgrade_framework_contract(db,tmp_path):
    from slr import replication
    import json
    mutate(db,'frameworks',maps=[mapping()])
    folder=replication.create(db,tmp_path/'downgrade')
    path=folder/replication.MANIFEST;m=json.loads(path.read_text());m.pop('question_framework_contract');path.write_text(json.dumps(m))
    result=replication.verify(folder)
    assert not next(c for c in result['checks'] if c['check']=='framework contract')['passed']
