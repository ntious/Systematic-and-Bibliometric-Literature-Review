"""Frozen, question-only evaluation of provisional analysis recommendations.

Observed-method overlap is not accuracy or independent suitability validation.
"""
import argparse
from hashlib import sha256
import json
from pathlib import Path

from .analysis_knowledge import canonical, recommend, validate


def digest(value):
    return sha256(canonical(value).encode('utf-8')).hexdigest()


def write_bundle(output, files):
    root = Path(output)
    root.mkdir(parents=True, exist_ok=False)
    written = []
    try:
        for name, value in files.items():
            path = root / name
            written.append(path)
            path.write_bytes((value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + '\n').encode('utf-8'))
        manifest = {'files': {p.name: sha256(p.read_bytes()).hexdigest() for p in written}}
        path = root / 'manifest.json'
        written.append(path)
        path.write_bytes((json.dumps(manifest, indent=2, sort_keys=True) + '\n').encode('utf-8'))
    except Exception:
        for path in written:
            path.unlink(missing_ok=True)
        root.rmdir()
        raise
    return root


def validate_cases(cases):
    if not isinstance(cases, list) or not cases:
        raise ValueError('Evaluation requires a nonempty case list')
    ids = set()
    for case in cases:
        if case['case_id'] in ids:
            raise ValueError('Duplicate evaluation case ID')
        ids.add(case['case_id'])
        if not isinstance(case['question'], str) or not case['question'].strip():
            raise ValueError('Each case requires an original question/objective')
        if not case.get('anchors') or not case.get('cohort') or not case.get('discipline'):
            raise ValueError('Each case requires anchors, cohort and discipline')
    return cases


def predict(graph, cases):
    validate(graph)
    validate_cases(cases)
    # Only this text enters the recommender: no actual analyses, full text or labels.
    results = [{'case_id': c['case_id'], 'cohort': c['cohort'], 'discipline': c['discipline'],
                'question_sha256': digest(c['question']), 'recommendation': recommend(graph, c['question'])} for c in cases]
    return dict(schema='litatlas-knowledge-evaluation-v1', catalogue_sha256=digest(graph),
                cases_sha256=digest(cases), cases=cases, predictions=results,
                notice='Unranked question-only candidates. Annotation and independent review are separate. No execution approval.')


def score(predictions, annotations):
    cases = validate_cases(predictions['cases'])
    if digest(cases) != predictions['cases_sha256']:
        raise ValueError('Case content hash mismatch')
    expected_ids = {c['case_id'] for c in cases}
    ids = [a['case_id'] for a in annotations]
    if len(set(ids)) != len(ids) or set(ids) != expected_ids:
        raise ValueError('Annotation IDs must match prediction cases exactly once')
    labels = {a['case_id']: a for a in annotations}
    results = {r['case_id']: r for r in predictions['predictions']}
    if set(results) != expected_ids or len(results) != len(predictions['predictions']):
        raise ValueError('Prediction IDs do not match cases')
    rows = []
    for case in cases:
        prediction = results[case['case_id']]
        result = prediction['recommendation']
        if prediction['question_sha256'] != digest(case['question']) or result['question'] != case['question']:
            raise ValueError('Prediction question mismatch')
        if result['catalogue_sha256'] != predictions['catalogue_sha256']:
            raise ValueError('Prediction catalogue mismatch')
        annotation = labels[case['case_id']]
        observed_list = annotation['observed_method_ids']
        if len(set(observed_list)) != len(observed_list):
            raise ValueError('Duplicate observed-method labels')
        if not annotation.get('anchors') or not annotation.get('annotator'):
            raise ValueError('Observed labels require source anchors and annotator')
        if annotation.get('status') == 'unresolved' and observed_list:
            raise ValueError('Unresolved annotation cannot contain observed labels')
        candidates = {c['method']['id'] for c in result['candidates']}
        observed = set(observed_list)
        matched = candidates & observed
        rows.append(dict(case_id=case['case_id'], cohort=case['cohort'], discipline=case['discipline'],
                         scorable=annotation.get('status') != 'unresolved', candidate_count=len(candidates), observed_count=len(observed), overlap_count=len(matched),
                         overlapping_methods=sorted(matched), missed_observed_methods=sorted(observed - candidates),
                         additional_candidates=sorted(candidates - observed),
                         outside_catalogue=annotation.get('outside_catalogue', []),
                         any_overlap=bool(matched), abstained=not candidates,
                         question=case['question'], annotation=annotation))
    groups = {}
    for cohort in sorted({r['cohort'] for r in rows}):
        selected = [r for r in rows if r['cohort'] == cohort]
        scorable = sum(r['scorable'] for r in selected)
        observed = sum(r['observed_count'] for r in selected)
        candidate_total = sum(r['candidate_count'] for r in selected)
        overlap = sum(r['overlap_count'] for r in selected)
        any_count = sum(r['any_overlap'] for r in selected)
        groups[cohort] = dict(cases=len(selected), cases_with_candidates=sum(not r['abstained'] for r in selected),
                             abstentions=sum(r['abstained'] for r in selected), cases_with_any_observed_overlap=any_count,
                             scorable_cases=scorable, any_overlap_rate=any_count / scorable if scorable else None,
                             observed_method_labels=observed, matched_labels=overlap,
                             within_catalogue_observed_label_recall=overlap / observed if observed else None,
                             candidate_labels=candidate_total,
                             published_overlap_fraction=overlap / candidate_total if candidate_total else None,
                             mean_candidates=candidate_total / len(selected),
                             unsupported_observed_cases=sum(bool(r['outside_catalogue']) for r in selected))
    return dict(schema='litatlas-knowledge-evaluation-score-v1', predictions_sha256=digest(predictions),
                annotations_sha256=digest(annotations), cohorts=groups, rows=rows,
                notice='Single-annotator observed-method agreement unless independently adjudicated. No true accuracy, suitability precision, or top-k accuracy is established. Additional candidates are not automatically wrong; omitted observed methods are not automatically necessary. Abstention is not automatically appropriate.')


def summary_markdown(report):
    lines = ['# Recommender pilot evaluation', '', report['notice'], '',
             '| Cohort | Cases | With candidates | Any observed-method overlap | Abstentions | Matched/observed labels |',
             '| --- | ---: | ---: | ---: | ---: | ---: |']
    for name, group in report['cohorts'].items():
        lines.append(f"| {name} | {group['cases']} | {group['cases_with_candidates']} | {group['cases_with_any_observed_overlap']} (among {group['scorable_cases']} scorable) | {group['abstentions']} | {group['matched_labels']}/{group['observed_method_labels']} |")
    return '\n'.join(lines) + '\n'


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    predict_parser = sub.add_parser('predict')
    predict_parser.add_argument('--catalogue', required=True)
    predict_parser.add_argument('--cases', required=True)
    predict_parser.add_argument('--output', required=True)
    score_parser = sub.add_parser('score')
    score_parser.add_argument('--predictions', required=True)
    score_parser.add_argument('--annotations', required=True)
    score_parser.add_argument('--output', required=True)
    args = parser.parse_args(argv)
    read = lambda p: json.loads(Path(p).read_text(encoding='utf-8'))
    try:
        if args.command == 'predict':
            result = predict(read(args.catalogue), read(args.cases))
            files = {'predictions.json': result}
        else:
            path = Path(args.predictions)
            manifest = read(path.parent / 'manifest.json')
            if sha256(path.read_bytes()).hexdigest() != manifest['files'][path.name]:
                raise ValueError('Frozen prediction file hash mismatch')
            result = score(read(path), read(args.annotations))
            files = {'scores.json': result, 'SUMMARY.md': summary_markdown(result)}
        folder = write_bundle(args.output, files)
    except (ValueError, OSError, KeyError, TypeError) as exc:
        parser.exit(1, f'slr knowledge-evaluate: {exc}\n')
    print(f'Evaluation artifacts written to {folder}')
    return 0
