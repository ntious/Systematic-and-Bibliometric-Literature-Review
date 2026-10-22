"""Offline synthetic evidence workflow; does not call a model or use real studies."""
import argparse
import json
from pathlib import Path
import subprocess
import sys

from slr import evidence as e
from slr.evidence_cli import export_evidence


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    folder = Path(args.output)
    folder.mkdir(parents=True, exist_ok=False)
    root = Path(__file__).resolve().parents[1]
    subprocess.run([sys.executable, str(root / 'Scripts/screening_demo.py'), '--output', str(folder / 'screening')], check=True)
    framework = json.loads((root / 'configs/evidence_framework.json').read_text())
    database = folder / 'evidence.sqlite'
    e.initialize(database, folder / 'screening/review.sqlite', framework)
    source = e.add_source(database, 'R000001', root / 'Examples/evidence_report.txt', 'fulltext', 'Synthetic demonstration text')
    items = []
    quotes = {
        'study_design': ('a descriptive survey', 1),
        'population': ('postgraduate students', 1),
        'sample_size': ('120 postgraduate students', 1),
        'setting': ('one fictional university', 2),
        'methods': ('The survey measured self-reported use of AI writing tools.', 1),
        'variables': ('self-reported use of AI writing tools', 1),
        'findings': ('Sixty respondents reported using an AI writing tool.', 2),
        'limitations': ('The single-institution setting limits generalizability.', 2)
    }
    for definition in framework['fields']:
        key = definition['id']
        reported = key in quotes
        quote, page = quotes.get(key, ('', 1))
        items.append({'key': key, 'status': 'reported' if reported else 'not_reported', 'value': quote if reported else None,
            'anchors': [{'source_id': source, 'page': page, 'quote': quote}] if reported else [], 'evidence_ids': [],
            'uncertainty': 'low' if reported else 'unknown', 'rationale': 'Demonstration extraction from supplied synthetic text.'})
    proposals = e.submit(database, 'extract', 'R000001', {'items': items}, {'method': 'manual', 'actor': 'alice'})
    for proposal in proposals:
        e.review(database, proposal, 'bob', 'approve', 'Checked the synthetic source and the scope of missing information.', support_confirmed=True)
    appraisals = [{'key': d['id'], 'status': 'not_reported', 'value': None, 'anchors': [], 'evidence_ids': [],
                  'uncertainty': 'unknown', 'rationale': 'The short synthetic text does not establish this appraisal domain.'} for d in framework['appraisal']['domains']]
    proposals = e.submit(database, 'appraise', 'R000001', {'items': appraisals}, {'method': 'manual', 'actor': 'alice'})
    for proposal in proposals:
        e.review(database, proposal, 'bob', 'approve', 'Confirmed insufficient information in the supplied synthetic text.', support_confirmed=True)
    packet = e.prepare(database, 'extract', 'R000001')
    (folder / 'prepared-request.json').write_text(json.dumps(packet, ensure_ascii=False, indent=2)+'\n')
    result = export_evidence(database, folder / 'report')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
