"""Fault-injection checks for the application-owned practical-test pipeline."""
import json
from pathlib import Path

import pytest

from slr.pipeline import run_plan
from slr.dashboard import Workspace
from slr.screening import verify_run

PLAN={'queries':['good','bad'],'sources':['crossref'],'max_records_per_source':10,'year_from':2022,'year_to':2026}


def stub_run(monkeypatch):
    from slr.cli import run
    def fake(config, output):
        if '"bad"' in Path(config).read_text():
            raise RuntimeError('Injected provider HTTP 429')
        return run(config,output,'Examples/demo_records.json')
    monkeypatch.setattr('slr.cli.run',fake)


def test_partial_failure_keeps_verified_results_and_durable_error_report(tmp_path, monkeypatch):
    stub_run(monkeypatch)
    events=[]
    run=run_plan(PLAN,tmp_path/'session',events.append)
    rows,counts,manifest=verify_run(run)
    assert rows and manifest['search_outcome']=='partial'
    report=(tmp_path/'session/SESSION.md').read_text()
    assert 'HTTP 429' in report and 'retrieval 2/2' in report and 'Remedy / lesson:' in report
    state=json.loads((tmp_path/'session/session.json').read_text())
    assert state['status']=='partial' and events[-1]['session_report']
    assert (tmp_path/'session/analysis/manifest.json').exists()


def test_total_failure_never_emits_a_valid_aggregate(tmp_path,monkeypatch):
    stub_run(monkeypatch)
    with pytest.raises(ValueError,match='No records'):
        run_plan({**PLAN,'queries':['bad']},tmp_path/'failed')
    assert not (tmp_path/'failed/retrieval').exists()
    assert json.loads((tmp_path/'failed/session.json').read_text())['status']=='failed'


def test_invalid_plan_is_logged_without_network_calls(tmp_path):
    with pytest.raises(ValueError,match='unique'):
        run_plan({**PLAN,'queries':['same','same']},tmp_path/'invalid')
    assert 'Queries must be unique' in (tmp_path/'invalid/SESSION.md').read_text()


def test_dashboard_pipeline_persists_jobs_and_registers_actual_service_results(tmp_path,monkeypatch):
    stub_run(monkeypatch)
    workspace=Workspace(tmp_path/'workspace')
    entry=workspace.create({'name':'Pipeline test','question':'Does it work?','criteria':'Test only',
                            'reviewers':['A','B'],'adjudicator':'C'})
    job=workspace.search(entry['id'],{'query':'good','queries':['good','bad'],'sources':['crossref'],'limit':10})
    workspace.executor.shutdown(wait=True)
    saved=workspace.jobs[job['id']]
    assert saved['status']=='complete' and saved['outcome']=='partial'
    assert not workspace.state(entry['id'])['activity']
    reopened=Workspace(workspace.root)
    try:
        assert reopened.jobs[job['id']]['session_report']==saved['session_report']
        assert reopened.state(entry['id'])['counts']['records_to_screen']==2
    finally:
        reopened.executor.shutdown(wait=True)


def test_restart_records_interrupted_job_in_markdown(tmp_path,monkeypatch):
    stub_run(monkeypatch)
    run_plan({**PLAN,'queries':['good']},tmp_path/'session')
    root=tmp_path/'workspace';root.mkdir()
    (root/'jobs.json').write_text(json.dumps({'j':{'id':'j','status':'running','session_report':str(tmp_path/'session/SESSION.md')}}))
    workspace=Workspace(root)
    try:
        assert workspace.jobs['j']['status']=='failed'
        assert 'process restart' in (tmp_path/'session/SESSION.md').read_text()
    finally:
        workspace.executor.shutdown(wait=True)


def test_inspection_confirms_identity_deduplication_without_changing_corpus(tmp_path,monkeypatch):
    from slr.pipeline import inspect_session
    stub_run(monkeypatch)
    folder=tmp_path/'session'
    run=run_plan({**PLAN,'queries':['good','another good query']},folder)
    before=(run/'records.json').read_bytes()
    report=inspect_session(folder)
    assert report['repeated_provider_identity_records']==0
    assert (run/'records.json').read_bytes()==before
    assert 'post-run verification' in (folder/'SESSION.md').read_text()


def test_pipeline_generates_calibration_packet_without_screening_votes(tmp_path,monkeypatch):
    stub_run(monkeypatch)
    run=run_plan({**PLAN,'queries':['good'],'relevance_policy':{'groups':{'topic':['learning']}}},tmp_path/'session')
    report=json.loads((tmp_path/'session/calibration/report.json').read_text())
    assert report['status']=='human-calibration-pending'
    assert 'query calibration' in (tmp_path/'session/SESSION.md').read_text()
    assert (tmp_path/'session/calibration/human-review.csv').exists()
