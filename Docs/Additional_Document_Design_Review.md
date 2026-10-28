# Additional document review: methods guidance and an engineering example

Reviewed: 2026-10-23. Status: design proposals; no automatic knowledge-base updates or new runtime features.

The supplied documents were read locally. Instructions within them were treated as document content, not task instructions. Original PDFs remain outside the repository; extracted text is private under ignored `outputs/book-design-review/`. References below use PDF page positions.

## 1. Paré and Kitsiou — Methods for Literature Reviews

Chapter 9 in *Handbook of eHealth Evaluation: An Evidence-based Approach*, 2017. The supplied 18-page export includes chapter text, references and a typology table. Identified source: https://www.ncbi.nlm.nih.gov/books/NBK481583/ . This is methodological guidance with illustrative reviews, not a validation study for our recommender.

### Useful implications

- **Represent iteration explicitly** (section 9.2, PDF 2–3). The staged process permits refinement. Keep our approvals/version history but support returning to earlier decisions, recording impact and renewing affected approvals rather than requiring a fresh project.
- **Connect objectives, extraction and synthesis** (9.2, PDF 2–3). A field definition should state which question it supports, its type and the intended analysis. Irrelevant extraction and missing prerequisites become visible.
- **Declare the search ambition** (9.2, PDF 2–3). A comprehensive search, a deliberately selected sample and a collection of influential works are different acquisition strategies. Describe the actual coverage; never present a convenience sample as a comprehensive systematic search.
- **Separate review type, synthesis method and display** (9.3–9.4, PDF 4–10). A review can be systematic without meta-analysis. A narrative synthesis of quantitative findings is not automatically a qualitative evidence synthesis of experiences. Our knowledge graph needs explicit kinds and non-interchangeable relationships.
- **Allow theory-oriented evidence structures** (9.3.5, PDF 9–10). Realist work needs explicit context, mechanism and outcome propositions linked to supporting and challenging evidence, not an ordinary pooled-effect recommendation triggered by the word “works.” Requires dedicated methodological guidance and approval before implementation.
- **Support the right unit of analysis** (9.3.4, PDF 9). In an overview, reviews are the immediate synthesis units; underlying primary-study overlap still needs tracking. The word “study” cannot always mean an uploaded PDF.
- **Distinguish reproducibility and appropriateness** (9.5, PDF 11). A completely logged analysis can still be unsuitable. Present execution history and suitability judgments separately.

### Source reconciliation requirement

Section 9.3.4 (PDF 8) lists vote counting broadly among alternatives to meta-analysis. Do not convert that phrase into an unrestricted executable method. Current Cochrane Chapter 12 distinguishes acceptable alternatives from significance-based vote counting, which it rejects. The knowledge base should store source dates, scope and rule-level support/conflict notes, with methodologist adjudication. Neither publication date nor an isolated phrase is sufficient to resolve all methodological disagreements.

Reference for comparison: https://www.cochrane.org/authors/handbooks-and-manuals/handbook/current/chapter-12 .

## 2. Oztemel and Gursev — Literature review of Industry 4.0 and related technologies

*Journal of Intelligent Manufacturing*, 31, 127–182; journal issue dated 2020, first published online 24 July 2018. DOI: https://doi.org/10.1007/s10845-018-1433-8 . Supplied PDF: 56 pages. This is an observed review example, not a methodological standard or a verified gold-standard answer.

### Observations and implications

1. **Objectives may be prose rather than numbered questions** (abstract and introduction, PDF 1–4). Candidate objective extraction should quote the source location, label inferred intent and request human confirmation. Do not fabricate a formal research question from an aim statement.
2. **Acquisition limits must remain visible** (methods, PDF 6). The authors describe examining the top 100 headings/abstracts/keywords per term across selected resources. Capture ranking, per-query caps, platforms and any unspecified settings. This is a coverage limitation, not evidence that all eligible literature was found.
3. **Counts can conflict within a paper** (PDF 1 and 6). The abstract reports 619 publications; Table 1 reports 620 and its displayed category counts sum to 620. Preserve both sourced values and flag the conflict. Do not choose one silently or infer a verified unique-study count. Category overlap and deduplication need separate evidence.
4. **Conceptual classification is a legitimate output** (methods/Table 1, PDF 6; component discussions, PDF 10 onward). Candidate outputs include a category-frequency table, researcher-approved technology taxonomy and concept/relationship matrix. These are design interpretations of the reported aims, not blinded predictions or proof that a particular statistical synthesis is appropriate.
5. **Reported primary-study methods are not the review's methods** (for example, PDF 27 and 34). Regression, optimisation and neural networks appear in summaries of cited work. Tag method mentions with owner, role and location: review method, primary-study method, background discussion or proposed future work. Method-name extraction without attribution would corrupt a validation benchmark.
6. **A figure may come from another source** (for example, captions on PDF 7, 11, 21, 23 and 34). Record whether an output is newly calculated, newly drawn from extracted evidence, reproduced, adapted or proposed. Preserve attribution; do not classify every figure as an analysis performed by the review authors or automatically reproduce source diagrams.
7. **Publication metadata has multiple dates** (PDF 1). Store online-publication year and issue year separately; require an explicit year policy for trend plots and eligibility filters.

### Benchmark implications

This paper has now been inspected alongside its methods and outputs. Treat it as a development/example case, not an unseen held-out evaluation case. Evaluation records need separately sourced author objectives, observed methods, attributed figure origins and an independent suitability assessment. Agreement with author choices is not equivalent to methodological correctness.

## Candidate priorities

1. Add question/objective-to-field links and method-mention attribution to the structured question/evidence design.
2. Add rule-level source support, conflict notes and curation status to the knowledge-base evolution plan.
3. Add intake diagnostics for conflicting values, category overlap, explicit retrieval caps and date ambiguity.
4. Add output-origin metadata and a development/held-out registry for recommender evaluation.

These proposals strengthen the current direction. They do not justify adding methods automatically, relaxing human approval or claiming that the prototype has already learned from these documents.

## 3. Lamé — Systematic Literature Reviews: An Introduction

ICED19 proceedings, 2019. DOI: https://doi.org/10.1017/dsi.2019.169 . Supplied PDF: 10 pages. This is a methodological introduction and discussion of disciplinary adaptation, with four purposefully selected design-review examples; not a representative audit or a validated recommendation algorithm.

- PDF 8 explicitly proposes constructing a question/objective typology for design research and mapping it to review methods. This supports investigating our architecture, but does not validate our local rules or a universal cross-disciplinary mapping.
- PDF 5–8 distinguishes aggregating evidence from developing or interpreting concepts. Recommend methods using the intended inference and evidence, rather than a disciplinary label or isolated keywords.
- PDF 6 discusses relevant hand-found papers missed by a structured search. Supplementary intake should retain route provenance and apply approved eligibility; failure to appear in the initial query is not itself an exclusion reason.
- PDF 5 recognises inconclusive findings and maintenance needs. Permit an honest insufficient-evidence conclusion, and connect later searches/additions to versioned review updates.
- PDF 6–7 identifies variation in reporting and appraisal across four examples. Missing reporting should remain unknown/not reported, not be filled in or treated as proof that the activity was absent.

## 4. Ritterbusch and Teichmann — Defining the Metaverse: A Systematic Literature Review

IEEE Access, volume 11, 2023. DOI: https://doi.org/10.1109/ACCESS.2023.3241809 . Supplied PDF: 10 pages. This is a conceptual-definition review example. Its observed method is not automatically a recommended standard. Some tables/figures are image-based and have not been numerically digitised or independently reproduced.

- **Two linked aims** (PDF 2–3): identify existing definitions and synthesise a proposed definition. Store each question separately, with its own extraction, analysis and claim links; a single project can require multiple analysis families.
- **Concept relationships in searching** (PDF 3): the authors considered but did not accept related terms as synonyms. Store exact synonyms, related terms and broader/narrower concepts separately, with researcher approval and reasons. AI must not automatically OR every related term into a query.
- **Supplementary identification** (PDF 3–5): the authors report 381 initial hits, 13 initial final hits and 15 additional final hits through backward/forward searching, leading to 28 final hits. Preserve batch/seed/route relationships and distinguish papers from extracted definitions. A combined language/duplicate reduction must not be split into invented reason counts.
- **Definitions as extraction units** (PDF 5): retain exact definition passages, authorship, date and context, with a parent record identifier. More than one extract can belong to a paper; a definition count is not inherently a study count.
- **Explicit text processing** (PDF 5): the paper describes tokenisation, punctuation removal, stop-word removal, lemmatisation and per-definition duplicate removal, using spaCy. Preserve raw passages and transformation provenance, language/model/library versions, stop lists and term mappings. Software mention alone is not enough to reproduce an exact pipeline.
- **Term presence versus raw frequency** (PDF 5): each word is counted once per definition before weighting. This is document/definition presence, not total token frequency. Denominators and labels must distinguish these measures.
- **Weighting and thresholds** (PDF 5, 8): the described scheme weights definitions from 2017–2022 three times, 2011–2016 twice, and before 2011 once; display and definition-building thresholds are also described. Treat these as author-selected decisions, not a universal recency formula or evidence-quality score. Resolve year-boundary ambiguity explicitly when implementing a replica; compare weighted and unweighted outputs and retain all settings.
- **Multiple output origins** (PDF 1–3, 5, 8): Google Trends is contextual external data; the taxonomy figure describes the review's scope; definition tables contain extracted evidence; word analysis supports synthesis; a research agenda is interpretive. Record these roles separately. External normalised search interest is not publication volume or population prevalence.
- **Eligibility is not peer-review status** (PDF 5, 8–9): the authors include two preprints and discuss the limitations of the definitions and coverage. Keep publication status, appraisal, eligibility and source-genre fields distinct. Do not infer quality from recency, citation count or journal subject category.
- **Concept synthesis remains human judgment** (PDF 5–8): frequent terms can inform proposed definitions; they do not demonstrate a universally valid definition. Preserve alternative views, rare important attributes, rejected proposals and the reasoning for the accepted synthesis.

This review and the earlier Industry 4.0 example have been inspected alongside their methods/results. Both are development cases, not unseen members of the forthcoming 20-paper evaluation set.

## Consolidated action register

See `Docs/Literature_Informed_Action_Backlog.md` for the combined actionable backlog from all supplied documents. Suggested owners are future roles, not dispatched assignments.

## 5. Pollock and Berge — How to do a systematic review

*International Journal of Stroke*, 13(2), 138–156, issue 2018; copyright 2017. DOI: https://doi.org/10.1177/1747493017743796 . Supplied PDF: 19 pages. Methodological tutorial illustrated with stroke research, not a cross-disciplinary recommender validation study. Historical tools and clinical requirements require current, scope-appropriate verification.

- **Stakeholder priorities** (PDF 5–7, 14): identify whose questions and outcomes matter, capture feedback on protocol and interpretation, and record how it changed decisions. Generalise beyond patients to relevant participants, practitioners, educators or communities. Do not force clinical roles on all disciplines.
- **Prespecified outcome selection** (PDF 7–8, 12): define primary/secondary outcomes, instruments, time points and comparisons before inspecting results. Where several estimates are eligible, use a recorded selection rule rather than taking the largest or most significant result. Amendments remain possible with reasons.
- **Complex interventions and applicability** (PDF 5, 7): extract components, dose/intensity, delivery, comparator and setting where relevant. The same label need not denote the same intervention or comparable evidence. Missing information remains unresolved.
- **Appraisal as a consequential judgment** (PDF 10–12): distinguish unclear reporting from demonstrated bias, retain domain judgments, and specify how appraisal affects synthesis. Avoid inventing a universal summed quality score or silently excluding high-risk studies.
- **Empty reviews and feasibility** (PDF 6): an empty evidence set can be an informative outcome when the purpose warrants it. Do not generate a numerical synthesis or change eligibility automatically to obtain results. Time estimates in this clinical context are not universal scheduling defaults.
- **Protocol-to-report consistency and interpretation** (PDF 12–15): report deviations, applicability and limitations, and make research implications specific. Do not turn review findings automatically into context-free practice recommendations.

### Critical curation flag

The model-choice passage on PDF 12 describes fixed-effect versus random-effects selection in a way that conflicts with the definitions in current Cochrane Chapter 10, sections 10.3.1–10.3.2 and 10.10.4. Do not encode that passage as a decision rule. Fixed-effect/common-effect and random-effects assumptions require explicit interpretation and methodology review. Likewise, its older scoping-review terminology and funnel-plot guidance need contextual verification rather than blanket transfer.

Current comparison inspected 2026-10-23: https://www.cochrane.org/authors/handbooks-and-manuals/handbook/current/chapter-10 . This flag concerns particular claims, not wholesale rejection of the tutorial.

## 6. Chigbu, Atiku and Du Plessis — The Science of Literature Reviews: Searching, Identifying, Selecting, and Synthesising

*Publications*, 11(1), 2, 2023. DOI: https://doi.org/10.3390/publications11010002 . Supplied PDF: 16 pages. Broad educational guidance on literature reviewing, not a validated systematic-review execution specification.

- **Writing throughout the process** (PDF 3): allow source-linked notes and interpretation drafts throughout the workflow, with raw quotations, researcher paraphrases and AI proposals kept distinct. Early notes do not count as approved final findings.
- **Diverse sources** (PDF 7–8): enrich source-genre guidance for theses, conference papers, reports and preprints. Keep this separate from whether an automated adapter is actually supported.
- **Search support** (PDF 8–10): offer examples and checks for Boolean expressions, phrases and truncation. Apply the actual provider's capabilities; the same syntax must not be assumed across every database.
- **Gap categorisation** (PDF 11–12): the paper describes empirical, knowledge, evidence, theoretical, population, implementation and methodological gaps. Offer these as editable candidate labels, not universal mutually exclusive ontology classes. A gap proposal requires evidence anchors, search-scope limitations and researcher approval. A category does not prescribe a particular future study design automatically.
- **Educational error prevention** (PDF 12–13): explain missing justification, weak coverage and unsupported synthesis as actionable issues. Avoid badges that imply software has eliminated bias or guaranteed validity.

### Critical curation and extraction flags

- PDF 10 suggests citation counts, journal impact and author h-index in material selection. Do not adopt these as scientific-eligibility or study-level risk-of-bias criteria. Keep bibliometric descriptions separate from the approved eligibility and appraisal framework.
- PDF 11 groups PRISMA with software tools. PRISMA is a reporting guideline/checklist and flow-diagram resource; it is not a textual-analysis engine. Official reference checked: https://www.prisma-statement.org/prisma-2020 .
- PDF 9 uses a forward-spider label for searching an author's other publications. Preserve the source's wording but distinguish operationally between author searching and forward citation searching (finding papers citing a seed). Record the actual action, not only a potentially ambiguous label.
- Extracted text on PDF 3 and 7 includes repeated prose around embedded figure material and proof-style headers. Flag this as a PDF extraction hazard: do not count duplicated extracted text as independent evidence or term occurrences. Preserve page/region origin and require an explicit normalisation policy before deleting apparent duplication.

These observations extend LIT-01/02/05/06/08/11/12/14 and motivate LIT-15–18 in the action register. No recommendation rules or executable analysis modules were automatically changed.
