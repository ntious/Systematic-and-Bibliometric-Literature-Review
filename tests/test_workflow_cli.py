import json
from pathlib import Path

import pytest

from slr import cli, questions, review_plan as plan, screening
from slr.workflow_cli import register_main


@pytest.fixture
def commands(tmp_path,capsys):
    def call(*args):
        result=cli.main([str(a) for a in args]);assert result==0
        return json.loads(capsys.readouterr().out)
    criteria=tmp_path/'criteria.md';criteria.write_text('Include empirical studies')
    db=tmp_path/'review.sqlite'
    create=call('review','create','--db',db,'--name','Synthetic CLI review','--topic','Synthetic learning',
                '--question','How are interventions evaluated?','--reviewers','A','B','--adjudicator','C','--criteria',criteria)
    counter=0
    def context():
        nonlocal counter
        counter+=1
        path=tmp_path/f'context-{counter}.json'
        call('plan','status','--db',db,'--output',path)
        return path
    def action(command,*args):
        return call('plan',command,'--db',db,'--actor','A','--context',context(),*args)
    return call,context,action,db,create


def approve(commands,tmp_path):
    call,_,action,db,_=commands
    call('questions','approve','--db',db,'--actor','A','--expected-revision','1')
    doc=dict(eligibility={'study_characteristics':'Empirical studies','report_characteristics':'English reports'},
        publication_period={'from':'2020-01-01','to':'2026-10-24','basis':'Researcher-defined scope'},
        information_sources=[{'name':'Crossref','kind':'automated','adapter':'crossref'}],
        searches=[{'adapter':'crossref','queries':['synthetic test'],'max_records_per_source':10}],
        selection_process='Independent screening and adjudication',data_items='Study design and outcomes',
        data_collection_process='Extract and independently verify',risk_of_bias='Assess design-specific limitations',
        synthesis={'criteria':'Group by comparable designs','non_quantitative':'Narrative synthesis'})
    file=tmp_path/'protocol.json';file.write_text(json.dumps(doc))
    action('save','--file',file)
    for section in plan.SECTIONS:action('approve-section','--section',section)
    action('approve-final')


def test_cli_full_manual_flow_preserves_same_ledger(commands,tmp_path,monkeypatch):
    call,_,action,db,_=commands
    original=screening.snapshot(db)['review_id']
    approve(commands,tmp_path)
    from slr.cli import run as fixture_run
    calls=[]
    def fixture(config,output):
        calls.append(config)
        return fixture_run(config,output,'Examples/demo_records.json')
    monkeypatch.setattr('slr.cli.run',fixture)
    with pytest.raises(SystemExit):action('run','--kind','main','--output',tmp_path/'refused')
    # The failed command's stderr is separate from JSON stdout; clear it before next command.
    pilot=action('run','--kind','pilot','--pilot-limit','2','--output',tmp_path/'pilot')
    assert not pilot['registered'] and screening.snapshot(db)['prisma']['identified']==0
    assert screening.snapshot(db)['review_id']==original
    preview=call('plan','inspect-pilot','--db',db,'--run-id',pilot['run_id'])
    assert preview[0]['sample'] and preview[0]['config']['tasks'][0]['max_records_per_source']==2
    action('review-pilot','--run-id',pilot['run_id'],'--decision','approve-strategy','--notes','The sample fits the intended scope; source cap reviewed')
    result=action('run','--kind','main','--output',tmp_path/'main')
    assert result['registered'] and result['records']==2 and len(calls)==2
    assert screening.snapshot(db)['review_id']==original
    current=plan.state(db)
    assert current['final_current'] and current['corpus_provenance']=='approved strategy · current'
    assert current['protocol_version']==1 and questions.state(db)['approved']
    assert any(r['kind']=='pilot-review' for r in current['history'])
    assert any(r['kind']=='main-run' for r in current['history'])
    assert not any(r['kind'].startswith('ai-') for r in current['history'])
    with pytest.raises(ValueError):register_main(db,result['run'])
    assert screening.snapshot(db)['prisma']['records_to_screen']==2
    assert screening.screening_access(db)['basis']=='approved-protocol'
    screening.decide(db,'R000001','A','title','include',expected_version=screening.snapshot(db)['criteria_version'])


def test_cli_stale_and_wrong_review_context_refused(commands,tmp_path,capsys):
    call,context,action,db,_=commands
    approve(commands,tmp_path)
    old=context()
    q=questions.state(db)
    questions.mutate(db,dict(actor='A',expected_revision=q['revision'],action='save',topic='Changed topic',questions=['Another question?']))
    q=questions.state(db)
    questions.mutate(db,dict(actor='A',expected_revision=q['revision'],action='approve'))
    with pytest.raises(SystemExit):call('plan','approve-section','--section','synthesis','--db',db,'--actor','A','--context',old)
    assert 'Approved questions changed' in capsys.readouterr().err
    value=json.loads(old.read_text());value['ledger_id']='another-ledger';bad=tmp_path/'other-context.json';bad.write_text(json.dumps(value))
    with pytest.raises(SystemExit):call('plan','approve-final','--db',db,'--actor','A','--context',bad)
    assert 'different review ledger' in capsys.readouterr().err


def test_explicit_unregistered_cli_is_required_and_cannot_register(commands,tmp_path,capsys):
    _,_,_,db,_=commands
    with pytest.raises(SystemExit):cli.main(['--config','configs/example_review.toml','--output',str(tmp_path/'raw')])
    assert '--unregistered' in capsys.readouterr().err
    with pytest.raises(SystemExit):cli.main(['pipeline','--plan','configs/example_pipeline.json','--output',str(tmp_path/'pipeline')])
    assert '--unregistered' in capsys.readouterr().err
    cli.run('configs/example_review.toml',tmp_path/'fixture','Examples/demo_records.json')
    p=tmp_path/'fixture/manifest.json';value=json.loads(p.read_text());value['mode']='live';p.write_text(json.dumps(value))
    with pytest.raises(ValueError,match='authorized main'):register_main(db,tmp_path/'fixture')
    criteria=tmp_path/'criteria.md'
    with pytest.raises(SystemExit):cli.main(['review','init','--db',str(tmp_path/'bypass.sqlite'),'--run',str(tmp_path/'fixture'),
        '--name','Bypass','--reviewers','A','B','--adjudicator','C','--criteria',str(criteria)])
    assert not (tmp_path/'bypass.sqlite').exists()
    assert screening.snapshot(db)['prisma']['identified']==0


def test_create_can_start_with_topic_only_and_never_overwrites(commands,tmp_path,capsys):
    call,_,_,db,_=commands
    before=db.read_bytes()
    with pytest.raises(SystemExit):call('review','create','--db',db,'--name','Other','--topic','Other','--reviewers','A','B','--adjudicator','C','--criteria',tmp_path/'criteria.md')
    capsys.readouterr()
    assert db.read_bytes()==before
    other=tmp_path/'topic-only.sqlite'
    created=call('review','create','--db',other,'--name','Topic only','--topic','Draft topic','--reviewers','A','B','--adjudicator','C','--criteria',tmp_path/'criteria.md')
    assert created['questions']['current']['content']['draft']['questions']==[]
    with pytest.raises(SystemExit):call('questions','approve','--db',other,'--actor','A','--expected-revision','1')
    assert questions.state(other)['approved'] is None


def test_failed_creation_does_not_publish_partial_ledger(tmp_path,monkeypatch):
    from slr.workflow_cli import create_review
    def fail(*args,**kwargs):raise ValueError('Injected question initialization failure')
    monkeypatch.setattr('slr.questions.mutate',fail)
    with pytest.raises(ValueError,match='Injected'):
        create_review(tmp_path/'new.sqlite',name='Test',topic='Topic',research_questions=[],
                      reviewers=['A','B'],adjudicator='C',criteria='Criteria')
    assert not (tmp_path/'new.sqlite').exists()
    assert not list(tmp_path.glob('new-initial-*'))


def test_stale_main_registration_keeps_ledger_empty(commands,tmp_path,monkeypatch):
    call,context,action,db,_=commands
    approve(commands,tmp_path)
    from slr.cli import run as fixture_run
    monkeypatch.setattr('slr.cli.run',lambda config,output:fixture_run(config,output,'Examples/demo_records.json'))
    pilot=action('run','--kind','pilot','--output',tmp_path/'pilot')
    action('review-pilot','--run-id',pilot['run_id'],'--decision','approve-strategy','--notes','Reviewed synthetic sample')
    from slr.workflow_cli import context_body
    auth=plan.authorize(db,context_body(db,context(),'A'),'main')
    run=plan.run_authorized(db,auth,tmp_path/'unregistered-main')
    state=plan.state(db);doc=state['protocol'];doc['title']='Amended before registration'
    plan.mutate(db,{'action':'save','actor':'A','expected_revision':state['revision'],
        'expected_protocol_version':state['protocol_version'],'expected_question_approval':state['question_approval'],
        'expected_criteria_sha256':state['criteria']['sha256'],'protocol':doc,'description':'Change title','rationale':'Test stale registration'})
    with pytest.raises(ValueError,match='historical'):register_main(db,run)
    assert screening.snapshot(db)['prisma']['identified']==0
