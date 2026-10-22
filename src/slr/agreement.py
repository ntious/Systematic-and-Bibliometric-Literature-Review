"""Inter-rater agreement for paired include/exclude screening decisions."""
from collections import Counter

CATEGORIES = ('include', 'exclude')
NOTE = ('Agreement uses only records both reviewers decided independently in this criteria version; adjudications are excluded. '
        'Kappa depends on prevalence and rater bias, so read it with observed agreement, PABAK and the contingency table. '
        'Conventional labels such as "substantial" are not validity thresholds.')


def paired_agreement(pairs):
    """Cohen's kappa, prevalence- and bias-adjusted kappa and observed agreement.

    pairs: iterable of (reviewer_a, reviewer_b) decisions, each 'include' or 'exclude'.
    Kappa is None when it is undefined (no pairs, or expected agreement of 1 because
    both reviewers used a single identical category throughout).
    """
    pairs = list(pairs)
    if any(a not in CATEGORIES or b not in CATEGORIES for a, b in pairs):
        raise ValueError('Agreement pairs must be include/exclude decisions')
    n = len(pairs)
    table = Counter(f'{a}/{b}' for a, b in pairs)
    result = {'pairs': n, 'table': {f'{a}/{b}': table[f'{a}/{b}'] for a in CATEGORIES for b in CATEGORIES},
              'observed_agreement': None, 'expected_agreement': None, 'cohen_kappa': None, 'pabak': None,
              'kappa_undefined_reason': None}
    if not n:
        result['kappa_undefined_reason'] = 'no paired decisions'
        return result
    observed = (table['include/include'] + table['exclude/exclude']) / n
    a_include = (table['include/include'] + table['include/exclude']) / n
    b_include = (table['include/include'] + table['exclude/include']) / n
    expected = a_include * b_include + (1 - a_include) * (1 - b_include)
    result.update(observed_agreement=observed, expected_agreement=expected, pabak=2 * observed - 1)
    if expected >= 1:
        result['kappa_undefined_reason'] = 'both reviewers used one identical category for every record'
    else:
        result['cohen_kappa'] = (observed - expected) / (1 - expected)
    return result


def stage_agreement(votes, reviewers, records=None):
    """votes: {record_id: {actor: event}} for one stage; restrict to `records` when given."""
    first, second = reviewers
    pairs, both_excluded, same_reason = [], 0, 0
    for record_id in sorted(votes):
        if records is not None and record_id not in records:
            continue
        cast = votes[record_id]
        if first in cast and second in cast:
            a, b = cast[first], cast[second]
            pairs.append((a['value'], b['value']))
            if a['value'] == b['value'] == 'exclude':
                both_excluded += 1
                same_reason += a['reason'] == b['reason']
    result = paired_agreement(pairs)
    result['reviewers'] = [first, second]
    result['exclusion_reason_agreement'] = {'both_excluded': both_excluded, 'same_primary_reason': same_reason}
    return result
