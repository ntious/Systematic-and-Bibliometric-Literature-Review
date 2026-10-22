"""Application-owned multi-query retrieval with durable practical-test sessions."""
import argparse
from collections import Counter
from datetime import date, datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
from uuid import uuid4

from . import __version__
from .models import Record
from .reporting import write_json, write_results
from .screening import verify_run


def now():
    return datetime.now(timezone.utc).isoformat()


class SessionJournal:
    """Rewrite an atomic Markdown/JSON snapshot after every recorded event."""
    def __init__(self, folder, plan):
        self.folder = Path(folder)
        self.folder.mkdir(parents=True, exist_ok=True)
        self.data = {'session_id': uuid4().hex, 'started_utc': now(), 'status': 'running',
                     'plan': plan, 'events': []}
        self.record('session', 'info', 'Pipeline started', evidence='plan.json')

    @classmethod
    def reopen(cls, folder):
        journal = cls.__new__(cls)
        journal.folder = Path(folder)
        journal.data = json.loads((journal.folder / 'session.json').read_text())
        return journal

    def record(self, stage, level, message, *, evidence='', remedy=''):
        self.data['events'].append({'utc': now(), 'stage': stage, 'level': level,
                                    'message': message, 'evidence': evidence, 'remedy': remedy})
        self.save()

    def save(self):
        for name, content in [('session.json', json.dumps(self.data, ensure_ascii=False, indent=2)+'\n'),
                              ('SESSION.md', self.markdown())]:
            path = self.folder / name
            temp = path.with_suffix(path.suffix+'.tmp')
            temp.write_text(content, encoding='utf-8')
            temp.replace(path)

    def markdown(self):
        d = self.data
        lines = ['# Pipeline practical-test session', '', f"Session: `{d['session_id']}`", '',
                 f"Started (UTC): {d['started_utc']}", '', f"Status: **{d['status']}**", '',
                 'The software executes retrieval, verification, deduplication and provisional analysis. Human screening and evidence approval are not automated.', '',
                 '## Events, errors and lessons', '']
        for index, event in enumerate(d['events'], 1):
            lines += [f"### {index}. {event['stage']} — {event['level']}", '',
                      f"Observed (UTC): {event['utc']}", '', event['message'], '',
                      f"Evidence: `{event['evidence']}`" if event['evidence'] else 'Evidence: current session state.', '',
                      'Remedy / lesson: '+(event['remedy'] or 'No corrective action required for this event.'), '']
        return '\n'.join(lines)


def validate_plan(plan):
    if not isinstance(plan, dict):
        raise ValueError('Pipeline plan must be an object')
    queries, sources = plan.get('queries'), plan.get('sources')
    if not isinstance(queries, list) or not 1 <= len(queries) <= 20 or any(not isinstance(q, str) or not q.strip() or len(q)>2000 for q in queries):
        raise ValueError('Provide 1–20 nonempty queries, each at most 2000 characters')
    if len(set(queries)) != len(queries):
        raise ValueError('Queries must be unique')
    if not isinstance(sources, list) or not sources or len(set(sources)) != len(sources) or any(s not in ('openalex','crossref','pubmed') for s in sources):
        raise ValueError('Pipeline sources must be unique supported adapters: openalex, crossref, pubmed')
    limit = plan.get('max_records_per_source', 100)
    if type(limit) is not int or not 1 <= limit <= 10000:
        raise ValueError('Pipeline maximum must be between 1 and 10000 per query/source')
    for key in ('year_from','year_to'):
        if key in plan and (type(plan[key]) is not int or not 1000 <= plan[key] <= 9999):
            raise ValueError('Years must be four-digit integers')
    if plan.get('year_from',1000)>plan.get('year_to',9999):
        raise ValueError('year_from must not exceed year_to')
    for key in ('date_from', 'date_to'):
        if key in plan:
            if not isinstance(plan[key], str) or len(plan[key]) != 10:
                raise ValueError('Dates must use YYYY-MM-DD')
            if date.fromisoformat(plan[key]).isoformat() != plan[key]:
                raise ValueError('Dates must use YYYY-MM-DD')
    if plan.get('date_from','0001-01-01') > plan.get('date_to','9999-12-31'):
        raise ValueError('date_from must not exceed date_to')
    if 'relevance_policy' in plan:
        from .calibration import validate_policy
        validate_policy(plan['relevance_policy'])
    return plan


def inspect_quality(rows):
    identities = Counter((r['source'], r['source_id']) for r in rows if r.get('source_id'))
    return {'retained_records': len(rows), 'missing_abstracts': sum(not r['abstract'] for r in rows),
            'repeated_provider_identity_records': sum(n-1 for n in identities.values()),
            'repeated_provider_identities': [{'source': source, 'source_id': identifier, 'copies': n}
                for (source, identifier), n in identities.items() if n > 1],
            'formal_screening_ready': False,
            'limitations': ['Relevance, exact dates, publication versions and human eligibility remain unchecked.']}


def record_quality(root, rows, event):
    report = inspect_quality(rows)
    write_json(Path(root)/'quality.json', report)
    if report['missing_abstracts']:
        event('metadata quality', 'warning', f"{report['missing_abstracts']}/{len(rows)} retained records have no abstract.",
              evidence='quality.json', remedy='Enrich metadata or seek full text; do not infer ineligibility from an absent abstract.')
    if report['repeated_provider_identity_records']:
        event('deduplication quality', 'warning', f"{report['repeated_provider_identity_records']} repeated provider identity records remain after DOI-only deduplication.",
              evidence='quality.json', remedy='Add explicit source/ID duplicate handling with provenance retention and regression tests before formal screening. Preserve this corpus as evidence; do not silently rewrite its counts.')
    return report


def inspect_session(folder):
    root = Path(folder)
    journal = SessionJournal.reopen(root)
    try:
        rows, _, _ = verify_run(root/'retrieval')
        report = record_quality(root, rows, journal.record)
        journal.record('post-run verification', 'info', 'Software inspection verified aggregate hashes and saved quality.json.', evidence='quality.json')
        return report
    except Exception as exc:
        journal.record('post-run verification', 'error', f'{type(exc).__name__}: {exc}',
                       remedy='Investigate changed/missing artifacts; do not use an unverified run for screening.')
        raise


def run_plan(plan, output, progress=None):
    """Return a verified aggregate run; preserve failed subruns and report partial coverage."""
    from .cli import run
    from .bibliometrics_cli import analyze
    root = Path(output)
    root.mkdir(parents=True, exist_ok=False)
    journal = SessionJournal(root, plan)
    write_json(root/'plan.json', plan)
    def event(stage, level, message, **context):
        journal.record(stage, level, message, **context)
        if progress:
            progress({'stage': stage, 'message': message, 'session_id': journal.data['session_id'],
                      'session_report': str((root/'SESSION.md').resolve())})
    try:
        validate_plan(plan)
        records, searches, failures = [], [], 0
        tasks = [(source, query) for query in plan['queries'] for source in plan['sources']]
        for index, (source, query) in enumerate(tasks, 1):
            stage = f'retrieval {index}/{len(tasks)}: {source}'
            sub = root/f'search-{index:02d}'
            config = {'query': query, 'sources': [source], 'max_records_per_source': plan.get('max_records_per_source',100)}
            config.update({k: plan[k] for k in ('year_from','year_to') if k in plan})
            path = root/f'search-{index:02d}.toml'
            path.write_text('\n'.join(k+' = '+json.dumps(v) for k,v in config.items())+'\n', encoding='utf-8')
            event(stage, 'info', 'Starting query: '+query, evidence=path.name)
            try:
                run(path, sub)
                verify_run(sub)
                rows = json.loads((sub/'retrieved.json').read_text())
                manifest = json.loads((sub/'manifest.json').read_text())
                for row in rows:
                    record = Record(**row)
                    record.provenance.append({'query': query, 'pipeline_session': journal.data['session_id'],
                                              'subrun': sub.name, 'retrieved_utc': manifest['finished_utc']})
                    records.append(record)
                searches.extend(manifest['searches'])
                event(stage, 'info', f'Retrieved and verified {len(rows)} records.', evidence=f'{sub.name}/manifest.json')
                if any(x.get('truncated') for x in manifest['searches']):
                    event(stage, 'warning', 'Provider reports more matches than the configured retrieval cap.',
                          evidence=f'{sub.name}/manifest.json', remedy='Expand pagination/caps after query calibration; this run cannot establish exhaustive coverage.')
            except Exception as exc:
                failures += 1
                searches.append({'source': source, 'query': query, 'status': 'failed', 'error': str(exc)})
                event(stage, 'error', f'{type(exc).__name__}: {exc}', evidence=f'{sub.name}/manifest.json',
                      remedy='Inspect provider access, rate limits, pagination credentials and response schema. Preserve this failed attempt and rerun in a new session after remediation. Exception text is evidence of failure, not a confirmed root cause.')
        if not records:
            raise ValueError('No records were successfully retrieved; the current review will remain unchanged')
        aggregate = root/'retrieval'
        aggregate.mkdir()
        from .dates import audit_dates
        scoped, date_audit = audit_dates(records, plan.get('date_from'), plan.get('date_to'))
        write_json(aggregate/'captured.json', [r.to_dict() for r in records])
        write_json(aggregate/'date-audit.json', date_audit)
        write_results(aggregate, scoped, identity=True)
        event('date validation', 'info', f"Captured {len(records)}; outside date window: {date_audit['outside_window']}; retained uncertain dates: {date_audit['uncertain_dates']}.", evidence='retrieval/date-audit.json')
        if date_audit['uncertain_dates']:
            event('date validation', 'warning', 'Uncertain or invalid publication dates remain for human verification.', evidence='retrieval/date-audit.json', remedy='Check original publication dates; partial dates crossing a boundary are retained, never guessed.')
        write_json(aggregate/'search-log.json', searches)
        write_json(aggregate/'manifest.json', {'status': 'complete', 'mode': 'live-pipeline', 'version': __version__,
            'started_utc': journal.data['started_utc'], 'finished_utc': now(), 'config': plan,
            'search_outcome': 'partial' if failures else 'complete', 'searches': searches,
            'session_id': journal.data['session_id'], 'deduplication':'doi-or-source-id-v1',
            'date_audit': {k:v for k,v in date_audit.items() if k != 'checks'},
            'files': {p.name: sha256(p.read_bytes()).hexdigest() for p in sorted(aggregate.iterdir())}})
        rows, counts, _ = verify_run(aggregate)
        event('verification', 'info', f"Verified aggregate artifact hashes: {counts}.", evidence='retrieval/manifest.json')
        record_quality(root, rows, event)
        event('metadata quality', 'warning', 'Provider-reported dates have been audited when bounds were supplied; relevance, uncertain dates and preprint/published-version pairs still require human verification.',
              evidence='retrieval/records.json', remedy='Verify exact dates against the protocol cutoff and manually inspect candidate duplicate versions before formal screening. Explicit source/ID matches are merged; different source identities are not linked by title.')
        if plan.get('relevance_policy'):
            try:
                from .calibration import calibrate_run
                event('query calibration','info','Generating lexical diagnostics and a blank human-review sample.', evidence='calibration/')
                report = calibrate_run(aggregate, plan['relevance_policy'], root/'calibration')
                event('query calibration','warning', f"Automated term-group cues present in {report['all_groups_present']}/{report['retained_records']} records; {report['review_sample_size']} records sampled for human calibration.", evidence='calibration/REPORT.md', remedy='Review the blank sample manually. These cue counts are not relevance precision, eligibility decisions or recall.')
                if any(not item['captured'] for item in report['known_items']):
                    event('known-item diagnostics','warning', f"Captured {sum(item['captured'] for item in report['known_items'])}/{len(report['known_items'])} illustrative known items in this bounded run.", evidence='calibration/report.json', remedy='Inspect query coverage, caps and publication aliases. Known-item checks are not an independent recall estimate.')
            except Exception as exc:
                event('query calibration','error',f'{type(exc).__name__}: {exc}', evidence='calibration/', remedy='Inspect the policy and metadata. Valid retrieval is preserved; rerun diagnostics in a new directory after fixing the cause.')
        try:
            event('analysis', 'info', 'Computing provisional captured-corpus bibliometrics.', evidence='analysis/')
            analyze(root/'analysis', run_folder=aggregate)
            event('analysis', 'info', 'Provisional network and coverage exports saved.', evidence='analysis/manifest.json')
        except Exception as exc:
            event('analysis', 'error', f'{type(exc).__name__}: {exc}', evidence='analysis/',
                  remedy='Inspect metadata and graph computation limits; retrieval remains usable independently of analysis.')
        journal.data['status'] = 'partial' if failures or any(e['level']=='error' for e in journal.data['events']) else 'complete'
        journal.data['finished_utc'] = now()
        event('human review gate', 'info', 'Retrieval finished. No screening votes, eligibility decisions or evidence approvals were generated.',
              remedy='Assign actual reviewers and calibrate criteria before screening. Bibliometric exports are provisional, not a research synthesis.')
        return aggregate
    except Exception as exc:
        journal.data.update(status='failed', finished_utc=now())
        event('pipeline', 'error', f'{type(exc).__name__}: {exc}',
              remedy='Use the saved plan, events and subrun artifacts to investigate. Start a new session rather than overwriting this evidence.')
        raise


def compare_sessions(baseline, current):
    """Compare verified runs without mutating either corpus; flag changed input cohorts."""
    old_root, new_root = Path(baseline), Path(current)
    old_rows, old_counts, old_manifest = verify_run(old_root/'retrieval')
    new_rows, new_counts, new_manifest = verify_run(new_root/'retrieval')
    def cohort(root):
        run = root/'retrieval'
        path = run/'captured.json' if (run/'captured.json').exists() else run/'retrieved.json'
        return Counter((r['source'],r['source_id']) for r in json.loads(path.read_text()))
    old_cohort, new_cohort = cohort(old_root), cohort(new_root)
    report = {'baseline_session':old_manifest.get('session_id'), 'current_session':new_manifest.get('session_id'),
              'same_provider_identity_cohort':old_cohort == new_cohort,
              'baseline_counts':old_counts, 'current_counts':new_counts,
              'baseline_repeated_provider_ids':inspect_quality(old_rows)['repeated_provider_identity_records'],
              'current_repeated_provider_ids':inspect_quality(new_rows)['repeated_provider_identity_records'],
              'date_audit':new_manifest.get('date_audit'),
              'interpretation':'Matching provider identities do not guarantee identical metadata. Date filtering and source changes can also affect counts; this comparison does not establish research validity.'}
    write_json(new_root/'comparison.json', report)
    lines=['# Pipeline session comparison', '',
           f"Baseline session: {report['baseline_session']}", f"Current session: {report['current_session']}", '',
           f"Same captured provider-identity cohort: {report['same_provider_identity_cohort']}", '',
           f"Retained records: {len(old_rows)} → {len(new_rows)}", '',
           f"Repeated provider-ID records: {report['baseline_repeated_provider_ids']} → {report['current_repeated_provider_ids']}", '',
           report['interpretation'], '', 'Detailed counts and date audit: `comparison.json`.']
    (new_root/'COMPARISON.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    if (new_root/'session.json').exists():
        journal = SessionJournal.reopen(new_root)
        journal.record('cross-session verification','info',f"Compared verified sessions: repeated provider-ID records {report['baseline_repeated_provider_ids']} → {report['current_repeated_provider_ids']}.", evidence='COMPARISON.md', remedy=report['interpretation'])
    return report


def main(argv=None):
    import sys
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == 'compare-calibration':
        from .calibration import compare_calibrations
        parser = argparse.ArgumentParser(description='Compare verified query diagnostics under the same policy.')
        parser.add_argument('--baseline', required=True)
        parser.add_argument('--revision', required=True)
        parser.add_argument('--output', required=True)
        args = parser.parse_args(argv[1:])
        print(json.dumps(compare_calibrations(args.baseline, args.revision, args.output), indent=2))
        return 0
    if argv and argv[0] == 'calibrate':
        from .calibration import calibrate_run
        parser = argparse.ArgumentParser(description='Verify a saved retrieval run and produce automated query diagnostics.')
        parser.add_argument('--run', required=True)
        parser.add_argument('--policy', required=True)
        parser.add_argument('--output', required=True)
        args = parser.parse_args(argv[1:])
        print(json.dumps(calibrate_run(args.run, json.loads(Path(args.policy).read_text()), args.output), indent=2))
        return 0
    if argv and argv[0] == 'compare':
        parser = argparse.ArgumentParser(description='Compare two verified pipeline sessions.')
        parser.add_argument('--baseline', required=True)
        parser.add_argument('--session', required=True)
        args = parser.parse_args(argv[1:])
        print(json.dumps(compare_sessions(args.baseline, args.session), indent=2))
        return 0
    if argv and argv[0] == 'inspect':
        parser = argparse.ArgumentParser(description='Verify a saved pipeline session and append its quality findings.')
        parser.add_argument('--session', required=True)
        args = parser.parse_args(argv[1:])
        print(json.dumps(inspect_session(args.session), indent=2))
        return 0
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan',required=True,help='JSON plan: queries, sources, years and maximum per query/source')
    parser.add_argument('--output',required=True,help='New session directory')
    args=parser.parse_args(argv)
    try:
        run=run_plan(json.loads(Path(args.plan).read_text()),args.output,
                     progress=lambda event: print(event['stage']+': '+event['message'],flush=True))
    except (ValueError,OSError,RuntimeError,TypeError) as exc:
        parser.exit(1,f'Pipeline failed: {exc}\n')
    print('Verified run: '+str(run))
    print('Session report: '+str(Path(args.output)/'SESSION.md'))
    return 0
