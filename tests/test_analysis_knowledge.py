import copy
import json
import sqlite3

import pytest

from slr.analysis_knowledge import initialize, load, main, recommend, seed, validate
from slr.cli import main as cli


def test_graph_database_round_trip_and_referential_integrity(tmp_path):
    db = tmp_path / 'knowledge.sqlite'
    expected = initialize(db)
    before = db.read_bytes()
    assert load(db) == expected
    assert db.read_bytes() == before
    assert len([n for n in expected['nodes'] if n['kind'] == 'method']) == 32
    assert len([n for n in expected['nodes'] if n['kind'] == 'source']) == 13
    with sqlite3.connect(db) as conn:
        assert not conn.execute('PRAGMA foreign_key_check').fetchall()


def test_never_overwrites_existing_database(tmp_path):
    db = tmp_path / 'screening.sqlite'
    db.write_bytes(b'Existing research data')
    with pytest.raises(FileExistsError):
        initialize(db)
    assert db.read_bytes() == b'Existing research data'


def test_tampering_is_detected(tmp_path):
    db = tmp_path / 'knowledge.sqlite'
    initialize(db)
    with sqlite3.connect(db) as conn:
        conn.execute("DELETE FROM edges WHERE predicate='candidate_method'")
    with pytest.raises(ValueError, match='hash mismatch'):
        load(db)


def test_dangling_and_duplicate_nodes_rejected():
    graph = seed()
    broken = copy.deepcopy(graph)
    broken['edges'][0]['object'] = 'missing'
    with pytest.raises(ValueError, match='Dangling'):
        validate(broken)
    graph['nodes'].append(graph['nodes'][0])
    with pytest.raises(ValueError, match='Duplicate'):
        validate(graph)


def test_question_hints_never_approve_or_execute():
    result = recommend(seed(), 'How effective is tutoring compared with usual teaching?')
    assert any(h['intent'] == 'effect' for h in result['tentative_intents'])
    assert result['candidates']
    assert all(c['state'] == 'needs_intent_confirmation' for c in result['candidates'])
    assert not result['approval_recorded'] and not result['execution_allowed']
    assert all(not c['execution_allowed'] for c in result['candidates'])


def test_confirmed_intent_overrides_lexical_hints():
    result = recommend(seed(), 'Experiences of an effective programme', intents=['experience'])
    assert result['confirmed_intents'] == ['experience']
    assert {c['method']['id'] for c in result['candidates']} == {'qualitative-selection', 'meta-aggregation'}
    assert all(c['missing_fields'] and c['unresolved_human_checks'] for c in result['candidates'])


def test_all_declared_prerequisites_still_cannot_run():
    graph = seed()
    target = next(n['data'] for n in graph['nodes'] if n['id'] == 'method:meta-fixed')
    result = recommend(graph, 'Compare effects', intents=['effect'], requested_method='meta-fixed',
                       available_fields=target['required_fields'], human_checks=target['human_checks'])
    candidate = next(c for c in result['candidates'] if c['method']['id'] == 'meta-fixed')
    assert candidate['state'] == 'candidate_requires_methodologist_review'
    assert not candidate['missing_fields'] and not candidate['execution_allowed']
    assert candidate['source']['url'].startswith('https://')


def test_unknown_and_negated_wording_is_never_treated_as_confirmed():
    assert not recommend(seed(), '¿Qué métodos se utilizan?')['candidates']
    assert not recommend(seed(), 'Unclear purpose')['candidates']
    result = recommend(seed(), 'We do not study effectiveness')
    assert not result['confirmed_intents']
    assert all(c['state'] == 'needs_intent_confirmation' for c in result['candidates'])
    # Boundary matching avoids the substring 'experience' in 'inexperience'.
    assert not recommend(seed(), 'Inexperience')['tentative_intents']


def test_requested_unknown_method_is_explicit():
    result = recommend(seed(), 'Unclear question', requested_method='invented-test')
    assert not result['requested_method_known']
    assert not result['candidates'] and not result['execution_allowed']


@pytest.mark.parametrize('options', [dict(intents=['made-up']), dict(available_fields=['made-up']), dict(human_checks=['made-up'])])
def test_unknown_prerequisite_names_fail(options):
    with pytest.raises(ValueError, match='Unknown'):
        recommend(seed(), 'What types of evidence?', **options)


def test_cli_wiring_and_missing_database_do_not_create_files(tmp_path, capsys):
    db = tmp_path / 'knowledge.sqlite'
    assert cli(['knowledge', 'init', '--db', str(db)]) == 0
    assert json.loads(capsys.readouterr().out)['methods'] == 32
    assert main(['recommend', '--db', str(db), '--question', 'What research gaps exist?', '--intent', 'map']) == 0
    assert json.loads(capsys.readouterr().out)['candidates']
    with pytest.raises(SystemExit):
        main(['catalogue', '--db', str(tmp_path / 'absent.sqlite')])
    assert not (tmp_path / 'absent.sqlite').exists()
