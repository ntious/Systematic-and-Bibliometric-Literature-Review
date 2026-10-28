"""WA-02 regressions: once a guided protocol exists, eligibility amendments are the one path to new screening
criteria, and no protocol save silently drops a criteria version. Legacy reviews keep direct revision."""
import json
import sqlite3
from hashlib import sha256

import pytest

from slr import cli, protocol, review_plan as rp, screening
from test_review_plan import approved, body, document, mutate, review  # noqa: F401  (review is a fixture)

BLOCK = 'guided protocol'


def amend(db, doc, why='Synthetic amendment'):
    return mutate(db, 'save', protocol=doc, description=why, rationale='Synthetic rationale for the change')


def last_save(db):
    return [r for r in rp.state(db)['history'] if r['kind'] == 'protocol-save'][-1]['content']


def test_reported_sequence_no_longer_reverts_a_screening_revision(review):
    workspace, entry, db = review
    approved(db)
    before = rp.state(db)['criteria']
    version = before['version']
    for attempt in (lambda: screening.revise_criteria(db, 'Screening-page revised criteria text', expected_version=version),
                    lambda: workspace.mutate_screening(entry['id'], {'action': 'criteria', 'version': version, 'text': 'Screening-page revised criteria text'})):
        with pytest.raises(ValueError, match=BLOCK):
            attempt()
    assert rp.state(db)['criteria'] == before and rp.state(db)['final_current']  # nothing written, approvals intact
    doc = rp.state(db)['protocol']
    doc['data_items'] = 'Design, outcomes and setting'  # the unrelated save from the report
    after = amend(db, doc)
    assert after['criteria'] == before and 'criteria_change' not in last_save(db)


def test_cli_criteria_revision_is_refused_with_guidance(review, tmp_path, capsys):
    _, _, db = review
    approved(db)
    revised = tmp_path / 'criteria.md'
    revised.write_text('Revised by CLI', encoding='utf-8')
    version = rp.state(db)['criteria']['version']
    with pytest.raises(SystemExit):
        cli.main(['review', 'criteria', '--db', str(db), '--version', str(version), '--file', str(revised)])
    assert 'Amend eligibility in Review protocol' in capsys.readouterr().err
    assert rp.state(db)['criteria']['version'] == version


def test_eligibility_amendment_is_the_path_and_is_recorded(review):
    _, _, db = review
    approved(db)
    old = rp.state(db)['criteria']
    doc = rp.state(db)['protocol']
    doc['eligibility']['study_characteristics'] = 'Include empirical studies in schools only'
    state = amend(db, doc, 'Narrow eligibility')
    assert state['criteria']['version'] == old['version'] + 1
    assert state['criteria']['text'] == rp.eligibility_text(doc)
    change = last_save(db)['criteria_change']
    assert change == {'from_version': old['version'], 'to_version': old['version'] + 1, 'replaced_sha256': old['sha256']}
    assert 'return to title screening' in last_save(db)['impact']
    assert not state['sections']['eligibility']['current'] and not state['final_current']


def test_first_guided_save_reports_replacing_pre_protocol_criteria(review):
    _, _, db = review
    from slr import questions
    questions.mutate(db, dict(actor='A', expected_revision=0, action='save', topic='T', questions=['Q?']))
    questions.mutate(db, dict(actor='A', expected_revision=1, action='approve'))
    screening.revise_criteria(db, 'Pre-protocol revision', expected_version=1)  # still allowed: no guided protocol yet
    mutate(db, 'save', protocol=document())
    change = last_save(db)['criteria_change']
    assert change['from_version'] == 2 and change['replaced_criteria_not_from_protocol'] is True
    assert 'was not taken from the saved protocol' in last_save(db)['impact']
    texts = [r[0] for r in sqlite3.connect(db).execute('SELECT text FROM criteria ORDER BY version')]
    assert 'Pre-protocol revision' in texts  # superseded, never deleted


def test_historical_out_of_protocol_revision_is_reported_not_silent(review):
    _, _, db = review
    approved(db)
    with sqlite3.connect(db) as conn:  # e.g. a ledger revised on the screening page before this repair
        version = conn.execute('SELECT MAX(version) FROM criteria').fetchone()[0]
        conn.execute('INSERT INTO criteria VALUES (?,?,?,?)', (version + 1, 'Historical screening-page text',
                     sha256(b'Historical screening-page text').hexdigest(), '2026-10-24T00:00:00+00:00'))
    with pytest.raises(ValueError, match='differ from this eligibility section'):
        mutate(db, 'approve-section', section='eligibility')
    doc = rp.state(db)['protocol']
    doc['data_items'] = 'unrelated edit'
    amend(db, doc)
    change = last_save(db)['criteria_change']
    assert change['from_version'] == version + 1 and change['replaced_criteria_not_from_protocol']


def test_ai_eligibility_accept_records_the_criteria_change(review):
    from slr import protocol_ai as pa
    _, _, db = review
    approved(db)
    packet = pa.request(db, body(db, section='eligibility'), {'provider': 'synthetic', 'model': 'm', 'mode': 'local'})
    value = {'study_characteristics': 'AI study scope', 'report_characteristics': 'AI report scope'}
    pa.record(db, {'request_id': packet['request_id'], 'request_sha256': packet['request_sha256'], 'provider': 'synthetic',
                   'requested_model': 'm', 'output': {'items': [{'field': 'eligibility', 'value': value, 'rationale': 'r'}]}})
    proposal = [r for r in rp.state(db)['history'] if r['kind'] == 'ai-proposal'][-1]
    state = pa.decide(db, body(db, proposal_sequence=proposal['sequence'], index=0, decision='accept'))
    change = last_save(db)['criteria_change']
    assert change['to_version'] == state['criteria']['version'] and 'replaced_criteria_not_from_protocol' not in change
    assert 'ai_request_id' in last_save(db)


def test_legacy_reviews_keep_direct_revision(review, tmp_path):
    _, _, db = review
    assert screening.revise_criteria(db, 'Legacy revision without a protocol', expected_version=1) == 2
    protocol.save(db, {}, 'A', expected_version=0)  # standalone PRISMA-P protocol, not the guided workflow
    assert screening.revise_criteria(db, 'Revision under a standalone protocol', expected_version=2) == 3
    assert protocol.state(db)['undocumented_criteria_revisions'] == [3]  # still reported, as before this repair


def test_legacy_review_with_plan_events_but_no_guided_protocol_keeps_revision(review):
    """Opening the protocol page or recording a screening exception creates plan events without a guided protocol."""
    _, _, db = review
    rp.state(db)  # creates the plan tables, as the dashboard's protocol page does
    gate = screening.screening_access(db)
    screening.screening_access(db, 'C', 'Teaching collection; protocol deliberately deferred here.', expected_version=1,
                               expected_binding=gate['binding'])
    assert any(r['kind'] == 'screening-exception' for r in rp.state(db)['history'])
    assert screening.revise_criteria(db, 'Legacy revision with plan events present', expected_version=1) == 2
