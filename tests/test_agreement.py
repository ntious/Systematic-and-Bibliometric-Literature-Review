import json
from hashlib import sha256

import pytest

from slr import screening as s
from slr.agreement import paired_agreement
from slr.cli import main, run
from slr.models import Record
from slr.review_cli import export_review

II, IE, EI, EE = ('include', 'include'), ('include', 'exclude'), ('exclude', 'include'), ('exclude', 'exclude')


# Hand-calculated statistics

def test_hand_calculated_kappa_and_prevalence_paradox():
    # n=50, po=42/50=.84; reviewer A includes 45/50, B 43/50.
    # pe=.9*.86+.1*.14=.788; kappa=(.84-.788)/(1-.788)=.24528...; PABAK=2*.84-1=.68
    result = paired_agreement([II] * 40 + [IE] * 5 + [EI] * 3 + [EE] * 2)
    assert result['pairs'] == 50
    assert result['table'] == {'include/include': 40, 'include/exclude': 5, 'exclude/include': 3, 'exclude/exclude': 2}
    assert result['observed_agreement'] == pytest.approx(0.84)
    assert result['expected_agreement'] == pytest.approx(0.788)
    assert result['cohen_kappa'] == pytest.approx(0.052 / 0.212)
    assert result['pabak'] == pytest.approx(0.68)


def test_balanced_table_kappa():
    # po=.7, pA=.5, pB=.6, pe=.5 -> kappa=.4
    result = paired_agreement([II] * 20 + [IE] * 5 + [EI] * 10 + [EE] * 15)
    assert result['cohen_kappa'] == pytest.approx(0.4)
    assert result['pabak'] == pytest.approx(0.4)


@pytest.mark.parametrize('pairs,kappa,pabak', [([II, EE] * 3, 1.0, 1.0), ([IE, EI] * 3, -1.0, -1.0)])
def test_perfect_agreement_and_disagreement(pairs, kappa, pabak):
    result = paired_agreement(pairs)
    assert result['cohen_kappa'] == pytest.approx(kappa)
    assert result['pabak'] == pytest.approx(pabak)


def test_kappa_undefined_without_variation_or_pairs():
    single = paired_agreement([II] * 5)
    assert single['cohen_kappa'] is None and single['pabak'] == 1.0
    assert 'one identical category' in single['kappa_undefined_reason']
    empty = paired_agreement([])
    assert empty['cohen_kappa'] is None and empty['observed_agreement'] is None and empty['pabak'] is None
    assert empty['kappa_undefined_reason'] == 'no paired decisions'


def test_invalid_pairs_rejected():
    with pytest.raises(ValueError):
        paired_agreement([('include', 'maybe')])


# Ledger integration

@pytest.fixture
def ledger(tmp_path):
    fixture = tmp_path / 'records.json'
    fixture.write_text(json.dumps([Record('synthetic', str(i), title=f'Synthetic study {i}', doi=f'10.1234/syn.{i}').to_dict()
                                   for i in range(1, 11)]), encoding='utf-8')
    run('configs/example_review.toml', tmp_path / 'run', fixture)
    db = tmp_path / 'review.sqlite'
    assert s.initialize(db, tmp_path / 'run', 'Agreement review', ['alice', 'bob'], 'carol', 'Criteria') == 10
    return db


def vote(db, record, actor, value, stage='title', version=1, reason=None):
    s.decide(db, record, actor, stage, value, reason or ('Wrong population' if value == 'exclude' else ''), expected_version=version)


def votes(db, pattern):
    for index, (a, b) in enumerate(pattern, 1):
        record = f'R{index:06d}'
        vote(db, record, 'alice', a)
        vote(db, record, 'bob', b)


def test_ledger_agreement_matches_votes_and_ignores_unpaired(ledger):
    votes(ledger, [II, II, EE, IE])
    vote(ledger, 'R000005', 'alice', 'include')  # unpaired: not counted
    title = s.snapshot(ledger)['agreement']['title']
    # po=.75, pA=.75, pB=.5, pe=.5 -> kappa=.5
    assert title['pairs'] == 4 and title['cohen_kappa'] == pytest.approx(0.5) and title['pabak'] == pytest.approx(0.5)
    assert title['reviewers'] == ['alice', 'bob']
    assert s.snapshot(ledger)['agreement']['fulltext']['pairs'] == 0


def test_adjudication_does_not_change_agreement(ledger):
    votes(ledger, [II, IE])
    before = s.snapshot(ledger)['agreement']['title']
    s.decide(ledger, 'R000002', 'carol', 'title', 'include', 'Meets criteria', adjudicate=True, expected_version=1)
    assert s.snapshot(ledger)['agreement']['title'] == before


def test_exclusion_reason_agreement(ledger):
    vote(ledger, 'R000001', 'alice', 'exclude', reason='Wrong population')
    vote(ledger, 'R000001', 'bob', 'exclude', reason='Wrong design')
    vote(ledger, 'R000002', 'alice', 'exclude', reason='Wrong design')
    vote(ledger, 'R000002', 'bob', 'exclude', reason='Wrong design')
    reasons = s.snapshot(ledger)['agreement']['title']['exclusion_reason_agreement']
    assert reasons == {'both_excluded': 2, 'same_primary_reason': 1}


def test_agreement_is_per_criteria_version(ledger):
    votes(ledger, [II, EE])
    s.revise_criteria(ledger, 'Revised criteria', expected_version=1)
    data = s.snapshot(ledger)['agreement']
    assert data['criteria_version'] == 2 and data['title']['pairs'] == 0


def test_reviewer_queue_does_not_leak_agreement(ledger):
    votes(ledger, [II, IE])
    queue = s.snapshot(ledger, reviewer='alice')
    assert 'agreement' not in queue and 'pilot' not in queue


# Pilot calibration round

def test_pilot_is_reproducible_and_recorded(ledger, tmp_path):
    sample = s.start_pilot(ledger, 'carol', 4, seed=7, expected_version=1)
    assert len(sample) == 4 and sample == sorted(sample)
    pilot = s.snapshot(ledger)['pilot']
    assert pilot['records'] == sample and pilot['seed'] == 7 and pilot['size'] == 4 and not pilot['complete']
    events = [e for e in s.snapshot(ledger)['events'] if e['kind'] == 'pilot']
    assert [e['record_id'] for e in events] == sample and {e['actor'] for e in events} == {'carol'}


def test_same_seed_same_sample_and_default_seed_recorded(ledger, tmp_path):
    other = tmp_path / 'other.sqlite'
    s.initialize(other, tmp_path / 'run', 'Copy', ['alice', 'bob'], 'carol', 'Criteria')
    assert s.start_pilot(ledger, 'carol', 5, seed=42, expected_version=1) == s.start_pilot(other, 'carol', 5, seed=42, expected_version=1)
    third = tmp_path / 'third.sqlite'
    s.initialize(third, tmp_path / 'run', 'Default seed', ['alice', 'bob'], 'carol', 'Criteria')
    s.start_pilot(third, 'carol', 3, expected_version=1)
    data = s.snapshot(third)
    expected = int(sha256(f"{data['review_id']}:1".encode()).hexdigest()[:8], 16)
    assert data['pilot']['seed'] == expected


@pytest.mark.parametrize('actor,size,message', [('alice', 3, 'adjudicator'), ('carol', 0, 'positive'), ('carol', 11, 'exceeds')])
def test_pilot_validation(ledger, actor, size, message):
    with pytest.raises(ValueError, match=message):
        s.start_pilot(ledger, actor, size, seed=1, expected_version=1)


def test_pilot_rejected_after_decisions_or_twice(ledger):
    s.start_pilot(ledger, 'carol', 2, seed=1, expected_version=1)
    with pytest.raises(ValueError, match='already exists'):
        s.start_pilot(ledger, 'carol', 2, seed=2, expected_version=1)


def test_pilot_rejected_once_screening_started(ledger):
    vote(ledger, 'R000001', 'alice', 'include')
    with pytest.raises(ValueError, match='before any title decisions'):
        s.start_pilot(ledger, 'carol', 2, seed=1, expected_version=1)


def test_pilot_gates_other_title_screening_until_both_finish(ledger):
    sample = s.start_pilot(ledger, 'carol', 3, seed=3, expected_version=1)
    outside = next(f'R{i:06d}' for i in range(1, 11) if f'R{i:06d}' not in sample)
    with pytest.raises(ValueError, match='pilot'):
        vote(ledger, outside, 'alice', 'include')
    queue = s.snapshot(ledger, reviewer='alice')
    assert queue['pilot_open'] and [r['record_id'] for r in queue['queue']] == sample and all(r['pilot'] for r in queue['queue'])
    for record in sample:
        vote(ledger, record, 'alice', 'include')
    with pytest.raises(ValueError, match='pilot'):  # bob has not finished yet
        vote(ledger, outside, 'alice', 'include')
    assert [r['record_id'] for r in s.snapshot(ledger, reviewer='bob')['queue']] == sample
    for record, value in zip(sample, ('include', 'exclude', 'include')):
        vote(ledger, record, 'bob', value)
    data = s.snapshot(ledger)
    assert data['pilot']['complete'] and data['pilot']['title_agreement']['pairs'] == 3
    assert data['pilot']['title_agreement']['observed_agreement'] == pytest.approx(2 / 3)
    vote(ledger, outside, 'alice', 'include')
    assert not s.snapshot(ledger, reviewer='bob')['pilot_open']
    assert len(s.snapshot(ledger, reviewer='bob')['queue']) == 7


def test_new_criteria_version_releases_old_pilot(ledger):
    sample = s.start_pilot(ledger, 'carol', 2, seed=1, expected_version=1)
    s.revise_criteria(ledger, 'Revised criteria', expected_version=1)
    outside = next(f'R{i:06d}' for i in range(1, 11) if f'R{i:06d}' not in sample)
    vote(ledger, outside, 'alice', 'include', version=2)
    assert s.snapshot(ledger)['pilot'] is None


# Exports and CLI

def test_export_includes_agreement_file_and_svg_line(ledger, tmp_path):
    votes(ledger, [II, EE, IE])
    export_review(ledger, tmp_path / 'report')
    data = json.loads((tmp_path / 'report/agreement.json').read_text(encoding='utf-8'))
    assert data['title']['pairs'] == 3 and 'pilot' in data
    manifest = json.loads((tmp_path / 'report/manifest.json').read_text(encoding='utf-8'))
    assert 'agreement.json' in manifest['files']
    svg = (tmp_path / 'report/prisma.svg').read_text(encoding='utf-8')
    assert "Title/abstract agreement (n=3)" in svg and "Cohen&#x27;s kappa" in svg
    assert 'Full-text agreement: no paired decisions' in svg


def test_cli_pilot_and_agreement(ledger, capsys):
    assert main(['review', 'pilot', '--db', str(ledger), '--version', '1', '--actor', 'carol', '--size', '2', '--seed', '9']) == 0
    sample = json.loads(capsys.readouterr().out)['pilot_records']
    assert len(sample) == 2
    assert main(['review', 'agreement', '--db', str(ledger)]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result['pilot']['records'] == sample and result['title']['pairs'] == 0
    assert main(['review', 'status', '--db', str(ledger)]) == 0
    assert 'agreement' in json.loads(capsys.readouterr().out)
