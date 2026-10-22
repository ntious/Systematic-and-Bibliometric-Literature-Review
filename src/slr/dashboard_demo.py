"""Synthetic data for an isolated dashboard workspace, never real research claims."""
from copy import deepcopy
import json
from pathlib import Path

from . import evidence as evidence_store
from . import screening
from .imports import import_files

TOPICS = [
    ('Generative AI', 'Learning design', 'Feedback', 'Student agency', 'Writing support', 'Reflection', 'Teacher practice'),
    ('Learning analytics', 'Adaptive learning', 'Personalization', 'Engagement', 'Intelligent tutors', 'Student success', 'Digital learning'),
    ('AI literacy', 'Assessment', 'Academic integrity', 'Higher education', 'Critical thinking', 'Responsible AI', 'Equity'),
]
AUTHORS = [('Avery Morgan', 'Jordan Chen', 'Riley Patel', 'Sam Rivera'),
           ('Taylor Kim', 'Casey Okafor', 'Drew Santos', 'Alex Nguyen'),
           ('Morgan Ellis', 'Cameron Lee', 'Sage Ibrahim', 'Quinn Bennett')]
TITLES = ['Rethinking feedback with generative AI', 'Designing adaptive learning experiences',
          'Building AI literacy in higher education', 'Student agency in AI-supported classrooms',
          'Understanding trust in learning analytics', 'Assessment practices for a changing classroom',
          'Human–AI collaboration in academic writing', 'Personalized support and student engagement',
          'Responsible adoption of educational AI', 'From automated feedback to reflective learning',
          'Teaching critical evaluation of AI outputs', 'Mapping equitable access to intelligent tutors']

FRAMEWORK = {'id': 'dashboard-synthetic-v1', 'fields': [
    {'id': 'study_design', 'description': 'Reported study design'},
    {'id': 'population', 'description': 'Reported study population'},
    {'id': 'sample_size', 'description': 'Reported sample size and units'},
    {'id': 'findings', 'description': 'Reported findings without causal extrapolation'}],
    'appraisal': {'id': 'illustrative-dashboard-v1', 'description': 'Synthetic demonstration questions, not a validated risk-of-bias instrument.',
    'domains': [{'id': 'selection', 'description': 'Is participant selection described?', 'judgments': ['low_concern', 'some_concern', 'unclear']},
                {'id': 'measurement', 'description': 'Are measurements described?', 'judgments': ['low_concern', 'some_concern', 'unclear']}]}}


def create_demo(root, count=64, completed=False):
    root = Path(root)
    root.mkdir(parents=True, exist_ok=False)
    rows = []
    for i in range(count):
        group = i % 3
        team = list(AUTHORS[group][:2 + i % 3])
        if i % 7 == 0:
            team.append(AUTHORS[(group + 1) % 3][0])
        offset = (i // 3) % len(TOPICS[group])
        keywords = [TOPICS[group][(offset + j) % len(TOPICS[group])] for j in range(3)]
        if i % 5 == 0:
            keywords.append(TOPICS[(group + 1) % 3][1])
        rows.append({'source': ['synthetic-openalex', 'synthetic-crossref', 'synthetic-pubmed'][i % 3],
            'source_id': f'DEMO-{i + 1:03}', 'doi': f'10.9999/synthetic-dashboard-{i + 1}',
            'title': TITLES[i % len(TITLES)] + (f': synthetic study {i // len(TITLES) + 1}' if i >= len(TITLES) else ''),
            'abstract': f'SYNTHETIC DEMONSTRATION. This fictional report explores {keywords[0].lower()} in higher education. A descriptive survey of {80 + i * 7} students examines experiences, reported benefits, and limitations of AI-supported learning. The single-institution setting limits generalization. This record is not research evidence.',
            'authors': team, 'year': 2020 + (i * 3 + i // 3) % 6, 'journal': ['Synthetic Journal of Learning Design', 'Synthetic Educational Technology Review', 'Synthetic Research in Higher Education'][group],
            'citations': (i * 17 + 11) % 130 if i % 9 else None, 'keywords': keywords,
            'references': [f'10.9999/synthetic-reference-{group * 4 + j}' for j in range(1, 5)] + ([f'10.9999/synthetic-reference-{(group + 1) % 3 * 4 + 1}'] if i % 4 == 0 else [])})
    if not completed:
        for i in range(8):
            duplicate = deepcopy(rows[i])
            duplicate['source'] = 'synthetic-crossref'
            duplicate['source_id'] += '-DUP'
            rows.append(duplicate)
    source = root / 'synthetic-input.json'
    source.write_text(json.dumps(rows, indent=2), encoding='utf-8')
    run = import_files([source], root / 'retrieval', 'synthetic-demonstration')
    db = root / 'screening.sqlite'
    name = 'Human–AI collaboration' if completed else 'AI in education'
    screening.initialize(db, run, name, ['Avery', 'Jordan'], 'Riley',
        'SYNTHETIC DEMONSTRATION. Include empirical studies of AI in higher education. Exclude non-empirical work, wrong populations and records outside education. Assess full texts independently; report one primary reason for exclusion.')
    for i in range(1, count + 1):
        record = f'R{i:06}'
        if completed:
            decision = 'include' if i <= 8 else 'exclude'
            for actor in ('Avery', 'Jordan'):
                screening.decide(db, record, actor, 'title', decision, 'Wrong population' if decision == 'exclude' else '', expected_version=1)
            if decision == 'include':
                screening.record_retrieval(db, record, 'Avery', 'retrieved', expected_version=1)
                for actor in ('Avery', 'Jordan'):
                    screening.decide(db, record, actor, 'fulltext', 'include', expected_version=1)
                screening.link_study(db, record, 'Riley', f'S{max(1, i - 1):03}', expected_version=1)
        elif i <= 14:
            for actor in ('Avery', 'Jordan'):
                screening.decide(db, record, actor, 'title', 'include', expected_version=1)
            if i <= 10:
                screening.record_retrieval(db, record, 'Avery', 'retrieved', expected_version=1)
                for actor in ('Avery', 'Jordan'):
                    screening.decide(db, record, actor, 'fulltext', 'include' if i <= 8 else 'exclude', 'Wrong study design' if i > 8 else '', expected_version=1)
                if i <= 8:
                    screening.link_study(db, record, 'Riley', f'S{max(1, i - 1):03}', expected_version=1)
            elif i == 11:
                screening.record_retrieval(db, record, 'Avery', 'not_retrieved', 'Library request unsuccessful', expected_version=1)
        elif i <= 32:
            for actor in ('Avery', 'Jordan'):
                screening.decide(db, record, actor, 'title', 'exclude', ['Wrong population', 'Not empirical', 'Outside education'][i % 3], expected_version=1)
        elif i <= 36:
            screening.decide(db, record, 'Avery', 'title', 'include', expected_version=1)
            screening.decide(db, record, 'Jordan', 'title', 'exclude', 'Wrong population', expected_version=1)
        elif i <= 44:
            screening.decide(db, record, 'Avery', 'title', 'include', expected_version=1)
    evidence_db = None
    if completed:
        evidence_db = root / 'evidence.sqlite'
        evidence_store.initialize(evidence_db, db, FRAMEWORK)
        for i in range(1, 9):
            text = f'SYNTHETIC DEMONSTRATION — NOT RESEARCH EVIDENCE.\nThis report describes a descriptive survey of {80 + (i - 1) * 7} students.\nThe population was students in higher education.\fRespondents reported improved access to feedback.\nNo causal effect was estimated. The fictional single-institution setting limits generalization.'
            path = root / f'source-{i}.txt'
            path.write_text(text, encoding='utf-8')
            sid = evidence_store.add_source(evidence_db, f'R{i:06}', path, 'fulltext', f'Synthetic article {i} · supplied text')
            if i > 4:
                continue
            values = {'study_design': ('a descriptive survey', 1), 'population': ('students in higher education', 1),
                      'sample_size': (f'{80 + (i - 1) * 7} students', 1), 'findings': ('Respondents reported improved access to feedback.', 2)}
            items = []
            for key, (value, page) in values.items():
                quote = 'An invented quote that does not occur.' if i == 4 and key == 'findings' else value
                items.append({'key': key, 'status': 'reported', 'value': value, 'anchors': [{'source_id': sid, 'page': page, 'quote': quote}],
                              'evidence_ids': [], 'uncertainty': 'medium', 'rationale': 'Synthetic demonstration extraction; check source support.'})
            ids = evidence_store.submit(evidence_db, 'extract', f'R{i:06}', {'items': items}, {'method': 'manual', 'actor': 'Avery'})
            appraisals = [{'key': domain['id'], 'status': 'not_reported', 'value': None, 'anchors': [], 'evidence_ids': [], 'uncertainty': 'unknown',
                           'rationale': 'Insufficient information in the short supplied synthetic text.'} for domain in FRAMEWORK['appraisal']['domains']]
            ids += evidence_store.submit(evidence_db, 'appraise', f'R{i:06}', {'items': appraisals}, {'method': 'manual', 'actor': 'Avery'})
            if i <= 3:
                for proposal in ids:
                    evidence_store.review(evidence_db, proposal, 'Jordan', 'approve', 'Checked synthetic source and the limits of the supplied text.', support_confirmed=True)
    return {'name': name, 'question': 'How is artificial intelligence shaping teaching, learning and assessment in higher education?',
            'screening_db': str(db.resolve()), 'run': str(run.resolve()), 'evidence_db': str(evidence_db.resolve()) if evidence_db else None, 'demo': True}
