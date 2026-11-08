"""Import UTF-8 CSV, RIS, and normalized JSON metadata without provider access."""
import argparse
import csv
from datetime import datetime, timezone
from hashlib import sha256
import io
import json
from pathlib import Path
import re

from . import __version__
from .models import Record
from .reporting import unsafe_cell, write_json, write_results

ALIASES = {
    'title': ('title', 'article title', 'document title'),
    'doi': ('doi', 'digital object identifier (doi)'),
    'source_id': ('source_id', 'eid', 'ut', 'accession number'),
    'abstract': ('abstract',), 'authors': ('authors', 'author full names'),
    'year': ('year', 'publication year'), 'journal': ('journal', 'source title', 'publication title'),
    'keywords': ('keywords', 'author keywords'), 'references': ('references', 'cited references'),
    'author_ids': ('author_ids',), 'reference_count': ('reference_count',),
    'venue_id': ('venue_id', 'source id'), 'issns': ('issns', 'issn'), 'publisher': ('publisher',),
    'affiliations': ('affiliations',), 'affiliation_ids': ('affiliation_ids',), 'countries': ('countries', 'country codes'),
    'subject_areas': ('subject_areas', 'subject areas'), 'subject_taxonomy': ('subject_taxonomy', 'subject taxonomy'),
    'citations': ('citations', 'cited by', 'times cited, wos core'), 'url': ('url', 'link'),
}


def _number(value, name):
    if value is None or value == '':
        return None
    if isinstance(value, bool) or not re.fullmatch(r'\d+', str(value).strip()):
        raise ValueError(f'Invalid {name}: {value!r}')
    return int(value)


def _record(fields, source, index, digest):
    title = fields.get('title', '').strip()
    if not title:
        raise ValueError(f'Missing title in record {index}')
    authors = fields.get('authors', '')
    if isinstance(authors, str):
        if authors.lstrip().startswith('['):
            authors = json.loads(authors)
        else:
            authors = [v.strip() for v in authors.split(';') if v.strip()]
    if not isinstance(authors, list) or not all(isinstance(a, str) for a in authors):
        raise ValueError(f'Invalid authors in record {index}')
    arrays = {}
    for key in ('keywords', 'references', 'author_ids', 'issns', 'affiliations', 'affiliation_ids', 'countries', 'subject_areas'):
        value = fields.get(key, '')
        if isinstance(value, str):
            value = json.loads(value) if value.lstrip().startswith('[') else [v.strip() for v in value.split(';') if v.strip()]
        arrays[key] = value
    identifier = fields.get('source_id') or f'{digest[:16]}:{index}'
    return Record(source=source, source_id=identifier, title=title, doi=fields.get('doi', ''),
        abstract=fields.get('abstract', ''), authors=authors, **arrays, reference_count=_number(fields.get('reference_count'), 'reference_count'), year=_number(fields.get('year'), 'year'),
        journal=fields.get('journal', ''), venue_id=fields.get('venue_id', ''), publisher=fields.get('publisher', ''), subject_taxonomy=fields.get('subject_taxonomy', ''), citations=_number(fields.get('citations'), 'citations'), url=fields.get('url', ''),
        provenance=[{'source': source, 'source_id': identifier, 'file_sha256': digest, 'row': index}])


def parse_csv(text, source, digest):
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise ValueError('CSV has no header')
    headers = [name.strip().lower() for name in reader.fieldnames]
    if len(headers) != len(set(headers)):
        raise ValueError('CSV has duplicate column names')
    if not any(name in headers for name in ALIASES['title']):
        raise ValueError('CSV requires Title or Article Title column')
    records = []
    for index, row in enumerate(reader, 1):
        if None in row or any(value is None for value in row.values()):
            raise ValueError(f'CSV row {index} does not match header columns')
        row = {key.strip().lower(): unsafe_cell(value.strip()) for key, value in row.items()}
        fields = {key: next((row[a] for a in aliases if row.get(a)), '') for key, aliases in ALIASES.items()}
        records.append(_record(fields, source, index, digest))
    return records


def parse_ris(text, source, digest):
    """Preserve repeated authors and wrapped fields; reject incomplete records."""
    entries, current, last = [], None, None
    for line in text.splitlines():
        if not line.strip():
            continue
        match = re.match(r'^([A-Z0-9]{2})  -\s?(.*)$', line)
        if not match:
            if current is None or last is None or not line.startswith((' ', '\t')):
                raise ValueError('Invalid RIS tag or continuation')
            current[last][-1] += ' ' + line.strip()
            continue
        tag, value = match.groups()
        if tag == 'TY':
            if current is not None:
                raise ValueError('RIS record missing ER terminator')
            current = {}
        elif current is None:
            raise ValueError('RIS record must begin with TY')
        if tag == 'ER':
            entries.append(current)
            current, last = None, None
        else:
            current.setdefault(tag, []).append(value)
            last = tag
    if current is not None:
        raise ValueError('RIS record missing ER terminator')
    records = []
    for index, entry in enumerate(entries, 1):
        def first(*tags):
            return next((entry[t][0] for t in tags if entry.get(t)), '')
        date = first('PY', 'Y1')
        fields = {'title': first('TI', 'T1'), 'doi': first('DO'), 'source_id': first('ID', 'AN'),
                  'authors': entry.get('AU', entry.get('A1', [])), 'year': date[:4],
                  'keywords': entry.get('KW', []), 'references': entry.get('CR', []),
                  'issns': entry.get('SN', []), 'publisher': first('PB'), 'affiliations': entry.get('AD', []), 'abstract': first('AB', 'N2'), 'journal': first('JO', 'JF', 'T2'), 'url': first('UR')}
        records.append(_record(fields, source, index, digest))
    return records


def import_files(paths, output, source):
    if not isinstance(source, str) or not source.strip():
        raise ValueError('Source label is required')
    records, originals, inputs = [], [], []
    for index, path in enumerate(map(Path, paths), 1):
        raw = path.read_bytes()
        digest = sha256(raw).hexdigest()
        text = raw.decode('utf-8-sig')
        suffix = path.suffix.lower()
        if suffix == '.csv':
            found = parse_csv(text, source, digest)
        elif suffix == '.ris':
            found = parse_ris(text, source, digest)
        elif suffix == '.json':
            rows = json.loads(text)
            if not isinstance(rows, list):
                raise ValueError('JSON input must be an array of normalized records')
            found = [Record(**r) for r in rows]
            for row, record in enumerate(found, 1):
                record.provenance.append({'source': source, 'source_id': record.source_id, 'file_sha256': digest, 'row': row})
        else:
            raise ValueError('Input extension must be .csv, .ris, or .json')
        if not found:
            raise ValueError(f'No records in {path.name}')
        records.extend(found)
        filename = f'input-{index:03d}{suffix}'
        originals.append((filename, raw))
        inputs.append({'file': filename, 'original_name': path.name, 'sha256': digest, 'records': len(found), 'source_label': source})
    if not records:
        raise ValueError('Provide at least one input file')
    folder = Path(output)
    folder.mkdir(parents=True, exist_ok=False)
    for filename, raw in originals:
        (folder / filename).write_bytes(raw)
    write_results(folder, records)
    write_json(folder / 'manifest.json', {'status': 'complete', 'mode': 'import',
        'finished_utc': datetime.now(timezone.utc).isoformat(), 'inputs': inputs,
        'searches': [], 'config': {}, 'version': __version__,
        'files': {p.name: sha256(p.read_bytes()).hexdigest() for p in sorted(folder.iterdir())}})
    return folder


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', nargs='+', required=True)
    parser.add_argument('--source', required=True, help='Origin label, e.g. scopus or web-of-science')
    parser.add_argument('--output', required=True)
    args = parser.parse_args(argv)
    try:
        folder = import_files(args.input, args.output, args.source)
    except (ValueError, TypeError, OSError, KeyError) as exc:
        parser.exit(1, f'slr import: {exc}\n')
    print(f'Imported review artifacts written to {folder}')
    return 0
