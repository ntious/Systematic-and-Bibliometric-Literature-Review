"""Conservative date-window checks against provider-reported publication metadata."""
from calendar import monthrange
from datetime import date
import re


def date_interval(value):
    """Return possible date range; partial dates never acquire invented precision."""
    if not isinstance(value, str) or not re.fullmatch(r'\d{4}(?:-\d{2})?(?:-\d{2})?', value):
        return None
    try:
        parts = [int(p) for p in value.split('-')]
        year = parts[0]
        if len(parts) == 1:
            return date(year,1,1), date(year,12,31)
        month = parts[1]
        if len(parts) == 2:
            return date(year,month,1), date(year,month,monthrange(year,month)[1])
        point = date(*parts)
        return point, point
    except (ValueError, OverflowError):
        return None


def audit_dates(records, start=None, end=None):
    lower = date.fromisoformat(start) if start else date.min
    upper = date.fromisoformat(end) if end else date.max
    retained, checks = [], []
    for record in records:
        value = next((p['publication_date'] for p in record.provenance if p.get('publication_date')), '')
        interval = date_interval(value)
        if not interval and not value and type(record.year) is int:
            value = str(record.year)
            interval = date_interval(value)
        if not start and not end:
            status = 'not-requested'
        elif interval is None:
            status = 'unknown-or-invalid'
        elif interval[1] < lower or interval[0] > upper:
            status = 'outside'
        elif lower <= interval[0] and interval[1] <= upper:
            status = 'within'
        else:
            status = 'uncertain-boundary'
        checks.append({'source':record.source,'source_id':record.source_id,'doi':record.doi,
                       'reported_date':value,'status':status})
        if status != 'outside':
            retained.append(record)
    return retained, {'date_from':start,'date_to':end,'captured_records':len(records),
                     'outside_window':sum(r['status']=='outside' for r in checks),
                     'uncertain_dates':sum(r['status'] in ('unknown-or-invalid','uncertain-boundary') for r in checks),
                     'checks':checks,'policy':'Exclude only dates wholly outside the window; retain uncertain dates for human verification. Dates are provider-reported, not independently established.'}
