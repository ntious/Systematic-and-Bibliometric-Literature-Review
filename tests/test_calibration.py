"""Query diagnostics must not impersonate human screening or inflate validation claims."""
import csv
from hashlib import sha256
import json

import pytest

from slr.calibration import calibrate_run, diagnostics, validate_policy
from slr.models import Record
from slr.reporting import write_json, write_results

POLICY={'groups':{'context':['security'],'method':['AI','machine learning'],'task':['triage']},'sample_per_stratum':1,
        'known_items':[{'title':'Security triage with AI','doi':'10.1234/a'}]}


def make_run(tmp_path):
    run=tmp_path/'retrieval';run.mkdir()
    records=[Record(source='test',source_id=str(i),title=title,abstract=abstract,doi=doi,
                    provenance=[{'source':'test','source_id':str(i),'query':query}])
             for i,(title,abstract,doi,query) in enumerate([
                ('Security triage with AI','A fictional evaluation.','10.1234/a','query one'),
                ('Security triage','A study with no method cue.','','query one'),
                ('Security triage with AI','','','query two'),
                ('Security triage with AI','Another fictional evaluation.','','query two')])]
    write_results(run,records)
    write_json(run/'manifest.json',{'status':'complete','files':{p.name:sha256(p.read_bytes()).hexdigest() for p in run.iterdir()}})
    return run


def test_literal_terms_have_word_boundaries_and_missing_metadata_remains_uncertain():
    rows=[Record(source='test',source_id='1',title='Security triage chairs',abstract='A fictional example').to_dict(),
          Record(source='test',source_id='2',title='Security triage with AI').to_dict()]
    results=diagnostics(rows,POLICY)
    assert not results[0]['all_groups_present']  # "AI" inside chairs is not a cue.
    assert results[1]['all_groups_present'] and results[1]['stratum']=='limited-metadata'


def test_verified_outputs_are_deterministic_and_leave_human_judgments_blank(tmp_path):
    run=make_run(tmp_path)
    before=(run/'records.json').read_bytes()
    report=calibrate_run(run,POLICY,tmp_path/'first')
    calibrate_run(run,POLICY,tmp_path/'second')
    assert report['status']=='human-calibration-pending'
    assert report['known_items'][0]['captured']
    assert (tmp_path/'first/human-review.csv').read_bytes()==(tmp_path/'second/human-review.csv').read_bytes()
    rows=list(csv.DictReader((tmp_path/'first/human-review.csv').open()))
    assert rows and all(not r['human_relevance'] and not r['reviewer'] for r in rows)
    assert (run/'records.json').read_bytes()==before
    assert 'not semantic relevance' in (tmp_path/'first/REPORT.md').read_text()


def test_tampered_input_is_rejected_before_diagnostics(tmp_path):
    run=make_run(tmp_path)
    (run/'records.json').write_text('[]')
    with pytest.raises(ValueError,match='hash mismatch'):
        calibrate_run(run,POLICY,tmp_path/'output')
    assert not (tmp_path/'output').exists()


def test_policy_validation_rejects_empty_terms_and_invalid_sampling():
    with pytest.raises(ValueError):validate_policy({'groups':{'x':['']}})
    with pytest.raises(ValueError):validate_policy({**POLICY,'sample_per_stratum':False})


def test_verified_comparison_flags_known_item_regression_without_claiming_relevance(tmp_path):
    from slr.calibration import compare_calibrations
    baseline=make_run(tmp_path)
    other=tmp_path/'other';other.mkdir()
    write_results(other,[Record(source='test',source_id='unseen',title='Different security triage using machine learning',abstract='Fictional evaluation.')])
    write_json(other/'manifest.json',{'status':'complete','files':{p.name:sha256(p.read_bytes()).hexdigest() for p in other.iterdir()}})
    calibrate_run(baseline,POLICY,tmp_path/'baseline')
    calibrate_run(other,POLICY,tmp_path/'revision')
    report=compare_calibrations(tmp_path/'baseline',tmp_path/'revision',tmp_path/'comparison')
    assert report['status']=='needs-investigation' and report['known_items_captured_before']==1 and report['known_items_captured_after']==0
    assert 'Do not automatically adopt' in report['recommendation']
    calibrate_run(other,{**POLICY,'sample_per_stratum':2},tmp_path/'different-policy')
    with pytest.raises(ValueError,match='same calibration policy'):
        compare_calibrations(tmp_path/'baseline',tmp_path/'different-policy',tmp_path/'invalid-comparison')
