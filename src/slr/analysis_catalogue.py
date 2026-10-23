"""Source register and provisional cross-disciplinary analysis knowledge graph.

Original short annotations, not redistributed articles or imported OWL classes.
Question mappings and eligibility checklists are local hypotheses, not validated rules.
"""
VERSION = '0.1.0'
SOURCES = [
    ('stato', 'STATO statistical ontology', 'https://stato-ontology.org/', 'Content and objectives',
     'Statistical vocabulary, inputs, conditions and outputs; not a question-to-method validation study.'),
    ('obcs', 'OBCS: standardized and reproducible statistical analysis', 'https://doi.org/10.1186/s13326-016-0100-2', 'Results and discussion',
     'Represents analysis workflow stages and links between methods and software; biomedical examples do not validate cross-disciplinary recommendations.'),
    ('munn', 'Munn et al. (2018), review typology', 'https://doi.org/10.1186/s12874-017-0468-4', 'Review typology and Table 1',
     'Connects question structures to review purposes in health sciences; broader use requires validation.'),
    ('right-review', 'Right Review (2022)', 'https://doi.org/10.1016/j.jclinepi.2022.03.004', 'Abstract: methods and results',
     'Structured decision support for synthesis-method selection; not validation of automatic keyword matching or statistical execution.'),
    ('retreat', 'Booth et al. (2018), RETREAT', 'https://doi.org/10.1016/j.jclinepi.2018.03.003', 'Abstract: results',
     'Qualitative method choice considers the question, epistemology, time, resources, expertise, audience and data.'),
    ('cochrane10', 'Cochrane Handbook Chapter 10', 'https://www.cochrane.org/authors/handbooks-and-manuals/handbook/current/chapter-10', 'Sections 10.2–10.14',
     'Quantitative synthesis guidance; effect measures, heterogeneity and methodological choices require review.'),
    ('cochrane12', 'Cochrane Handbook Chapter 12', 'https://www.cochrane.org/authors/handbooks-and-manuals/handbook/current/chapter-12', 'Sections 12.2–12.3',
     'Structured synthesis and displays when pooling is unsuitable; significance-based vote counting is not acceptable.'),
    ('cochrane13', 'Cochrane Handbook Chapter 13', 'https://www.cochrane.org/authors/handbooks-and-manuals/handbook/current/chapter-13', 'Sections 13.3–13.4',
     'Missing-evidence assessment and small-study effects; funnel asymmetry is not diagnostic of publication bias.'),
    ('cochrane14', 'Cochrane Handbook Chapter 14', 'https://www.cochrane.org/authors/handbooks-and-manuals/handbook/current/chapter-14', 'Sections 14.1–14.2',
     'Outcome-level certainty assessment for intervention reviews; do not impose GRADE universally.'),
    ('jbi', 'JBI qualitative evidence synthesis', 'https://jbi-global.atlassian.net/wiki/spaces/MANUAL/pages/355860547', 'JBI approach to qualitative evidence synthesis',
     'Methodological grounding for meta-aggregation; not interchangeable with keyword counting.'),
    ('campbell', 'White et al. (2020), evidence and gap maps', 'https://doi.org/10.1002/cl2.1125', 'Abstract and map framework guidance',
     'Systematically coded evidence availability; empty cells are bounded by search coverage and coding.'),
    ('vosviewer', 'VOSviewer manual 1.6.20', 'https://www.vosviewer.com/documentation/Manual_VOSviewer_1.6.20.pdf', 'Sections 2 and 3.5.4',
     'Bibliometric network types and counting choices; connectivity is not scientific quality.'),
    ('prov', 'W3C PROV-O', 'https://www.w3.org/TR/prov-o/', 'Starting Point terms',
     'Reference model for entities, activities, agents and derivations; local schema is not certified PROV-O conformance.'),
]

# Cue phrases are deliberately inspectable, English-only local hints, not literature claims.
INTENTS = {
    'describe': ('Describe characteristics', ['what types', 'which methods', 'characteristics', 'distribution']),
    'map': ('Map evidence', ['research gaps', 'evidence gaps', 'map the evidence', 'evidence map']),
    'effect': ('Assess comparative effects', ['effectiveness', 'effective', 'effect of', 'improve', 'compared with', 'compared to']),
    'frequency': ('Estimate frequency', ['prevalence', 'incidence', 'how common', 'what proportion']),
    'association': ('Assess associations', ['associated with', 'association', 'relationship between', 'risk factors']),
    'experience': ('Understand experiences', ['experience', 'experiences', 'perceptions', 'barriers', 'facilitators']),
    'explain': ('Explain mechanisms', ['mechanisms', 'for whom', 'under what circumstances']),
    'accuracy': ('Assess predictive/test performance', ['sensitivity', 'specificity', 'diagnostic accuracy', 'prediction performance']),
    'literature': ('Describe scholarly activity', ['publication trends', 'co-authorship', 'co-citation', 'bibliometric', 'keyword networks']),
    'robustness': ('Assess robustness', ['robustness', 'sensitivity analysis', 'robust']),
    'bias': ('Assess bias or certainty', ['risk of bias', 'certainty of evidence', 'reporting bias', 'publication bias']),
}


def method(identifier, label, kind, intents, requires, checks, outputs, source, locator, limitation):
    return dict(id=identifier, label=label, kind=kind, intents=intents.split(),
                required_fields=requires.split(), human_checks=checks.split(), outputs=outputs.split('|'),
                source=source, locator=locator, limitation=limitation,
                mapping_status='local_unvalidated_hypothesis', execution_status='not_integrated',
                curation_status='draft_requires_methodologist_review')


METHODS = [
    method('characteristics', 'Study characteristics table', 'description', 'describe map', 'study_id characteristics', 'counting_unit', 'table', 'cochrane12', '12.3.1', 'Describe captured evidence, not the entire field.'),
    method('category-counts', 'Categorical frequencies', 'description', 'describe map', 'study_id categories', 'counting_unit denominator multi_label', 'frequency table|bar chart', 'cochrane12', '12.3.1', 'Overlapping categories may sum beyond 100 percent.'),
    method('cross-tabulation', 'Cross-tabulated characteristics', 'description', 'describe map', 'study_id category_a category_b', 'counting_unit denominator multi_label', 'cross-tabulation|heatmap', 'cochrane12', '12.3.1', 'Descriptive cross-tabulation does not establish an association.'),
    method('evidence-map', 'Evidence availability map', 'mapping', 'map describe', 'study_id category_a category_b', 'counting_unit search_coverage coding_framework', 'evidence matrix|bubble map', 'campbell', 'Abstract and framework guidance', 'No identified evidence is not evidence of no effect.'),
    method('structured-synthesis', 'Structured synthesis without pooling', 'synthesis', 'effect association accuracy describe', 'study_id findings', 'grouping comparability outcome_selection', 'grouped findings table', 'cochrane12', '12.3.1', 'State synthesis rules; do not privilege convenient results.'),
    method('forest-unpooled', 'Forest plot without pooled estimate', 'display', 'effect association', 'study_id effect_estimate standard_error effect_measure', 'comparability effect_scale dependence', 'unpooled forest plot', 'cochrane12', '12.3.2', 'A common plot does not imply that numerical pooling is justified.'),
    method('effect-direction', 'Effect direction display', 'display', 'effect', 'study_id effect_direction outcome', 'direction_coding dependence outcome_selection', 'effect direction plot', 'cochrane12', '12.3.5', 'Direction alone discards magnitude and precision; do not count significance votes.'),
    method('harvest', 'Harvest plot', 'display', 'effect', 'study_id effect_direction study_characteristics', 'direction_coding grouping outcome_selection', 'harvest plot', 'cochrane12', '12.3.5', 'Symbol definitions and grouping decisions need approval.'),
    method('albatross', 'Albatross plot', 'display', 'effect association', 'study_id p_value sample_size effect_direction', 'compatible_p_values assumptions dependence', 'albatross plot', 'cochrane12', '12.3.4', 'Contours are approximate and require method-specific assumptions.'),
    method('effect-distribution', 'Distribution of study estimates', 'display', 'effect association', 'study_id effect_estimate effect_measure', 'comparability effect_scale dependence', 'box plot|study-level dot plot', 'cochrane12', '12.3.3', 'An unweighted distribution is not a pooled effect estimate.'),
    method('meta-fixed', 'Fixed-effect inverse-variance synthesis', 'statistical', 'effect association', 'study_id effect_estimate standard_error effect_measure', 'comparability common_effect dependence risk_of_bias effect_scale', 'forest plot|pooled estimate', 'cochrane10', '10.3.1', 'Requires a justified common-effect interpretation.'),
    method('meta-random', 'Random-effects synthesis', 'statistical', 'effect association', 'study_id effect_estimate standard_error effect_measure', 'comparability model_choice dependence risk_of_bias effect_scale', 'forest plot|pooled estimate|prediction interval when appropriate', 'cochrane10', '10.3.2 and 10.10.4', 'Random effects do not repair incompatible studies.'),
    method('mean-difference', 'Mean-difference synthesis', 'statistical', 'effect', 'study_id group_means group_sds group_sizes', 'same_scale comparability dependence risk_of_bias', 'effect table|forest plot', 'cochrane10', '10.5.1', 'Means must measure the same outcome on a compatible scale.'),
    method('standardized-difference', 'Standardized mean-difference synthesis', 'statistical', 'effect', 'study_id group_means group_sds group_sizes', 'same_construct scale_direction comparability dependence risk_of_bias', 'effect table|forest plot', 'cochrane10', '10.5.1', 'Standardization does not make unrelated constructs comparable.'),
    method('risk-ratio', 'Risk-ratio synthesis', 'statistical', 'effect association', 'study_id group_events group_totals', 'event_definition comparability zero_events dependence risk_of_bias', 'effect table|forest plot', 'cochrane10', '10.4', 'Check event definitions, follow-up and zero-event handling.'),
    method('odds-ratio', 'Odds-ratio synthesis', 'statistical', 'effect association', 'study_id group_events group_totals', 'event_definition comparability zero_events dependence risk_of_bias', 'effect table|forest plot', 'cochrane10', '10.4', 'Odds ratios must not be described as risk ratios.'),
    method('hazard-ratio', 'Hazard-ratio synthesis', 'statistical', 'effect association', 'study_id log_hazard_ratio standard_error', 'comparability proportional_hazards dependence risk_of_bias', 'effect table|forest plot', 'cochrane10', '10.9', 'Do not mix hazard ratios and risk ratios without justified methods.'),
    method('heterogeneity', 'Statistical heterogeneity assessment', 'diagnostic', 'effect association robustness', 'study_id effect_estimate standard_error effect_measure', 'comparability dependence model_choice', 'Q and I-squared table|tau-squared estimate', 'cochrane10', '10.10.2', 'Heterogeneity statistics do not replace substantive comparability judgments.'),
    method('subgroups', 'Subgroup comparison', 'statistical', 'effect association robustness', 'study_id effect_estimate standard_error subgroup', 'comparability dependence interaction_test prespecification sufficient_information', 'subgroup forest plot|interaction table', 'cochrane10', '10.11.3', 'Different within-group significance is not a test of subgroup differences.'),
    method('meta-regression', 'Meta-regression', 'statistical', 'association robustness effect', 'study_id effect_estimate standard_error moderators', 'comparability dependence sufficient_information prespecification confounding', 'moderator table|regression plot', 'cochrane10', '10.11.4', 'Study-level associations are not individual-level causal effects.'),
    method('sensitivity', 'Sensitivity scenarios', 'diagnostic', 'robustness effect association', 'study_id analysis_results scenario_definitions', 'prespecification defensible_scenarios dependence', 'scenario comparison table', 'cochrane10', '10.14', 'Record all planned scenarios, not only convenient results.'),
    method('funnel', 'Funnel plot', 'diagnostic', 'bias effect association', 'study_id effect_estimate standard_error effect_measure', 'comparability suitable_effect_measure small_study_context', 'funnel plot', 'cochrane13', '13.3.4.2', 'Asymmetry has several possible explanations.'),
    method('asymmetry-test', 'Method-appropriate funnel asymmetry test', 'diagnostic', 'bias effect association', 'study_id effect_estimate standard_error effect_measure', 'comparability at_least_ten_studies varied_precision suitable_test', 'test result table', 'cochrane13', '13.3.4.4', 'Ten studies is a rule of thumb, not sufficient justification; test choice matters.'),
    method('missing-evidence', 'Missing-evidence assessment', 'appraisal', 'bias', 'study_id protocols reported_outcomes', 'reviewer_judgment outcome_selection search_coverage', 'missing-results matrix', 'cochrane13', '13.3.1 and 13.4', 'Missing evidence cannot be ruled out solely by a non-significant test.'),
    method('certainty', 'GRADE outcome-level certainty profile', 'appraisal', 'bias effect', 'outcome evidence_summary appraisal', 'grade_applicable reviewer_judgment framework_training', 'summary of findings|certainty profile', 'cochrane14', '14.1 and 14.2', 'GRADE is not a universal score for every review type.'),
    method('qualitative-selection', 'Qualitative synthesis method selection', 'decision_support', 'experience explain', 'qualitative_findings context', 'epistemology purpose resources expertise data_richness', 'method comparison record', 'retreat', 'Abstract: RETREAT criteria', 'This selects a method; it does not perform qualitative synthesis.'),
    method('meta-aggregation', 'Qualitative meta-aggregation', 'synthesis', 'experience', 'study_id qualitative_findings supporting_illustrations', 'jbi_method_fit credibility reviewer_judgment', 'category table|synthesised findings', 'jbi', 'JBI approach', 'Human interpretation and methodological commitments remain necessary.'),
    method('publication-trends', 'Publication counts over time', 'bibliometric', 'literature', 'record_id publication_year', 'counting_unit corpus_scope date_completeness', 'annual count table|line chart', 'vosviewer', 'Sections 2 and 3.5.4; local descriptive extension', 'Corpus growth does not establish population prevalence or improved effectiveness.'),
    method('coauthorship', 'Co-authorship network', 'bibliometric', 'literature', 'record_id author_identifiers', 'author_disambiguation counting_rule corpus_scope', 'edge table|network plot', 'vosviewer', '3.5.4', 'A network edge denotes collaboration, not quality.'),
    method('keyword-network', 'Keyword co-occurrence network', 'bibliometric', 'literature', 'record_id keywords', 'term_normalization counting_rule corpus_scope', 'edge table|network plot', 'vosviewer', '3.5.4', 'Co-occurring words do not establish a validated conceptual theory.'),
    method('bibliographic-coupling', 'Bibliographic coupling', 'bibliometric', 'literature', 'record_id reference_identifiers', 'reference_coverage counting_rule corpus_scope', 'edge table|network plot', 'vosviewer', '3.5.4', 'Shared references are a relation, not a proof of shared findings.'),
    method('co-citation', 'Co-citation network', 'bibliometric', 'literature', 'record_id reference_identifiers', 'reference_coverage counting_rule corpus_scope', 'edge table|network plot', 'vosviewer', '3.5.4', 'Results depend on the citing corpus and reference coverage.'),
]
