"""Review-bound CLI workflow using the same human approval services as the dashboard."""
import argparse
from collections import Counter
from hashlib import sha256
import json
import os
import shutil
from pathlib import Path
import sqlite3
from uuid import uuid4

from . import questions, review_plan as plan, screening
from .reporting import write_json, write_results


def create_review(database, *, name, reviewers, adjudicator, criteria, topic, research_questions):
    """Create a review before retrieval, preserving a topic-only starting point."""
    draft=questions.draft(topic,research_questions)
    path=Path(database)
    if path.exists():raise ValueError('Review database already exists')
    path.parent.mkdir(parents=True,exist_ok=True)
    folder=path.parent/(path.stem+'-initial-'+uuid4().hex)
    folder.mkdir()
    write_results(folder,[])
    write_json(folder/'manifest.json',{'status':'complete','mode':'empty-review','config':{},'searches':[],
        'files':{p.name:sha256(p.read_bytes()).hexdigest() for p in folder.iterdir()}})
    staged=folder/'initial-ledger.sqlite'
    try:
        screening.initialize(staged,folder,name,reviewers,adjudicator,criteria)
        questions.mutate(staged,{'action':'save','actor':reviewers[0],'expected_revision':0,**draft})
        # Link a complete database on the same filesystem without overwriting a
        # concurrent creator. Do not fall back to a destructive replace.
        os.link(staged,path)
    except Exception:
        shutil.rmtree(folder)  # only the directory created by this attempt
        raise
    staged.unlink()
    return {'db':str(path.resolve()),'initial_run':str(folder.resolve()),'questions':question_state(path)}


def question_state(database):
    with screening.connect(database) as conn:
        ledger=conn.execute('SELECT id FROM review').fetchone()[0]
        state=questions._state(questions._rows(conn))
    return {'ledger_id':ledger,**state}


def context_body(database, context_file, actor):
    """Use the state the user inspected, never silently fetch fresh approval identities."""
    state=json.loads(Path(context_file).read_text(encoding='utf-8-sig'))
    if not isinstance(state,dict):raise ValueError('Context file must contain inspected plan status')
    with screening.connect(database) as conn:
        ledger=conn.execute('SELECT id FROM review').fetchone()[0]
    if state.get('ledger_id')!=ledger:
        raise ValueError('Context belongs to a different review ledger; inspect the intended review')
    return {'actor':actor,'expected_revision':state['revision'],'expected_protocol_version':state['protocol_version'],
            'expected_question_approval':state['question_approval'],'expected_criteria_sha256':state['criteria']['sha256']}


def register_main(database, run):
    """Populate an empty ledger in place; retain its identity and every history table."""
    folder=Path(run).resolve()
    rows,counts,manifest=screening.verify_run(folder)
    auth=manifest.get('authorization')
    if manifest.get('mode')!='approved-main' or not isinstance(auth,dict) or auth.get('kind')!='main':
        raise ValueError('Only an authorized main search can populate this review; imported external collections use the intake route')
    if manifest.get('config')!=auth.get('plan'):
        raise ValueError('Run configuration differs from its authorization')
    # The transaction prevents a concurrent amendment between approval validation and registration.
    with screening.connect(database) as conn:
        plan._check_authorization(conn,auth)
        if conn.execute('SELECT 1 FROM records').fetchone() or conn.execute('SELECT 1 FROM events').fetchone():
            raise ValueError('This review already has a corpus or decisions; existing work is preserved')
        if not any(r['kind']=='run-start' and r['content']['authorization_sequence']==auth['sequence'] for r in plan._events(conn)):
            raise ValueError('This authorization has not executed through the governed retrieval service')
        # Verify again before changing ledger state; no source path is opened from model output.
        screening.verify_run(folder)
        retrieved=json.loads((folder/'retrieved.json').read_text())
        counts['identified_by_source']=dict(Counter(r['source'] for r in retrieved))
        for i,row in enumerate(rows,1):
            conn.execute('INSERT INTO records VALUES (?,?)',(f'R{i:06d}',json.dumps(row,ensure_ascii=False)))
        conn.execute('UPDATE review SET identification=?,origin=?',(json.dumps(counts),json.dumps(manifest)))
        content={'run_id':auth['run_id'],'authorization_sequence':auth['sequence'],
            'binding':{k:v for k,v in auth['binding'].items() if k in ('question_approval','criteria_sha256','strategy_sha256')},
            'path':str(folder),'manifest_sha256':sha256((folder/'manifest.json').read_bytes()).hexdigest(),
            'status':'complete','error':''}
        event=next(r for r in plan._events(conn) if r['sequence']==auth['sequence'])
        plan._append(conn,'main-run',event['actor'],content)
    return {'records':len(rows),'db':str(Path(database).resolve()),'run':str(folder),'registered':True}


def run_review(database, body, kind, output):
    # Refuse a nonempty main review before spending provider quota.
    if Path(output).exists():raise ValueError('Output directory already exists; choose a new session directory')
    if kind=='main':
        with screening.connect(database) as conn:
            if conn.execute('SELECT 1 FROM records').fetchone() or conn.execute('SELECT 1 FROM events').fetchone():
                raise ValueError('Main search requires an empty review; existing work is preserved')
    auth=plan.authorize(database,body,kind)
    result=None
    try:
        result=plan.run_authorized(database,auth,output)
        if kind=='main':return register_main(database,result)
        plan.check_authorization(database,auth)
        plan.record_run(database,auth,result,'complete')
        return {'run_id':auth['run_id'],'kind':kind,'run':str(result),'registered':False}
    except Exception as exc:
        reason=str(exc) if isinstance(exc,(ValueError,OSError,RuntimeError)) else type(exc).__name__
        plan.record_run(database,auth,result or Path(output)/'retrieval','failed',error=reason)
        raise


def _emit(value, output=None):
    serialized=json.dumps(value,ensure_ascii=False,indent=2)+'\n'
    if output:
        # Status files may contain private research context; refuse accidental overwrite.
        with Path(output).open('x',encoding='utf-8') as handle:handle.write(serialized)
    print(serialized,end='')


def questions_main(argv=None):
    parser=argparse.ArgumentParser(prog='slr questions',description='Versioned manual topic/questions and explicit approval')
    sub=parser.add_subparsers(dest='command',required=True)
    status=sub.add_parser('status');status.add_argument('--output')
    save=sub.add_parser('save');save.add_argument('--file',required=True,help='JSON object: topic and questions')
    approve=sub.add_parser('approve')
    for item in (save,approve):
        item.add_argument('--actor',required=True);item.add_argument('--expected-revision',type=int,required=True)
    for item in sub.choices.values():item.add_argument('--db',required=True)
    args=parser.parse_args(argv)
    try:
        if args.command=='status':_emit(question_state(args.db),args.output)
        else:
            payload=json.loads(Path(args.file).read_text(encoding='utf-8-sig')) if args.command=='save' else {}
            if not isinstance(payload,dict) or set(payload)-{'topic','questions'}:raise ValueError('Question draft file accepts only topic and questions')
            _emit(questions.mutate(args.db,payload|{'action':args.command,'actor':args.actor,'expected_revision':args.expected_revision}))
    except (ValueError,OSError,TypeError,KeyError,sqlite3.DatabaseError) as exc:parser.exit(1,f'slr questions: {exc}\n')
    return 0


def main(argv=None):
    parser=argparse.ArgumentParser(prog='slr plan',description=__doc__)
    sub=parser.add_subparsers(dest='command',required=True)
    status=sub.add_parser('status');status.add_argument('--output',help='New private JSON status/context file')
    inspect=sub.add_parser('inspect-pilot');inspect.add_argument('--run-id',required=True)
    save=sub.add_parser('save');save.add_argument('--file',required=True);save.add_argument('--description');save.add_argument('--rationale')
    section=sub.add_parser('approve-section');section.add_argument('--section',choices=list(plan.SECTIONS),required=True)
    na=sub.add_parser('not-applicable');na.add_argument('--section',choices=list(plan.NA_SECTIONS),required=True);na.add_argument('--rationale',required=True)
    sub.add_parser('approve-final')
    revoke=sub.add_parser('revoke');revoke.add_argument('--target',type=int,required=True);revoke.add_argument('--rationale',required=True)
    pilot=sub.add_parser('review-pilot');pilot.add_argument('--run-id',required=True);pilot.add_argument('--decision',choices=['approve-strategy','revise'],required=True);pilot.add_argument('--notes',required=True)
    run=sub.add_parser('run');run.add_argument('--kind',choices=['pilot','main'],required=True);run.add_argument('--pilot-limit',type=int,default=5);run.add_argument('--output',required=True)
    for name,item in sub.choices.items():
        item.add_argument('--db',required=True)
        if name not in ('status','inspect-pilot'):item.add_argument('--actor',required=True);item.add_argument('--context',required=True,help='Plan status JSON you inspected; stale identities are rejected')
    args=parser.parse_args(argv)
    try:
        if args.command=='status':_emit(plan.state(args.db),args.output)
        elif args.command=='inspect-pilot':_emit(plan.inspect_pilots(args.db,args.run_id))
        else:
            body=context_body(args.db,args.context,args.actor)
            if args.command=='run':_emit(run_review(args.db,body|{'pilot_limit':args.pilot_limit},args.kind,args.output))
            else:
                action={'review-pilot':'pilot-review','revoke':'revoke'}.get(args.command,args.command)
                body['action']=action
                for attr in ('section','rationale','description','run_id','decision','notes'):
                    if hasattr(args,attr) and getattr(args,attr) is not None:body[attr]=getattr(args,attr)
                if args.command=='revoke':body['target_sequence']=args.target
                if args.command=='save':body['protocol']=json.loads(Path(args.file).read_text(encoding='utf-8-sig'))
                _emit(plan.mutate(args.db,body))
    except (ValueError,OSError,TypeError,KeyError,RuntimeError,sqlite3.DatabaseError) as exc:parser.exit(1,f'slr plan: {exc}\n')
    return 0
