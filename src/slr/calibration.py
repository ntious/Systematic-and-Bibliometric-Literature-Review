"""Reproducible lexical query diagnostics and an explicitly unjudged review sample."""
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
import re
import unicodedata

from .models import Record, normalize_doi
from .reporting import write_csv, write_json
from .screening import verify_run


def normalized(text):
    return ' '.join(unicodedata.normalize('NFKC', text).casefold().split())


def validate_policy(policy):
    if not isinstance(policy, dict) or not isinstance(policy.get('groups'), dict) or not 1 <= len(policy['groups']) <= 8:
        raise ValueError('Calibration policy needs 1–8 term groups')
    for name, terms in policy['groups'].items():
        if not isinstance(name, str) or not name.strip() or not isinstance(terms, list) or not 1 <= len(terms) <= 100 or any(not isinstance(t,str) or not t.strip() or len(t)>200 for t in terms):
            raise ValueError('Each calibration group needs a name and 1–100 nonempty literal terms')
    count = policy.get('sample_per_stratum',2)
    if type(count) is not int or not 1 <= count <= 10:
        raise ValueError('sample_per_stratum must be between 1 and 10')
    known = policy.get('known_items',[])
    if not isinstance(known,list) or len(known)>100 or any(not isinstance(k,dict) or not isinstance(k.get('title'),str) or not k['title'].strip() or (k.get('doi') is not None and not isinstance(k['doi'],str)) for k in known):
        raise ValueError('Known-item checks need titles and optional DOI strings; at most 100 items')
    return policy


def matches(text, term):
    return bool(re.search(r'(?<!\w)'+re.escape(normalized(term))+r'(?!\w)', text))


def diagnostics(rows, policy):
    validate_policy(policy)
    result=[]
    for index,row in enumerate(rows,1):
        r=Record(**row)
        text=normalized(r.title+' '+r.abstract)
        hits={name:[term for term in terms if matches(text,term)] for name,terms in policy['groups'].items()}
        missing=[name for name,terms in hits.items() if not terms]
        queries=sorted({p['query'] for p in r.provenance if isinstance(p.get('query'),str)}) or ['(query provenance unavailable)']
        result.append({'index':index,'source':r.source,'source_id':r.source_id,'title':r.title,'doi':r.doi,
                       'abstract':r.abstract,'year':r.year,'url':r.url,'queries':queries,'hits':hits,
                       'missing_groups':missing,'all_groups_present':not missing,
                       'stratum':'limited-metadata' if not r.abstract else 'incomplete-cues' if missing else 'all-groups-present'})
    return result


def calibrate_run(run_folder, policy, output):
    rows,_,_=verify_run(run_folder)
    validate_policy(policy)
    output=Path(output)
    output.mkdir(parents=True,exist_ok=False)
    write_json(output/'policy.json',policy)
    policy_hash=sha256((output/'policy.json').read_bytes()).hexdigest()
    checks=diagnostics(rows,policy)
    queries=sorted({q for r in checks for q in r['queries']})
    query_counts=[]
    sample={}
    for query in queries:
        subset=[r for r in checks if query in r['queries']]
        counts=Counter(r['stratum'] for r in subset)
        query_counts.append({'query':query,'retained_records':len(subset),
                             'all_groups_present':sum(r['all_groups_present'] for r in subset),
                             'strata':dict(counts)})
        for stratum in ('all-groups-present','incomplete-cues','limited-metadata'):
            pool=[r for r in subset if r['stratum']==stratum]
            pool.sort(key=lambda r:sha256((policy_hash+'|'+r['source']+'|'+r['source_id']).encode()).hexdigest())
            for row in pool[:policy.get('sample_per_stratum',2)]:
                item=sample.setdefault(row['index'],{**row,'sampled_for_queries':[]})
                item['sampled_for_queries'].append(query)
    known=[]
    for item in policy.get('known_items',[]):
        found=[r for r in checks if (item.get('doi') and normalize_doi(item['doi']) and normalize_doi(item['doi'])==r['doi']) or normalized(item['title'])==normalized(r['title'])]
        known.append({'title':item['title'],'doi':item.get('doi',''),'captured':bool(found),
                      'matches':[{'source':r['source'],'source_id':r['source_id']} for r in found],
                      'interpretation':'Illustrative known-item coverage only. Not independently adjudicated eligibility or a recall estimate.'})
    sample_rows=sorted(sample.values(),key=lambda r:r['index'])
    report={'status':'human-calibration-pending','retained_records':len(rows),
            'all_groups_present':sum(r['all_groups_present'] for r in checks),
            'missing_abstracts':sum(not r['abstract'] for r in checks),
            'per_query':query_counts,'known_items':known,'review_sample_size':len(sample_rows),
            'policy_sha256':policy_hash,'source_manifest_sha256':sha256((Path(run_folder)/'manifest.json').read_bytes()).hexdigest(),
            'limitations':['Literal title/abstract term cues are not semantic relevance, eligibility, precision or recall.',
                          'Missing text/cues are not exclusion decisions; full-text/indexed terms may explain provider matches.',
                          'Stratified capped samples are for calibration and cannot estimate overall precision without a justified design.',
                          'Known items are illustrative and not an independent reference set. No human judgment has been generated.']}
    write_json(output/'report.json',report)
    write_json(output/'record-diagnostics.json',checks)
    fields=['index','source','source_id','title','doi','year','abstract','url','stratum','missing_groups','sampled_for_queries','human_relevance','human_rationale','reviewer','reviewed_utc']
    write_csv(output/'human-review.csv',fields,[{**{k:r.get(k,'') for k in fields},
        'missing_groups':'; '.join(r['missing_groups']),'sampled_for_queries':json.dumps(r['sampled_for_queries'],ensure_ascii=False)} for r in sample_rows])
    lines=['# Query calibration: automated diagnostics', '',
           '**Human relevance validation is pending.** No eligibility votes or human judgments were generated.', '',
           f"Retained records: {len(rows)}. Records with every configured term-group cue: {report['all_groups_present']}. Missing abstracts: {report['missing_abstracts']}.", '',
           f"Reproducible stratified review sample: {len(sample_rows)} records in `human-review.csv`. Reviewer columns are blank.", '',
           '| Query | Retained | All term groups present |', '|---|---:|---:|']
    lines += ['| '+r['query'].replace('|','\\|')+' | '+str(r['retained_records'])+' | '+str(r['all_groups_present'])+' |' for r in query_counts]
    lines += ['', '## Limits', '']+['- '+item for item in report['limitations']]
    if known:
        lines += ['', '## Illustrative known-item coverage', '']+['- '+item['title']+': '+('captured' if item['captured'] else 'not captured in this bounded run') for item in known]
    (output/'REPORT.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    write_json(output/'manifest.json',{'status':'complete','mode':'automated-query-diagnostics',
        'policy_sha256':policy_hash,'source_manifest_sha256':report['source_manifest_sha256'],
        'files':{p.name:sha256(p.read_bytes()).hexdigest() for p in sorted(output.iterdir())}})
    return report


def compare_calibrations(baseline, revision, output):
    """Compare verified diagnostics under an identical policy; never infer precision."""
    def verified(folder):
        root=Path(folder)
        manifest=json.loads((root/'manifest.json').read_text())
        if manifest.get('status')!='complete' or manifest.get('mode')!='automated-query-diagnostics':
            raise ValueError('Only completed calibration artifacts can be compared')
        if not {'report.json','policy.json','human-review.csv'} <= manifest.get('files',{}).keys():
            raise ValueError('Calibration manifest lacks required files')
        for name,digest in manifest['files'].items():
            if Path(name).name!=name or '/' in name or '\\' in name:
                raise ValueError('Invalid calibration artifact path')
            if sha256((root/name).read_bytes()).hexdigest()!=digest:
                raise ValueError('Calibration artifact hash mismatch')
        report=json.loads((root/'report.json').read_text())
        if report['policy_sha256']!=sha256((root/'policy.json').read_bytes()).hexdigest():
            raise ValueError('Calibration policy hash mismatch')
        return report
    old,new=verified(baseline),verified(revision)
    if old['policy_sha256']!=new['policy_sha256']:
        raise ValueError('Compare query revisions with the same calibration policy')
    captured_before={r['title'] for r in old['known_items'] if r['captured']}
    captured_after={r['title'] for r in new['known_items'] if r['captured']}
    lost=sorted(captured_before-captured_after)
    report={'status':'needs-investigation' if lost else 'human-calibration-pending',
            'baseline':{k:old[k] for k in ('retained_records','all_groups_present','missing_abstracts','review_sample_size')},
            'revision':{k:new[k] for k in ('retained_records','all_groups_present','missing_abstracts','review_sample_size')},
            'known_items_captured_before':len(captured_before),'known_items_captured_after':len(captured_after),
            'lost_known_items':lost,'policy_sha256':new['policy_sha256'],
            'recommendation':'Do not automatically adopt the query revision. Investigate cap/ranking, source syntax/fields and version aliases; review the sample before expanding coverage.' if lost else 'Human relevance validation is still required; cue counts do not establish search validity.',
            'limitations':new['limitations']}
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    write_json(output/'comparison.json',report)
    lines=['# Query-revision diagnostic comparison','',f"Status: **{report['status']}**",'',
           f"Baseline: {old['retained_records']} retained; {old['all_groups_present']} with all term-group cues.",
           f"Revision: {new['retained_records']} retained; {new['all_groups_present']} with all term-group cues.",'',
           f"Illustrative known items captured: {len(captured_before)} → {len(captured_after)}.",'',report['recommendation'],'',
           'These are metadata diagnostics, not eligible-study counts, human precision or recall. The known items were not independently adjudicated. Source coverage and caps limit interpretation.']
    (output/'REPORT.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    if (Path(revision).parent/'session.json').exists():
        from .pipeline import SessionJournal
        journal=SessionJournal.reopen(Path(revision).parent)
        journal.record('query-revision comparison','warning' if lost else 'info',
                       f'Illustrative known-item coverage changed {len(captured_before)} → {len(captured_after)}. Human validation remains pending.',
                       evidence=str(output/'REPORT.md'),remedy=report['recommendation'])
    return report
