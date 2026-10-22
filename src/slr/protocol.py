"""Structured PRISMA-P protocols, append-only amendments linked to criteria versions, and registry drafts."""
import argparse
from datetime import date
from hashlib import sha256
import json
from pathlib import Path
import sqlite3

from . import __version__
from .reporting import write_json
from .screening import _check_version, _context, connect, now

FRAMEWORKS = ('PICO', 'PECO', 'PCC', 'SPIDER', 'other')
STAGES = ('planned', 'searching', 'screening', 'extraction', 'synthesis', 'completed')
MAX_TEXT = 20000
TEXT, BOOL, DATE, TEXTS, MAPPING = 'text', 'bool', 'date', 'texts', 'mapping'

# Every protocol field; unknown keys are rejected so typos never silently drop content.
SCHEMA = {
    'title': TEXT, 'is_update': BOOL, 'update_of': TEXT,
    'registration': {'registry': TEXT, 'id': TEXT},
    'authors': [{'name': TEXT, 'affiliation': TEXT, 'email': TEXT, 'contributions': TEXT, 'contact': BOOL}],
    'guarantor': TEXT, 'amendment_plan': TEXT,
    'support': {'sources': TEXT, 'sponsor': TEXT, 'sponsor_role': TEXT},
    'conflicts_of_interest': TEXT,
    'review_type': TEXT, 'stage': TEXT, 'anticipated_start': DATE, 'anticipated_completion': DATE,
    'condition_or_domain': TEXT, 'context': TEXT, 'language': TEXT, 'country': TEXT, 'keywords': TEXTS,
    'rationale': TEXT,
    'objectives': {'question': TEXT, 'framework': TEXT, 'elements': MAPPING},
    'eligibility': {'study_characteristics': TEXT, 'report_characteristics': TEXT},
    'information_sources': [{'name': TEXT, 'platform': TEXT, 'planned_date': DATE, 'coverage': TEXT}],
    'search_strategy': {'database': TEXT, 'strategy': TEXT},
    'data_management': TEXT, 'selection_process': TEXT, 'data_collection_process': TEXT, 'data_items': TEXT,
    'outcomes': {'main': TEXT, 'additional': TEXT, 'prioritization': TEXT},
    'risk_of_bias': TEXT,
    'synthesis': {'quantitative': BOOL, 'criteria': TEXT, 'methods': TEXT, 'additional_analyses': TEXT, 'non_quantitative': TEXT},
    'meta_bias': TEXT, 'confidence': TEXT, 'dissemination': TEXT,
}

REGISTRY_NOTICE = ('Draft field mapping for copy-and-paste. Registry forms change; verify every field label and requirement '
                   'against the current registry form before submitting. Nothing is submitted automatically.')


def _check(value, spec, path):
    if isinstance(spec, dict):
        if not isinstance(value, dict):
            raise ValueError(f'{path or "protocol"} must be an object')
        unknown = sorted(set(value) - set(spec))
        if unknown:
            raise ValueError(f'Unknown protocol field: {(path + ".") if path else ""}{unknown[0]}')
        for key, item in value.items():
            _check(item, spec[key], f'{path}.{key}' if path else key)
    elif isinstance(spec, list):
        if not isinstance(value, list) or len(value) > 200:
            raise ValueError(f'{path} must be a list of at most 200 entries')
        for index, item in enumerate(value):
            _check(item, spec[0], f'{path}[{index}]')
    elif spec == TEXT:
        if not isinstance(value, str) or len(value) > MAX_TEXT:
            raise ValueError(f'{path} must be text of at most {MAX_TEXT} characters')
    elif spec == BOOL:
        if type(value) is not bool:
            raise ValueError(f'{path} must be true or false')
    elif spec == DATE:
        try:
            if not isinstance(value, str) or len(value) != 10:
                raise ValueError
            date.fromisoformat(value)
        except ValueError:
            raise ValueError(f'{path} must be a YYYY-MM-DD date') from None
    elif spec == TEXTS:
        if not isinstance(value, list) or len(value) > 50 or any(not isinstance(v, str) or len(v) > 200 for v in value):
            raise ValueError(f'{path} must be a list of at most 50 short text values')
    elif spec == MAPPING:
        if not isinstance(value, dict) or len(value) > 12 or any(not isinstance(k, str) or not k.strip() or not isinstance(v, str) or len(v) > MAX_TEXT for k, v in value.items()):
            raise ValueError(f'{path} must map at most 12 element names to text')


def validate(protocol):
    """Check types and vocabularies. Incomplete drafts are valid; see checklist() for completeness."""
    _check(protocol, SCHEMA, '')
    framework = get(protocol, 'objectives.framework')
    if framework and framework not in FRAMEWORKS:
        raise ValueError(f'objectives.framework must be one of {", ".join(FRAMEWORKS)}')
    if protocol.get('stage') and protocol['stage'] not in STAGES:
        raise ValueError(f'stage must be one of {", ".join(STAGES)}')
    if protocol.get('anticipated_start') and protocol.get('anticipated_completion') and protocol['anticipated_start'] > protocol['anticipated_completion']:
        raise ValueError('anticipated_start must not be after anticipated_completion')
    return json.loads(json.dumps(protocol, ensure_ascii=False))


def get(protocol, path):
    value = protocol
    for key in path.split('.'):
        if not isinstance(value, dict):
            return None
        value = value.get(key)
    return value


def _filled(value):
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, dict)):
        return bool(value)
    return value is not None


def filled(protocol, *paths):
    return all(_filled(get(protocol, path)) for path in paths)


def _contact(protocol):
    authors = protocol.get('authors') or []
    return (bool(authors) and all(filled(a, 'name', 'affiliation') for a in authors)
            and any(a.get('contact') is True and filled(a, 'email') for a in authors))


def _no_sponsor(protocol):
    return (get(protocol, 'support.sponsor') or '').strip().casefold() in ('', 'none', 'not applicable', 'n/a')


ADMIN, INTRO, METHODS = 'Administrative information', 'Introduction', 'Methods'
ALWAYS = lambda p: True  # noqa: E731
# (item, section, topic, fields, applies, reported) following the PRISMA-P 2015 checklist.
ITEMS = [
    ('1a', ADMIN, 'Identification', ['title'], ALWAYS, lambda p: filled(p, 'title')),
    ('1b', ADMIN, 'Update', ['is_update', 'update_of'], lambda p: p.get('is_update') is True, lambda p: filled(p, 'update_of')),
    ('2', ADMIN, 'Registration', ['registration.registry', 'registration.id'], ALWAYS, lambda p: filled(p, 'registration.registry', 'registration.id')),
    ('3a', ADMIN, 'Authors: contact', ['authors[].name', 'authors[].affiliation', 'authors[].email', 'authors[].contact'], ALWAYS, _contact),
    ('3b', ADMIN, 'Authors: contributions', ['authors[].contributions', 'guarantor'], ALWAYS,
     lambda p: bool(p.get('authors')) and all(filled(a, 'contributions') for a in p['authors']) and filled(p, 'guarantor')),
    ('4', ADMIN, 'Amendments', ['amendment_plan'], ALWAYS, lambda p: filled(p, 'amendment_plan')),
    ('5a', ADMIN, 'Support: sources', ['support.sources'], ALWAYS, lambda p: filled(p, 'support.sources')),
    ('5b', ADMIN, 'Support: sponsor', ['support.sponsor'], ALWAYS, lambda p: filled(p, 'support.sponsor')),
    ('5c', ADMIN, 'Support: role of sponsor or funder', ['support.sponsor_role'], lambda p: not _no_sponsor(p), lambda p: filled(p, 'support.sponsor_role')),
    ('6', INTRO, 'Rationale', ['rationale'], ALWAYS, lambda p: filled(p, 'rationale')),
    ('7', INTRO, 'Objectives', ['objectives.question', 'objectives.framework', 'objectives.elements'], ALWAYS,
     lambda p: filled(p, 'objectives.question', 'objectives.framework', 'objectives.elements')),
    ('8', METHODS, 'Eligibility criteria', ['eligibility.study_characteristics', 'eligibility.report_characteristics'], ALWAYS,
     lambda p: filled(p, 'eligibility.study_characteristics', 'eligibility.report_characteristics')),
    ('9', METHODS, 'Information sources', ['information_sources[].name', 'information_sources[].planned_date'], ALWAYS,
     lambda p: bool(p.get('information_sources')) and all(filled(s, 'name', 'planned_date') for s in p['information_sources'])),
    ('10', METHODS, 'Search strategy', ['search_strategy.database', 'search_strategy.strategy'], ALWAYS,
     lambda p: filled(p, 'search_strategy.database', 'search_strategy.strategy')),
    ('11a', METHODS, 'Study records: data management', ['data_management'], ALWAYS, lambda p: filled(p, 'data_management')),
    ('11b', METHODS, 'Study records: selection process', ['selection_process'], ALWAYS, lambda p: filled(p, 'selection_process')),
    ('11c', METHODS, 'Study records: data collection process', ['data_collection_process'], ALWAYS, lambda p: filled(p, 'data_collection_process')),
    ('12', METHODS, 'Data items', ['data_items'], ALWAYS, lambda p: filled(p, 'data_items')),
    ('13', METHODS, 'Outcomes and prioritization', ['outcomes.main', 'outcomes.prioritization'], ALWAYS,
     lambda p: filled(p, 'outcomes.main', 'outcomes.prioritization')),
    ('14', METHODS, 'Risk of bias in individual studies', ['risk_of_bias'], ALWAYS, lambda p: filled(p, 'risk_of_bias')),
    ('15a', METHODS, 'Synthesis: criteria for quantitative synthesis', ['synthesis.quantitative', 'synthesis.criteria'], ALWAYS,
     lambda p: type(get(p, 'synthesis.quantitative')) is bool and filled(p, 'synthesis.criteria')),
    ('15b', METHODS, 'Synthesis: quantitative methods', ['synthesis.methods'], lambda p: get(p, 'synthesis.quantitative') is not False,
     lambda p: filled(p, 'synthesis.methods')),
    ('15c', METHODS, 'Synthesis: additional analyses', ['synthesis.additional_analyses'], lambda p: get(p, 'synthesis.quantitative') is not False,
     lambda p: filled(p, 'synthesis.additional_analyses')),
    ('15d', METHODS, 'Synthesis: non-quantitative summary', ['synthesis.non_quantitative'], lambda p: get(p, 'synthesis.quantitative') is not True,
     lambda p: filled(p, 'synthesis.non_quantitative')),
    ('16', METHODS, 'Meta-bias(es)', ['meta_bias'], ALWAYS, lambda p: filled(p, 'meta_bias')),
    ('17', METHODS, 'Confidence in cumulative evidence', ['confidence'], ALWAYS, lambda p: filled(p, 'confidence')),
]


def checklist(protocol):
    protocol = validate(protocol)
    items = []
    for item, section, topic, fields, applies, reported in ITEMS:
        status = 'not_applicable' if not applies(protocol) else 'reported' if reported(protocol) else 'missing'
        items.append({'item': item, 'section': section, 'topic': topic, 'fields': fields, 'status': status})
    missing = [i['item'] for i in items if i['status'] == 'missing']
    return {'standard': 'PRISMA-P 2015 (Moher et al. Syst Rev 2015;4:1)', 'items': items, 'missing': missing, 'complete': not missing,
            'note': 'Status checks that each item has content, not that the content is methodologically adequate.'}


# Registry drafts -----------------------------------------------------------

def _render(value):
    if value is None or value == '' or value == [] or value == {}:
        return ''
    if isinstance(value, bool):
        return 'Yes' if value else 'No'
    if isinstance(value, list):
        return '; '.join(_render(v) for v in value if _render(v))
    if isinstance(value, dict):
        return '; '.join(f'{k.replace("_", " ")}: {_render(v)}' for k, v in value.items() if _render(v))
    return str(value).strip()


def _element(protocol, *names):
    elements = {k.strip().casefold(): v for k, v in (get(protocol, 'objectives.elements') or {}).items()}
    return next((elements[n] for n in names if _filled(elements.get(n))), '')


def _contact_author(protocol):
    return next((a for a in protocol.get('authors') or [] if a.get('contact')), {})


def _team(protocol):
    return '; '.join(' '.join(filter(None, [a.get('name', ''), f"({a['affiliation']})" if a.get('affiliation') else ''])) for a in protocol.get('authors') or [])


def _sources(protocol):
    return '; '.join(' '.join(filter(None, [s.get('name', ''), f"via {s['platform']}" if s.get('platform') else '',
                                            f"(planned search {s['planned_date']})" if s.get('planned_date') else '',
                                            f"— {s['coverage']}" if s.get('coverage') else '']))
                     for s in protocol.get('information_sources') or [])


def _join(protocol, *paths):
    return '\n\n'.join(_render(get(protocol, p)) for p in paths if _render(get(protocol, p)))


def _synthesis(protocol):
    return _join(protocol, 'synthesis.criteria', 'synthesis.methods', 'synthesis.non_quantitative')


POPULATION = ('population', 'participants', 'p')
EXPOSURE = ('intervention', 'exposure', 'interventions', 'exposures', 'concept', 'phenomenon of interest', 'i', 'e')
COMPARATOR = ('comparator', 'comparison', 'control', 'c')

# (registry field label, protocol source description, getter)
PROSPERO = [
    ('Review title', 'title', lambda p: _render(p.get('title'))),
    ('Anticipated or actual start date', 'anticipated_start', lambda p: _render(p.get('anticipated_start'))),
    ('Anticipated completion date', 'anticipated_completion', lambda p: _render(p.get('anticipated_completion'))),
    ('Stage of review at time of submission', 'stage', lambda p: _render(p.get('stage'))),
    ('Named contact', 'authors[contact].name', lambda p: _render(_contact_author(p).get('name'))),
    ('Named contact email', 'authors[contact].email', lambda p: _render(_contact_author(p).get('email'))),
    ('Organisational affiliation of the review', 'authors[contact].affiliation', lambda p: _render(_contact_author(p).get('affiliation'))),
    ('Review team members and their organisational affiliations', 'authors', _team),
    ('Funding sources/sponsors', 'support', lambda p: _render(p.get('support'))),
    ('Conflicts of interest', 'conflicts_of_interest', lambda p: _render(p.get('conflicts_of_interest'))),
    ('Review question', 'objectives.question', lambda p: _render(get(p, 'objectives.question'))),
    ('Searches', 'information_sources', _sources),
    ('Search strategy', 'search_strategy', lambda p: _join(p, 'search_strategy.database', 'search_strategy.strategy')),
    ('Condition or domain being studied', 'condition_or_domain', lambda p: _render(p.get('condition_or_domain'))),
    ('Participants/population', 'objectives.elements[population]', lambda p: _element(p, *POPULATION)),
    ('Intervention(s), exposure(s)', 'objectives.elements[intervention/exposure]', lambda p: _element(p, *EXPOSURE)),
    ('Comparator(s)/control', 'objectives.elements[comparator]', lambda p: _element(p, *COMPARATOR)),
    ('Types of study to be included', 'eligibility.study_characteristics', lambda p: _render(get(p, 'eligibility.study_characteristics'))),
    ('Context', 'context', lambda p: _render(p.get('context'))),
    ('Main outcome(s)', 'outcomes.main', lambda p: _render(get(p, 'outcomes.main'))),
    ('Additional outcome(s)', 'outcomes.additional', lambda p: _render(get(p, 'outcomes.additional'))),
    ('Data extraction (selection and coding)', 'selection_process; data_collection_process; data_items',
     lambda p: _join(p, 'selection_process', 'data_collection_process', 'data_items')),
    ('Risk of bias (quality) assessment', 'risk_of_bias', lambda p: _render(p.get('risk_of_bias'))),
    ('Strategy for data synthesis', 'synthesis', _synthesis),
    ('Analysis of subgroups or subsets', 'synthesis.additional_analyses', lambda p: _render(get(p, 'synthesis.additional_analyses'))),
    ('Type and method of review', 'review_type', lambda p: _render(p.get('review_type'))),
    ('Language', 'language', lambda p: _render(p.get('language'))),
    ('Country', 'country', lambda p: _render(p.get('country'))),
    ('Dissemination plans', 'dissemination', lambda p: _render(p.get('dissemination'))),
    ('Keywords', 'keywords', lambda p: _render(p.get('keywords'))),
    ('Details of any existing review of the same topic by the same authors', 'update_of', lambda p: _render(p.get('update_of'))),
]

OSF = [
    ('Review title', 'title', lambda p: _render(p.get('title'))),
    ('Authors and affiliations', 'authors', _team),
    ('Type of review', 'review_type', lambda p: _render(p.get('review_type'))),
    ('Current review stage', 'stage', lambda p: _render(p.get('stage'))),
    ('Start date', 'anticipated_start', lambda p: _render(p.get('anticipated_start'))),
    ('End date', 'anticipated_completion', lambda p: _render(p.get('anticipated_completion'))),
    ('Background', 'rationale', lambda p: _render(p.get('rationale'))),
    ('Primary research question(s)', 'objectives.question', lambda p: _render(get(p, 'objectives.question'))),
    ('Question framework and elements', 'objectives.framework; objectives.elements', lambda p: _join(p, 'objectives.framework', 'objectives.elements')),
    ('Dependent variables / outcomes', 'outcomes', lambda p: _render(p.get('outcomes'))),
    ('Funding', 'support', lambda p: _render(p.get('support'))),
    ('Conflicts of interest', 'conflicts_of_interest', lambda p: _render(p.get('conflicts_of_interest'))),
    ('Databases', 'information_sources[].name', lambda p: _render([s.get('name', '') for s in p.get('information_sources') or []])),
    ('Interfaces', 'information_sources[].platform', lambda p: _render([s.get('platform', '') for s in p.get('information_sources') or []])),
    ('Inclusion and exclusion criteria', 'eligibility', lambda p: _render(p.get('eligibility'))),
    ('Query strings', 'search_strategy', lambda p: _join(p, 'search_strategy.database', 'search_strategy.strategy')),
    ('Screening procedure, reliability and reconciliation', 'selection_process', lambda p: _render(p.get('selection_process'))),
    ('Data management and sharing', 'data_management', lambda p: _render(p.get('data_management'))),
    ('Data collection', 'data_collection_process; data_items', lambda p: _join(p, 'data_collection_process', 'data_items')),
    ('Risk of bias assessment', 'risk_of_bias', lambda p: _render(p.get('risk_of_bias'))),
    ('Synthesis plan', 'synthesis', _synthesis),
    ('Meta-bias assessment', 'meta_bias', lambda p: _render(p.get('meta_bias'))),
    ('Certainty of evidence', 'confidence', lambda p: _render(p.get('confidence'))),
    ('Dissemination', 'dissemination', lambda p: _render(p.get('dissemination'))),
]


def registry_fields(protocol, registry):
    protocol = validate(protocol)
    mapping = {'prospero': PROSPERO, 'osf': OSF}[registry]
    fields = [{'field': label, 'protocol_source': source, 'value': getter(protocol)} for label, source, getter in mapping]
    for row in fields:
        row['status'] = 'filled' if row['value'] else 'needs_entry'
    template = ('PROSPERO registration form' if registry == 'prospero' else 'OSF Generalized Systematic Review Registration template')
    return {'registry': registry, 'template': template, 'notice': REGISTRY_NOTICE, 'fields': fields,
            'needs_entry': [r['field'] for r in fields if r['status'] == 'needs_entry']}


# Append-only protocol ledger ------------------------------------------------

PROTOCOL_TABLES = [
    '''CREATE TABLE IF NOT EXISTS protocol (version INTEGER PRIMARY KEY, criteria_version INTEGER NOT NULL REFERENCES criteria(version),
       content TEXT NOT NULL, sha256 TEXT NOT NULL, actor TEXT NOT NULL, amendment TEXT, changed_sections TEXT NOT NULL, created_utc TEXT NOT NULL)''',
    "CREATE TRIGGER IF NOT EXISTS immutable_protocol_update BEFORE UPDATE ON protocol BEGIN SELECT RAISE(ABORT,'append-only protocol'); END",
    "CREATE TRIGGER IF NOT EXISTS immutable_protocol_delete BEFORE DELETE ON protocol BEGIN SELECT RAISE(ABORT,'append-only protocol'); END",
]


def _canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def _has_table(conn):
    return conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='protocol'").fetchone() is not None


def save(database, protocol, actor, *, expected_version, amendment=None):
    """Append a protocol version. Later versions are amendments with a description and rationale."""
    content = validate(protocol)
    with connect(database) as conn:
        for statement in PROTOCOL_TABLES:  # executescript would commit the open transaction
            conn.execute(statement)
        review, criteria_version = _context(conn)
        if actor not in review['reviewers'] + [review['adjudicator']]:
            raise ValueError('Actor is not assigned to this review')
        current = conn.execute('SELECT * FROM protocol ORDER BY version DESC LIMIT 1').fetchone()
        current_version = current['version'] if current else 0
        if type(expected_version) is not int or expected_version != current_version:
            raise ValueError(f'Stale protocol version: current version is {current_version}')
        if current is None:
            if amendment is not None:
                raise ValueError('The first protocol version is not an amendment')
            changed = sorted(content)
        else:
            if not isinstance(amendment, dict) or set(amendment) != {'description', 'rationale'} or not all(
                    isinstance(amendment[k], str) and amendment[k].strip() for k in amendment):
                raise ValueError('Protocol amendments need a description and a rationale')
            amendment = {k: v.strip() for k, v in amendment.items()}
            previous = json.loads(current['content'])
            changed = sorted(k for k in set(previous) | set(content) if previous.get(k) != content.get(k))
            if not changed:
                raise ValueError('Protocol content is unchanged; nothing to amend')
        text = _canonical(content)
        conn.execute('INSERT INTO protocol VALUES (?,?,?,?,?,?,?,?)',
                     (current_version + 1, criteria_version, text, sha256(text.encode()).hexdigest(), actor,
                      json.dumps(amendment, ensure_ascii=False) if amendment else None, json.dumps(changed), now()))
        return current_version + 1


def state(database):
    """Current protocol, amendment history and how criteria versions are documented."""
    with connect(database) as conn:
        _, criteria_version = _context(conn)
        criteria = [dict(r) for r in conn.execute('SELECT version, sha256, created_utc FROM criteria ORDER BY version')]
        rows = [dict(r) for r in conn.execute('SELECT * FROM protocol ORDER BY version')] if _has_table(conn) else []
    history = [{'version': r['version'], 'criteria_version': r['criteria_version'], 'sha256': r['sha256'], 'actor': r['actor'],
                'created_utc': r['created_utc'], 'amendment': json.loads(r['amendment']) if r['amendment'] else None,
                'changed_sections': json.loads(r['changed_sections'])} for r in rows]
    links = [{'criteria_version': c['version'], 'criteria_sha256': c['sha256'], 'criteria_created_utc': c['created_utc'],
              'protocol_versions': [h['version'] for h in history if h['criteria_version'] == c['version']]} for c in criteria]
    undocumented = [link['criteria_version'] for link in links if link['criteria_version'] > 1 and not link['protocol_versions']]
    current = json.loads(rows[-1]['content']) if rows else None
    return {'version': len(rows), 'protocol': current, 'checklist': checklist(current) if current else None,
            'history': history, 'criteria_version': criteria_version, 'criteria_links': links,
            'undocumented_criteria_revisions': undocumented,
            'note': 'A criteria revision is documented when a protocol version or amendment was saved under that criteria version.'}


# Exports ------------------------------------------------------------------

def _cell(value):
    return str(value).replace('\\', '\\\\').replace('|', '\\|').replace('\r', ' ').replace('\n', '<br>')


def _table(rows, columns):
    lines = ['| ' + ' | '.join(title for title, _ in columns) + ' |', '|' + '---|' * len(columns)]
    lines += ['| ' + ' | '.join(_cell(row[key]) for _, key in columns) + ' |' for row in rows]
    return lines


def _protocol_markdown(protocol, version_note):
    lines = [f"# {protocol.get('title') or 'Untitled review protocol'}", '', version_note, '']
    for key in SCHEMA:
        if _render(protocol.get(key)):
            value = _team(protocol) if key == 'authors' else _sources(protocol) if key == 'information_sources' else _render(protocol[key])
            lines += [f"## {key.replace('_', ' ').capitalize()}", '', value, '']
    return '\n'.join(lines)


def export(output, *, protocol_file=None, database=None):
    if (protocol_file is None) == (database is None):
        raise ValueError('Choose exactly one protocol file or review database')
    if database is not None:
        current = state(database)
        if current['protocol'] is None:
            raise ValueError('This review has no saved protocol')
        protocol = current['protocol']
        origin = {'mode': 'review-ledger', 'protocol_version': current['version'], 'sha256': current['history'][-1]['sha256']}
        note = f"Protocol version {current['version']} from the review ledger (criteria version {current['history'][-1]['criteria_version']})."
    else:
        raw = Path(protocol_file).read_bytes()
        protocol = validate(json.loads(raw.decode('utf-8-sig')))
        current = None
        origin = {'mode': 'protocol-file-unversioned', 'filename': Path(protocol_file).name, 'sha256': sha256(raw).hexdigest()}
        note = 'Draft from an unversioned protocol file; save it to a review ledger to track amendments.'
    report = checklist(protocol)
    folder = Path(output)
    folder.mkdir(parents=True, exist_ok=False)
    write_json(folder / 'protocol.json', protocol)
    write_json(folder / 'prisma-p-checklist.json', report)
    lines = ['# PRISMA-P 2015 checklist', '', note, '', report['note'], '']
    lines += _table(report['items'], [('Item', 'item'), ('Section', 'section'), ('Topic', 'topic'), ('Status', 'status')])
    (folder / 'prisma-p-checklist.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    for registry in ('prospero', 'osf'):
        fields = registry_fields(protocol, registry)
        write_json(folder / f'{registry}-fields.json', fields)
        lines = [f"# {fields['template']}: draft fields", '', f"**{fields['notice']}**", '']
        lines += _table(fields['fields'], [('Field', 'field'), ('Value', 'value'), ('Status', 'status'), ('Protocol source', 'protocol_source')])
        (folder / f'{registry}-fields.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    (folder / 'PROTOCOL.md').write_text(_protocol_markdown(protocol, note), encoding='utf-8')
    if current is not None:
        write_json(folder / 'protocol-history.json', {k: current[k] for k in ('version', 'history', 'criteria_links', 'undocumented_criteria_revisions', 'note')})
        lines = ['# Protocol amendments', '']
        for entry in current['history']:
            what = 'Initial protocol' if entry['amendment'] is None else f"Amendment: {entry['amendment']['description']} Rationale: {entry['amendment']['rationale']}"
            lines.append(f"- Version {entry['version']} ({entry['created_utc']}, {entry['actor']}, criteria version {entry['criteria_version']}): "
                         f"{_cell(what)} Changed sections: {', '.join(entry['changed_sections'])}.")
        if current['undocumented_criteria_revisions']:
            lines += ['', '**Criteria revisions without a protocol amendment:** ' + ', '.join(map(str, current['undocumented_criteria_revisions']))]
        (folder / 'amendments.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    write_json(folder / 'manifest.json', {'status': 'complete', 'version': __version__, 'created_utc': now(), 'origin': origin,
        'prisma_p_complete': report['complete'], 'files': {p.name: sha256(p.read_bytes()).hexdigest() for p in sorted(folder.iterdir())}})
    return {'output': str(folder), 'prisma_p_complete': report['complete'], 'missing_items': report['missing']}


def main(argv=None):
    parser = argparse.ArgumentParser(prog='slr protocol', description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    check = sub.add_parser('check', help='Validate a protocol file and report PRISMA-P completeness')
    check.add_argument('--file', required=True)
    saved = sub.add_parser('save', help='Save the first protocol version or an amendment to a review ledger')
    saved.add_argument('--db', required=True)
    saved.add_argument('--file', required=True)
    saved.add_argument('--actor', required=True)
    saved.add_argument('--expected-version', required=True, type=int, help='Current protocol version (0 before the first save)')
    saved.add_argument('--amendment', help='What changed (required after the first version)')
    saved.add_argument('--rationale', help='Why it changed (required after the first version)')
    status = sub.add_parser('status', help='Current protocol, amendments and criteria-version links')
    status.add_argument('--db', required=True)
    exported = sub.add_parser('export', help='PRISMA-P checklist, PROSPERO/OSF field drafts and amendment log')
    source = exported.add_mutually_exclusive_group(required=True)
    source.add_argument('--db')
    source.add_argument('--file')
    exported.add_argument('--output', required=True)
    args = parser.parse_args(argv)

    def load(path):
        return json.loads(Path(path).read_text(encoding='utf-8-sig'))
    try:
        if args.command == 'check':
            result = checklist(load(args.file))
        elif args.command == 'save':
            amendment = None
            if args.amendment is not None or args.rationale is not None:
                amendment = {'description': args.amendment or '', 'rationale': args.rationale or ''}
            result = {'protocol_version': save(args.db, load(args.file), args.actor, expected_version=args.expected_version, amendment=amendment)}
        elif args.command == 'status':
            result = state(args.db)
        else:
            result = export(args.output, protocol_file=args.file, database=args.db)
    except (ValueError, TypeError, OSError, KeyError, sqlite3.DatabaseError) as exc:
        parser.exit(1, f'slr protocol: {exc}\n')
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0
