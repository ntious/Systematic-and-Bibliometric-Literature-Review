"""Private verification bundles. Hash checks are integrity checks, not signatures."""
import argparse
from contextlib import closing
from hashlib import sha256
import json
from pathlib import Path, PurePosixPath
import shutil
import sqlite3
import tempfile
import zipfile

from . import __version__, screening, questions, review_plan, ai_disclosure, manuscript
from .review_cli import export_review
from .question_frameworks import VERSION as FRAMEWORK_CONTRACT

MANIFEST = 'bundle-manifest.json'
LIMIT = 1024 * 1024 * 1024
NOTICE = ('Private review bundle: includes local reviewer labels, metadata, decision history and any recorded AI inputs. '
          'Inspect before sharing. Hashes do not authenticate people or prevent a complete rewrite. '
          'Searches and AI are not rerun; external results may change. Local source paths may remain in historical evidence.')


def backup(source, target):
    with closing(sqlite3.connect(Path(source).resolve(strict=True).as_uri()+'?mode=ro',uri=True)) as src:
        with closing(sqlite3.connect(target)) as dest:
            src.backup(dest)


def seal(folder):
    folder=Path(folder)
    files={p.relative_to(folder).as_posix():sha256(p.read_bytes()).hexdigest()
           for p in sorted(folder.rglob('*')) if p.is_file() and p.name!=MANIFEST}
    manifest={'schema':'litatlas-verification-bundle-v1','software_version':__version__,
              'question_framework_contract':FRAMEWORK_CONTRACT,
              'notice':NOTICE,'files':files,
              'levels':{'verifiable':'listed files checked against SHA-256',
                        'replayable':'recorded SQLite/JSON histories inspectable; completeness not certified',
                        're_executable':'screening counts/agreement and report render only; retrieval and AI not rerun'}}
    (folder/MANIFEST).write_text(json.dumps(manifest,sort_keys=True,indent=2)+'\n',encoding='utf-8')
    return manifest


def create(database, output, evidence_database=None):
    folder=Path(output)
    folder.mkdir(parents=True,exist_ok=False)
    try:
        backup(database,folder/'screening.sqlite')
        frozen=folder/'screening.sqlite'
        # Readers may add empty legacy tables; finish all derived exports before hashing.
        export_review(frozen,folder/'screening')
        (folder/'protocol-approval-history.json').write_text(json.dumps(review_plan.state(frozen),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        from . import protocol
        if protocol.state(frozen)['version']:
            protocol.export(folder/'protocol', database=frozen)
        (folder/'ai-assistance-and-revision-record.json').write_text(json.dumps(questions.disclosure(frozen),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        evidence=None
        if evidence_database:
            evidence=folder/'evidence.sqlite'
            backup(evidence_database,evidence)
            from .evidence_cli import export_evidence
            export_evidence(evidence,folder/'evidence')
        ai=ai_disclosure.capture(frozen,evidence)
        (folder/'ai-disclosure.json').write_text(json.dumps(ai,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        manuscript.export(manuscript.capture(frozen,evidence_database=evidence),folder/'methods')
        (folder/'README.txt').write_text(NOTICE+'\n\nVerify with: slr verify PATH_TO_BUNDLE\nNo models, credentials, runtime folders or external PDFs are copied automatically.\n',encoding='utf-8')
        seal(folder)
    except BaseException:
        shutil.rmtree(folder)
        raise
    return folder


def _safe(name):
    p=PurePosixPath(name)
    if not name or p.is_absolute() or '\\' in name or ':' in name or any(s in ('','.','..') for s in name.split('/')):
        raise ValueError('Unsafe bundle path')


def _read(path):
    path=Path(path)
    if path.is_dir():
        entries=[p for p in path.rglob('*')]
        if any(p.is_symlink() for p in entries):raise ValueError('Bundle symlinks are not supported')
        files=[p for p in entries if p.is_file()]
        if len(files)>10000 or sum(p.stat().st_size for p in files)>LIMIT:raise ValueError('Bundle exceeds verification limits')
        return {p.relative_to(path).as_posix():p.read_bytes() for p in files}
    with zipfile.ZipFile(path) as z:
        entries=[i for i in z.infolist() if not i.is_dir()]
        if len(entries)>10000 or sum(i.file_size for i in entries)>LIMIT:raise ValueError('Bundle exceeds verification limits')
        if len({i.filename for i in entries})!=len(entries):raise ValueError('Duplicate ZIP paths')
        for i in entries:
            _safe(i.filename)
            if (i.external_attr>>16)&0o170000==0o120000:raise ValueError('Bundle symlinks are not supported')
        return {i.filename:z.read(i) for i in entries}


def verify(path):
    files=_read(path)
    for name in files:_safe(name)
    manifest=json.loads(files[MANIFEST])
    if manifest.get('schema')!='litatlas-verification-bundle-v1':raise ValueError('Unsupported bundle schema')
    expected=manifest['files']
    if not isinstance(expected,dict):raise ValueError('Invalid bundle file manifest')
    for name in expected:_safe(name)
    checks=[]
    def check(name,passed,detail):checks.append({'check':name,'passed':bool(passed),'detail':detail})
    check('file inventory',set(files)==set(expected)|{MANIFEST},'Missing and unlisted files are rejected')
    for name,digest in expected.items():check(name,name in files and sha256(files[name]).hexdigest()==digest,'SHA-256')
    required={'ai-disclosure.json','protocol-approval-history.json','ai-assistance-and-revision-record.json','screening.sqlite','screening/review.json','methods/report-inputs.json','methods/methods.md','methods/report-provenance.json'}
    check('required artifacts',required<=set(expected),'Frozen ledger, screening export and report inputs')
    if all(c['passed'] for c in checks):
        with tempfile.TemporaryDirectory(prefix='litatlas-verify-') as temp:
            db=Path(temp)/'screening.sqlite';db.write_bytes(files['screening.sqlite'])
            # Reading cannot load extensions; only the known application queries run.
            try:
                actual=screening.snapshot(db)
                check('screening replay',actual==json.loads(files['screening/review.json']),'Counts, agreement, criteria and events recomputed from the bundled ledger')
                inputs=json.loads(files['methods/report-inputs.json'])
                check('report screening binding',inputs['screening']==actual,'Report inputs match the bundled screening ledger')
                outputs=manuscript.render(inputs)
                check('methods replay',all(files.get('methods/'+k)==v.encode('utf-8') for k,v in outputs.items()),'All deterministic report outputs recomputed')
                evidence_db=None
                if 'evidence.sqlite' in files:
                    evidence_db=Path(temp)/'evidence.sqlite';evidence_db.write_bytes(files['evidence.sqlite'])
                ai=ai_disclosure.capture(db,evidence_db)
                check('AI disclosure binding',ai==json.loads(files['ai-disclosure.json']) and inputs.get('ai_disclosure')==ai,'Summary recomputed from bundled question/protocol and available evidence ledgers')
                recorded_questions=json.loads(files['ai-assistance-and-revision-record.json'])
                replayed_questions=questions.disclosure(db)
                legacy=manifest.get('question_framework_contract') is None
                has_v2=any(m.get('catalog_version')==FRAMEWORK_CONTRACT for event in replayed_questions['history'] for m in event['content'].get('draft',{}).get('framework_maps',[]))
                check('framework contract',manifest.get('question_framework_contract')==FRAMEWORK_CONTRACT or (legacy and not has_v2),'Current framework records require the versioned contract; legacy records are not upgraded')
                if legacy and not has_v2:
                    replayed_questions.pop('framework_reasoning',None)
                check('question history binding',replayed_questions==recorded_questions,'Question history and revision disclosure recomputed')
                replayed_plan=review_plan.state(db)
                if legacy and not has_v2:
                    # Replay the original contract only; never used by live authorization.
                    with screening.connect(db) as conn:
                        replayed_plan=review_plan._state(conn, legacy_framework_replay=True)
                check('protocol history binding',replayed_plan==json.loads(files['protocol-approval-history.json']),'Approval state recomputed under the recorded framework contract')
            except (ValueError,KeyError,TypeError,sqlite3.Error) as exc:
                check('semantic replay',False,str(exc))
    return {'schema':'litatlas-verification-result-v1','passed':all(c['passed'] for c in checks),
            'software_version':__version__,'bundle_software_version':manifest.get('software_version'),'fingerprint':sha256(files[MANIFEST]).hexdigest(),'checks':checks,'notice':NOTICE,
            'not_checked':['Authenticity or independent reviewer identities','Completeness of outside AI use or search coverage',
                           'External retrieval files not included','AI regeneration','Scientific validity of evidence judgments']}


def main(argv=None, *, verification=False):
    parser=argparse.ArgumentParser(description=__doc__)
    if verification:parser.add_argument('bundle')
    else:
        parser.add_argument('--db',required=True)
        parser.add_argument('--evidence-db')
        parser.add_argument('--output',required=True)
    args=parser.parse_args(argv)
    try:
        if verification:
            result=verify(args.bundle)
            print(json.dumps(result,indent=2))
            return 0 if result['passed'] else 1
        folder=create(args.db,args.output,args.evidence_db)
        print(json.dumps({'bundle':str(folder),'notice':NOTICE}))
        return 0
    except (ValueError,OSError,KeyError,TypeError,sqlite3.Error,zipfile.BadZipFile) as exc:
        parser.exit(1,f'slr verification bundle: {exc}\n')
