import json

import pytest

from slr.analysis_knowledge import seed
from slr.knowledge_evaluation import predict, score, write_bundle, main


def cases():
    return [dict(case_id='A', question='What types of interventions exist?', cohort='core', discipline='education',
                 anchors=[dict(pdf_page=2,quote='What types of interventions exist?')]),
            dict(case_id='B', question='How is the concept understood?', cohort='core', discipline='social',
                 anchors=[dict(pdf_page=3,quote='How is the concept understood?')])]


def annotations():
    return [dict(case_id='A',observed_method_ids=['category-counts','characteristics'],annotator='test',anchors=[{'pdf_page':4,'quote':'counted categories'}]),
            dict(case_id='B',observed_method_ids=['structured-synthesis'],annotator='test',anchors=[{'pdf_page':5,'quote':'grouped findings'}])]


def test_question_only_input_ignores_labels_and_freezes_graph():
    data=cases()
    first=predict(seed(),data)
    data[0]['observed_method_ids']=['meta-random']
    second=predict(seed(),data)
    assert first['predictions']==second['predictions']
    assert not any(p['recommendation']['approval_recorded'] for p in first['predictions'])


def test_hand_calculated_overlap_and_abstention():
    result=score(predict(seed(),cases()),annotations())
    group=result['cohorts']['core']
    # A produces five descriptive candidates; B none. Two of three observed labels match.
    assert group['cases']==2 and group['cases_with_candidates']==1
    assert group['abstentions']==1 and group['cases_with_any_observed_overlap']==1
    assert group['any_overlap_rate']==0.5
    assert group['within_catalogue_observed_label_recall']==pytest.approx(2/3)
    assert group['published_overlap_fraction']==pytest.approx(2/5)
    assert 'accuracy' not in group


@pytest.mark.parametrize('kind',['case','question','catalogue','duplicate_prediction'])
def test_binding_changes_are_rejected(kind):
    frozen=predict(seed(),cases())
    if kind=='case':frozen['cases'][0]['question']='changed'
    if kind=='question':frozen['predictions'][0]['recommendation']['question']='changed'
    if kind=='catalogue':frozen['predictions'][0]['recommendation']['catalogue_sha256']='changed'
    if kind=='duplicate_prediction':frozen['predictions'].append(frozen['predictions'][0])
    with pytest.raises(ValueError):score(frozen,annotations())


@pytest.mark.parametrize('labels',[[],annotations()+[annotations()[0]]])
def test_missing_or_duplicate_annotations_rejected(labels):
    with pytest.raises(ValueError,match='Annotation IDs'):score(predict(seed(),cases()),labels)


def test_existing_artifacts_never_overwritten(tmp_path):
    output=write_bundle(tmp_path/'out',{'data.json':{'test':True}})
    with pytest.raises(FileExistsError):write_bundle(output,{'data.json':{'test':False}})
    assert json.loads((output/'data.json').read_text())=={'test':True}


def test_cli_rejects_tampered_frozen_prediction(tmp_path):
    folder=write_bundle(tmp_path/'predictions',{'predictions.json':predict(seed(),cases())})
    (folder/'predictions.json').write_text('{}')
    labels=tmp_path/'labels.json';labels.write_text(json.dumps(annotations()))
    with pytest.raises(SystemExit):
        main(['score','--predictions',str(folder/'predictions.json'),'--annotations',str(labels),'--output',str(tmp_path/'scores')])
    assert not (tmp_path/'scores').exists()


def test_unresolved_annotation_excluded_from_agreement_denominator():
    labels=annotations()
    labels[1].update(status='unresolved',observed_method_ids=[])
    group=score(predict(seed(),cases()),labels)['cohorts']['core']
    assert group['cases']==2
    assert group['scorable_cases']==1
    assert group['any_overlap_rate']==1
    labels[1]['observed_method_ids']=['characteristics']
    with pytest.raises(ValueError,match='Unresolved'):
        score(predict(seed(),cases()),labels)
