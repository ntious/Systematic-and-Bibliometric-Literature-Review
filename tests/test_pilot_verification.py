"""WA-03 regressions: pilot strategy review rests on a governed, still-verifiable run, and one unavailable pilot
never hides the protocol page. Synthetic records only; the provider call is replaced by a local fixture."""
import json
import shutil

import pytest

from conftest import _fixture_run, governed_pilot
from slr import cli, review_plan as rp
from test_review_plan import approved, body, mutate, review  # noqa: F401  (review is a fixture)


def review_pilot(db, run_id, decision='approve-strategy'):
    return mutate(db, 'pilot-review', run_id=run_id, decision=decision, notes='Synthetic pilot sample inspected')


def preview(workspace, entry):
    """The exact call the dashboard's GET /api/plan makes."""
    return rp.state(entry['screening_db']) | {'pilots': workspace.pilot_preview(entry['id'])}


def test_verified_pilot_review_records_what_was_verified(review, tmp_path):
    _, _, db = review
    approved(db)
    auth, result = governed_pilot(db, body(db, pilot_limit=5), tmp_path / 'pilot')
    [shown] = rp.inspect_pilots(db, auth['run_id'])
    assert shown['status'] == 'complete' and shown['counts']['identified'] > 0
    event = review_pilot(db, auth['run_id'])['history'][-1]
    assert event['content']['verified_manifest_sha256'] == shown['manifest_sha256']
    assert event['content']['verified_identified'] == shown['counts']['identified']
    assert rp.authorize(db, body(db), 'main')['kind'] == 'main'


def test_pilot_without_governed_start_cannot_be_reviewed(review, tmp_path):
    _, _, db = review
    approved(db)
    auth = rp.authorize(db, body(db, pilot_limit=5), 'pilot')
    folder = tmp_path / 'never-ran'
    folder.mkdir()
    (folder / 'manifest.json').write_text('{}')
    rp.record_run(db, auth, folder, 'complete')  # recorded as complete, but run_authorized never started it
    for decision in ('approve-strategy', 'revise'):
        with pytest.raises(ValueError, match='did not start through the governed'):
            review_pilot(db, auth['run_id'], decision)
    with pytest.raises(ValueError, match='Review and approve'):
        rp.authorize(db, body(db), 'main')


@pytest.mark.parametrize('damage', ['records', 'manifest', 'deleted'])
def test_changed_or_missing_results_are_unavailable_and_unreviewable(review, tmp_path, damage):
    workspace, entry, db = review
    approved(db)
    auth, result = governed_pilot(db, body(db, pilot_limit=5), tmp_path / 'pilot')
    if damage == 'records':
        (result / 'records.json').write_text('[]')
    elif damage == 'manifest':
        manifest = json.loads((result / 'manifest.json').read_text())
        manifest['searches'] = []
        (result / 'manifest.json').write_text(json.dumps(manifest))
    else:
        shutil.rmtree(result.parent)
    state = preview(workspace, entry)  # the protocol page still loads
    [shown] = state['pilots']
    assert shown['status'] == 'unavailable' and shown['recorded_status'] == 'complete'
    assert 'cannot be reviewed' in shown['error'] and 'counts' not in shown and 'sample' not in shown
    with pytest.raises(ValueError, match='manifest changed|Artifact hash|no longer available'):
        review_pilot(db, auth['run_id'])
    with pytest.raises(ValueError, match='Review and approve'):
        rp.authorize(db, body(db), 'main')
    history = rp.state(db)['history']
    assert [r['content']['status'] for r in history if r['kind'] == 'pilot-run'] == ['complete']  # ledger untouched


def test_one_unavailable_pilot_does_not_hide_others_and_a_new_pilot_recovers(review, tmp_path):
    workspace, entry, db = review
    approved(db)
    old, old_result = governed_pilot(db, body(db, pilot_limit=5), tmp_path / 'old')
    shutil.rmtree(old_result.parent)  # e.g. a researcher cleaned up old session folders
    new, _ = governed_pilot(db, body(db, pilot_limit=5), tmp_path / 'new')
    statuses = {p['run_id']: p['status'] for p in preview(workspace, entry)['pilots']}
    assert statuses == {old['run_id']: 'unavailable', new['run_id']: 'complete'}
    review_pilot(db, new['run_id'])
    assert rp.authorize(db, body(db), 'main')['pilot_review_sequence']


def test_results_from_another_pilot_authorization_are_rejected(review, tmp_path):
    _, _, db = review
    approved(db)
    first, first_result = governed_pilot(db, body(db, pilot_limit=5), tmp_path / 'first')
    second = rp.authorize(db, body(db, pilot_limit=5), 'pilot')
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr('slr.cli.run', lambda config, folder: _fixture_run(config, folder, 'Examples/demo_records.json'))
        rp.run_authorized(db, second, tmp_path / 'second')
    rp.record_run(db, second, first_result, 'complete')  # second's run-start exists, but it points at first's results
    [shown] = rp.inspect_pilots(db, second['run_id'])
    assert shown['status'] == 'unavailable' and 'do not belong' in shown['error']
    with pytest.raises(ValueError, match='do not belong'):
        review_pilot(db, second['run_id'])
    review_pilot(db, first['run_id'])  # the genuine one is still reviewable


def test_cli_inspect_reports_unavailable_instead_of_failing(review, tmp_path, capsys):
    _, _, db = review
    approved(db)
    auth, result = governed_pilot(db, body(db, pilot_limit=5), tmp_path / 'pilot')
    shutil.rmtree(result.parent)
    assert cli.main(['plan', 'inspect-pilot', '--db', str(db), '--run-id', auth['run_id']]) == 0
    [shown] = json.loads(capsys.readouterr().out)
    assert shown['status'] == 'unavailable'
