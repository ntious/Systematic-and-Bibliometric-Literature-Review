"""Source-linked reasoning guides. No automatic scientific quality assessment."""
from copy import deepcopy
from hashlib import sha256
import json

VERSION='question-frameworks-v2'
CATALOG={
 'PICO':{'label':'PICO','purpose':'Intervention/effectiveness questions; do not assume applicability to every discipline or question.',
 'components':{'population':'Population or problem','intervention':'Intervention','comparison':'Comparison','outcomes':'Outcomes'},
 'sources':[{'title':'Cochrane Handbook chapter 4','url':'https://www.cochrane.org/authors/handbooks-and-manuals/handbook/current/chapter-04','version':'v6.5.1; chapter updated March 2025; consulted 2026-10-25'}],
 'limits':'Generally unsuitable for diagnostic accuracy, prognosis, qualitative or methods questions. Search blocks need not include every component. Comparator/outcome restrictions may reduce sensitivity.'},
 'PCC':{'label':'PCC','purpose':'Scoping review questions: population, concept and context.',
 'components':{'population':'Population','concept':'Concept','context':'Context'},
 'sources':[{'title':'JBI: defining and aligning objectives/questions','url':'https://jbi-global.atlassian.net/wiki/spaces/MANUAL/pages/355862687/10.2.3%2BDefining%2Band%2Baligning%2Bthe%2Bobjective%2Bs%2Band%2Bquestion%2Bs','version':'Living guidance; consulted 2026-10-25'}],
 'limits':'Applicability and justified absent components depend on the review purpose; PCC is not a universal requirement.'},
 'SPIDER':{'label':'SPIDER','purpose':'An alternative structure for qualitative and mixed-method questions.',
 'components':{'sample':'Sample','phenomenon':'Phenomenon of interest','design':'Design','evaluation':'Evaluation','research_type':'Research type'},
 'sources':[{'title':'Cooke, Smith and Booth: Beyond PICO (2012)','url':'https://pubmed.ncbi.nlm.nih.gov/22829486/','version':'2012; DOI 10.1177/1049732312452938'}],
 'limits':'The original paper calls for wider testing. This does not establish better retrieval or question quality.'},
 'custom':{'label':'Custom or no listed framework fits','purpose':'Explain your chosen structure or why no listed framework fits.',
 'components':{'researcher_defined':'Describe your structure, components or reason for not using a listed framework'},
 'sources':[],'limits':'Researcher-defined reasoning; no endorsement or established-framework claim is inferred.'}}


# Component labels are short paraphrases, not reproduced checklist instruments.
_JBI_SEARCH={'title':'JBI 2.4.3: Developing a Search Strategy',
 'url':'https://jbi-global.atlassian.net/wiki/spaces/MANUAL/pages/652279828/2.4.3%2BDeveloping%2Ba%2BSearch%2BStrategy',
 'version':'Page updated May 5, 2025; consulted 2026-10-25'}
for _key, _purpose, _components in (
 ('PICo','Qualitative questions about experiences in a setting.',{'population':'Population','phenomenon':'Phenomenon of interest','context':'Context'}),
 ('CoCoPop','Questions about the frequency of a condition in a population and setting.',{'condition':'Condition','context':'Context','population':'Population'}),
 ('PIRD','Diagnostic questions involving index and reference tests.',{'population':'Population','index_test':'Index test','reference_test':'Reference test','diagnosis':'Diagnosis'})):
    CATALOG[_key]={'label':_key,'purpose':_purpose,'components':_components,'sources':[deepcopy(_JBI_SEARCH)],
      'limits':'Choose according to the review purpose with human methodological review; component presence does not establish suitability.'}
CATALOG['PECO']={'label':'PECO','purpose':'Questions organized around exposure rather than an assigned intervention.',
 'components':{'population':'Population','exposure':'Exposure','comparison':'Comparator','outcomes':'Outcomes'},
 'sources':deepcopy(CATALOG['PCC']['sources']),
 'limits':'Exposure comparisons do not by themselves establish causality. The researcher must justify applicability.'}
CATALOG['CIMO']={'label':'CIMO','purpose':'Design-oriented synthesis of how an intervention may work in context.',
 'components':{'context':'Context','intervention':'Intervention','mechanisms':'Mechanisms','outcomes':'Outcomes'},
 'sources':[{'title':'Denyer, Tranfield and van Aken: Developing Design Propositions through Research Synthesis',
 'url':'https://journals.sagepub.com/doi/10.1177/0170840607088020','version':'2008; DOI 10.1177/0170840607088020; abstract checked 2026-10-25'}],
 'limits':'A design-oriented reasoning structure; inferred mechanisms require evidence and human interpretation, not a causal-certification claim.'}
CATALOG['PICOC']={'label':'PICOC','purpose':'Software-engineering questions incorporating the setting of a comparison.',
 'components':{'population':'Population','intervention':'Intervention','comparison':'Comparison','outcomes':'Outcomes','context':'Context'},
 'sources':[{'title':'Kitchenham and Charters: Guidelines for performing Systematic Literature Reviews in Software Engineering',
 'url':'https://ebse.webspace.durham.ac.uk/wp-content/uploads/sites/49/2022/08/Systematic-reviews-5-8.pdf',
 'version':'EBSE-2007-01, version 2.3, July 9, 2007; section 5.3.2; checked 2026-10-25'}],
 'limits':'Software-engineering guidance; do not assume every review or search needs all five components.'}

for _key, _spec in CATALOG.items():
    _spec['id'] = _key
    _spec['version'] = '2'
    _spec['not_suitable_for'] = ('Diagnostic accuracy, prognosis, qualitative or methods questions' if _key=='PICO' else 'Questions outside the stated purpose without a researcher justification')
    _spec['search_note'] = 'Reasoning components are not mandatory search blocks. Inclusion and omission of concepts need a separately reviewed search strategy.'


def digest(value):
    return sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def reasoning_state(record):
    if not record:
        return 'unmapped'
    if record.get('catalog_version') != VERSION:
        return 'legacy-unassessed'
    values = list(record.get('components', {}).values())
    if any(v['status'] == 'unreviewed' for v in values):
        return 'selected-not-reasoned'
    if any(v['status'] in ('missing', 'unclear') for v in values):
        return 'reasoned-with-unresolved'
    return 'reasoned'


def reasoning_records(draft):
    maps = draft.get('framework_maps', [])
    return [dict(question_index=i, question_sha256=sha256(q.encode()).hexdigest(),
                 state=reasoning_state(next((m for m in maps if m['question_index']==i and m['question_sha256']==sha256(q.encode()).hexdigest()), None)))
            for i, q in enumerate(draft.get('questions', []))]


def catalog():
    return {'version':VERSION,'frameworks':deepcopy(CATALOG),
      'notice':'Reasoning guides, not grades. Mappings are researcher statements; no automatic semantic assessment. Independent QF-1 review informed this contract; catalog expansion remains separate work.'}


def validate(maps,questions):
    if not isinstance(maps,list) or len(maps)>len(questions):raise ValueError('Provide at most one framework map per question')
    result=[];seen=set()
    for item in maps:
        if not isinstance(item,dict) or set(item)!={'question_index','framework','rationale','components'}:raise ValueError('Invalid framework mapping fields')
        index=item['question_index'];key=item['framework']
        if type(index) is not int or not 0<=index<len(questions) or index in seen:raise ValueError('Invalid or repeated question index')
        if not isinstance(key,str) or key not in CATALOG:raise ValueError('Choose an available framework or a documented custom approach')
        rationale=item['rationale']
        if not isinstance(rationale,str) or not 10<=len(rationale.strip())<=4000:raise ValueError('Explain the framework choice in 10–4000 characters')
        components=item['components'];spec=CATALOG[key]
        if key == 'custom' and isinstance(components,dict):
            if len(components)>8 or any(not isinstance(n,str) or not n.strip() or len(n)>100 for n in components):
                raise ValueError('Use zero to eight named custom components; explain a no-fit choice in the rationale')
        elif not isinstance(components,dict) or set(components)!=set(spec['components']):raise ValueError('Map the selected framework components explicitly')
        checked={}
        for name,value in components.items():
            if not isinstance(value,dict) or not {'status','text'} <= set(value) or set(value)-{'status','text','provenance','quote'} or value['status'] not in ('unreviewed','identified','missing','unclear','not_applicable'):raise ValueError('Invalid component status')
            if not isinstance(value['text'],str) or len(value['text'])>2000:raise ValueError('Component notes must be text up to 2000 characters')
            if value['status']!='unreviewed' and not value['text'].strip():raise ValueError('Explain identified, unclear or not-applicable components')
            provenance=value.get('provenance','unreviewed')
            quote=value.get('quote','')
            if provenance not in ('unreviewed','question_quote','researcher_context') or not isinstance(quote,str):
                raise ValueError('Choose question quote or researcher context provenance')
            if value['status']=='identified' and provenance=='unreviewed':
                raise ValueError('Identified components require explicit provenance')
            if provenance=='question_quote' and (not quote.strip() or quote not in questions[index]):
                raise ValueError('Quote must be an exact substring of this question')
            if provenance!='question_quote' and quote:
                raise ValueError('Only literal question support may carry a question quote')
            checked[name]={'status':value['status'],'text':value['text'].strip(),'provenance':provenance,'quote':quote}
        result.append({'question_index':index,'question_sha256':sha256(questions[index].encode()).hexdigest(),
          'framework':key,'rationale':rationale.strip(),'components':checked,'catalog_version':VERSION,
          'guidance':deepcopy(spec),'guidance_sha256':digest(spec),'entry_version':spec['version'],'origin':'researcher','notice':'Human reasoning record; not an automated validation or score.'})
        seen.add(index)
    for record in result:
        record['reasoning_state']=reasoning_state(record)
    return sorted(result,key=lambda m:m['question_index'])
