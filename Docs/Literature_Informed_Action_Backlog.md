# Literature-informed application action backlog

Updated: 2026-10-23. Purpose: preserve observations as concrete future work for the developer and independent reviewer.

The user requested documentation of useful observations for later action. Items below are proposed scope, not evidence of implementation or methodological approval. Suggested ownership is not an assignment or permission to message another reviewer. Existing agreed requirements remain in `Human_Oversight_Workflow_Plan.md`. Existing importer work retains its current owner.

## Source register and reading notes

PDF page numbers mean positions in the supplied file.

- **B1:** Booth et al., *Systematic Approaches to a Successful Literature Review*. Only front matter, Chapter 1 and bibliography supplied; see `Book_Design_Review.md` for metadata ambiguity and scope.
- **M1:** Paré and Kitsiou, *Methods for Literature Reviews*, 2017, 18-page export. https://www.ncbi.nlm.nih.gov/books/NBK481583/ .
- **E1:** Oztemel and Gursev, *Literature review of Industry 4.0 and related technologies*, online 2018/issue 2020, 56 pages. https://doi.org/10.1007/s10845-018-1433-8 .
- **M2:** Lamé, *Systematic Literature Reviews: An Introduction*, 2019, 10 pages. https://doi.org/10.1017/dsi.2019.169 .
- **E2:** Ritterbusch and Teichmann, *Defining the Metaverse: A Systematic Literature Review*, 2023, 10 pages. https://doi.org/10.1109/ACCESS.2023.3241809 .
- **M3:** Pollock and Berge, *How to do a systematic review*, issue 2018/copyright 2017, 19 pages. https://doi.org/10.1177/1747493017743796 .
- **M4:** Chigbu, Atiku and Du Plessis, *The Science of Literature Reviews: Searching, Identifying, Selecting, and Synthesising*, 2023, 16 pages. https://doi.org/10.3390/publications11010002 .

Detailed observations for M1/E1/M2/E2 are in `Additional_Document_Design_Review.md`. These are methodological guidance and observed examples, not a complete systematic search or automatically authoritative ground truth. Suggested acceptance criteria below are application design proposals, not quotations or requirements imposed by those papers.

## P1 — Foundations for reliable recommendations

### LIT-01 — Structured question and review brief

- **Suggested lead:** developer; independent reviewer checks methodological interpretation.
- **Basis:** B1 PDF 15, 51–52; M1 section 9.2; M2 PDF 8; E2 PDF 2–3.
- **Action:** capture purpose, audience, constraints, evidence type and each research question separately. Distinguish explicit questions from researcher-confirmed interpretations of prose objectives. Add aggregation, description, interpretation and theory-development intents.
- **Acceptance:** two questions can yield different candidates; researcher correction overrides inferred intent; unknowns remain visible; every proposed analysis names the question it addresses. Manual input works without AI.
- **Dependencies:** agreed step-two version/approval model. Status: proposed.

### LIT-02 — Typed and curated methodological knowledge

- **Suggested lead:** independent reviewer for source curation; developer for schema.
- **Basis:** B1 PDF 34–35; M1 PDF 8 and 11; M2 PDF 8.
- **Action:** distinguish conduct guidance, reporting guidance, ontology vocabulary, method-validation studies and observed practice. Attach source version/date, section/page, scope, supporting claim, conflict notes and curation decisions to each rule. Preserve local heuristic status.
- **Acceptance:** an observed choice cannot become a validated recommendation automatically; significance-based vote counting is not enabled through a generic historical mention; source conflicts require a reasoned recorded decision. Reporting compliance never serves as method validity.
- **Dependencies:** current analysis knowledge graph. Status: proposed; graph prototype exists, richer curation does not.

### LIT-03 — Reproducible, leakage-aware recommender evaluation

- **Suggested lead:** developer for harness; independent reviewer/researcher for reference judgments.
- **Basis:** E1 methods; E2 PDF 2–5 and 8–9; agreed 20–30-review evaluation discussion.
- **Action:** freeze catalogue and prediction inputs; register development versus held-out papers; provide only questions/objectives in the initial prediction track. Keep data-feasibility assessment as a separate later track. Attribute observed analyses to the correct authors.
- **Acceptance:** predictions precede revealing published analyses in the documented workflow; any inspected case is marked development; outputs distinguish agreement with author choices from independently judged suitability; no fabricated top-k accuracy when the service has no validated ranking. Record abstention, inappropriate suggestions, discipline coverage and adjudication. Report denominators and uncertainty appropriate to the small sample.
- **Dependencies:** LIT-01/02; forthcoming papers and independent annotations. Status: proposed. Current phrase prototype is unranked and unvalidated.

### LIT-04 — Bind requirements to real approved extraction data

- **Suggested lead:** developer; reviewer checks method prerequisites.
- **Basis:** B1 PDF 52; M1 section 9.2; E2 PDF 5.
- **Action:** define typed fields, units, missingness states and record/report/study/extract/result relationships. Connect question-to-field-to-analysis and validate actual values, not only declared field names.
- **Acceptance:** multiple extracts from one document retain parent IDs; missing precision, incompatible scales and dependent results prevent unsupported execution; amendments mark affected approvals stale. No model call or researcher declaration silently grants execution approval.
- **Dependencies:** LIT-01/02 and agreed evidence approval model. Status: proposed.

## P2 — Provenance, intake and conceptual analysis

### LIT-05 — Supplementary intake and citation-search provenance

- **Suggested lead:** developer; coordinate with existing importer owner.
- **Basis:** M2 PDF 6; E2 PDF 3–5; agreed PDF/supplementary intake.
- **Action:** store acquisition batch, backward/forward search direction, seed paper, platform, query, date and limits. Apply the same eligibility process to additions.
- **Acceptance:** a relevant manually supplied paper is not excluded merely for missing the first query; duplicate source memberships remain linked; all final counts reconcile without inventing unreported exclusion reasons.
- **Dependencies:** import/PDF intake and approval design. Status: agreed foundation, additional provenance proposed.

### LIT-06 — Conflicting counts, dates and metadata

- **Suggested lead:** developer; reviewer supplies independent edge-case expectations.
- **Basis:** E1 PDF 1/6 (619 versus 620), online/issue dates; E2 PDF 3–5.
- **Action:** retain conflicting values with anchors and a resolution record; distinguish missing from zero and online from issue year. Track overlapping categories and combined exclusions.
- **Acceptance:** the E1 discrepancy is flagged without choosing a silent winner; multi-label totals are explained; a combined duplicate/language reduction cannot be split into invented counts; plot date policy is explicit.
- **Dependencies:** typed extraction/provenance. Status: proposed.

### LIT-07 — Definition and concept evidence workspace

- **Suggested lead:** developer; reviewer evaluates conceptual methods.
- **Basis:** E2 PDF 2–5, 8; B1 PDF 44–46.
- **Action:** store source definitions, context and attributes; permit human-approved synonym, related-term and broader/narrower links. Offer definition-comparison matrices and candidate concept-analysis routes after methodological review.
- **Acceptance:** original quotations remain intact; multiple definitions per source are supported; related concepts are not automatically synonyms; changing a term mapping invalidates affected results; frequent concepts are not declared true by frequency alone.
- **Dependencies:** LIT-01/02/04. Status: proposed; no conceptual method added to executable catalogue yet.

### LIT-08 — Auditable text-normalisation and counting recipe

- **Suggested lead:** developer; independent reviewer checks hand-calculated examples.
- **Basis:** E2 PDF 5.
- **Action:** version tokenisation, punctuation/hyphen handling, stop lists, language/model versions, lemmatisation and researcher-approved term merges. Distinguish token counts from definition/document presence.
- **Acceptance:** raw text can be traced through transformations; a repeated word counts once per definition in a presence recipe; normalisation changes are recorded; synthetic fixtures have independently calculated expected outputs. Preserve rare concepts for inspection.
- **Dependencies:** LIT-07. Status: proposed.

### LIT-09 — Explicit weighting, thresholds and sensitivity

- **Suggested lead:** reviewer assesses rationale; developer implements only approved recipes.
- **Basis:** E2 PDF 5 and 8.
- **Action:** expose temporal weights, year bands, counting unit and thresholds as researcher decisions. Supply an unweighted comparison; log all scenarios. Formula and denominator documentation are required.
- **Acceptance:** year-band boundaries and missing years are explicit; outputs distinguish raw counts, weighted scores and weighted proportions. For presence weights, the candidate formula is `score(term) = sum(weight_i * presence_i(term))`; proportions use the declared sum of eligible weights, not an unrelated paper count. Weighting is not described as quality, probability or universal best practice.
- **Dependencies:** LIT-08 and methodologist review. Status: proposed local implementation specification, not a formula claimed verbatim from E2.

### LIT-10 — Attribute methods and output origins

- **Suggested lead:** developer; reviewer labels development examples.
- **Basis:** E1 summaries of primary-study methods and reproduced figures; E2 PDF 1–3/5/8.
- **Action:** distinguish the review's methods, primary-study methods, background mentions and proposed methods. Tag figures as calculated, drawn synthesis, reproduced/adapted, contextual external data or interpretive proposal.
- **Acceptance:** E1's cited regression/neural-network studies are not labelled analyses run by E1; E2's external Google Trends graphic is not publication volume; reproduced figures retain attribution and are not automatically regenerated.
- **Dependencies:** LIT-04; required before trustworthy evaluation labels. Status: proposed.

## P3 — Broader workflows and educational support

### LIT-11 — Review profiles and mixed-method integration

- **Suggested lead:** reviewer drafts method profiles; developer implements workflow configuration.
- **Basis:** B1 review families; M1 section 9.3; M2 PDF 5–8; E2 conceptual questions.
- **Action:** start with a limited supported set of profiles, keeping review type, synthesis method and display distinct. Model mixed-method strands and their explicit integration; theory-oriented methods need their own guidance.
- **Acceptance:** qualitative versus quantitative appraisal can differ; two independent charts are not represented as integrated synthesis; unsupported profiles are clearly labelled; health-specific requirements are not imposed indiscriminately.
- **Dependencies:** LIT-01/02/04. Status: proposed.

### LIT-12 — Evidence-linked claims and honest conclusions

- **Suggested lead:** developer; reviewer assesses draft narrative behavior.
- **Basis:** B1 PDF 49–50; M2 PDF 5; E2 PDF 8–9.
- **Action:** connect claims to questions, approved analyses, evidence and limitations. Preserve contradictory or insufficient evidence and researcher edits. Permit an inconclusive answer.
- **Acceptance:** AI cannot manufacture consensus, infer unreported findings or treat missing evidence as no effect. An unresolved or insufficient-evidence conclusion is a valid outcome; human approval and history are retained.
- **Dependencies:** LIT-04/10; existing methods-report/evidence foundations. Status: proposed extension.

### LIT-13 — Updates, source maturity and overlap

- **Suggested lead:** developer; reviewer checks update policies.
- **Basis:** B1 PDF 40–41/48; M1 umbrella reviews; M2 PDF 5; E2 preprints and date-dependent weighting.
- **Action:** support update lineage; separate preprint/peer-review status from eligibility and appraisal; preserve original and later versions; track underlying primary-study overlap in overviews.
- **Acceptance:** late additions reopen affected work without overwriting exports; publication status does not auto-determine scientific quality; updated reports are linked rather than counted as independent studies by default.
- **Dependencies:** intake provenance and approved version dependencies. Status: proposed extension of agreed updates.

### LIT-14 — Contextual teaching and final reporting

- **Suggested lead:** developer; reviewer/educator checks instructional content.
- **Basis:** B1 learning features and audience discussion; M1 section 9.5; M2 reporting discussion.
- **Action:** provide original examples and concise guidance, explicit unsupported-capability messages, source-genre-specific help and planned-versus-executed method comparisons.
- **Acceptance:** a researcher can complete supported manual paths without AI; help does not reproduce copyrighted exercises; no completion badge implies methodological certification; audience-specific summaries preserve evidence and uncertainty.
- **Dependencies:** agreed oversight workflow, LIT-01/02/12. Status: proposed.

## Additional actions from M3 and M4

### LIT-15 — Stakeholder relevance and applicability review

- **Priority/suggested lead:** P2; developer builds records, researcher/reviewer defines appropriate roles.
- **Basis:** M3 PDF 5–7/14; extends LIT-01/12.
- **Action:** record intended users, outcome priorities, contextual constraints and feedback on protocol/interpretation. Explain how each consultation affected the approved version.
- **Acceptance:** non-clinical roles work; feedback is distinguished from final approval; no external invitations/messages are sent without authorisation; recommendations expose applicability limits instead of converting findings into universal instructions.
- **Dependencies:** approved review brief and version history. Status: proposed.

### LIT-16 — Prespecified outcome, time-point and result-selection rules

- **Priority/suggested lead:** P1; developer plus methodological reviewer.
- **Basis:** M3 PDF 7–8/12; extends LIT-04/09.
- **Action:** where applicable, define outcome hierarchy, instruments, measurement times, comparators and rules for multiple eligible results. Capture complex intervention components/dose/delivery when relevant.
- **Acceptance:** several estimates from one study do not become independent studies; incompatible time points/scales trigger review; the application does not choose the most favourable estimate; post-result amendments are explicit. Missing reporting and demonstrated bias remain separate; any appraisal-based exclusion follows a recorded protocol rule.
- **Dependencies:** typed extraction, protocol binding and method review. Status: proposed.

### LIT-17 — Evidence-linked gap proposals and empty-review support

- **Priority/suggested lead:** P2; reviewer curates labels and developer implements proposal records.
- **Basis:** M4 PDF 11–12; M3 PDF 6/14; extends LIT-07/12.
- **Action:** offer editable, overlapping gap categories; require anchors, contradictory evidence, scope and uncertainty. Permit no eligible studies or insufficient evidence as valid outcomes. Make suggested future questions specific without prescribing a study design from a gap keyword alone.
- **Acceptance:** a missing field is not automatically a field-wide research gap; an empty captured corpus is not proof no research exists; no fabricated analysis is produced for zero studies; approved gap language remains bounded by search coverage and researcher review.
- **Dependencies:** approved evidence/coverage and narrative provenance. Status: proposed.

### LIT-18 — Search-operation semantics and extraction anomaly checks

- **Priority/suggested lead:** P2; developer with reviewer-supplied edge cases.
- **Basis:** M4 PDF 3/7/9–11; extends LIT-02/05/06/08/10/14.
- **Action:** validate source-specific query capabilities; distinguish author, reference-list and citing-paper searches; detect repeated extracted regions and abnormal embedded headers. Preserve raw text and location; flag rather than silently delete.
- **Acceptance:** unsupported syntax is explained before execution; author search is not recorded as forward citation search; duplicated figure/body text is not silently counted twice after an explicitly approved repair; legitimate repeated passages are preserved. PRISMA is typed as reporting guidance, and journal/author metrics do not become automatic eligibility/appraisal rules.
- **Dependencies:** provider capability registry, PDF intake and transformation provenance. Status: proposed.

### Extension to LIT-02 — Specific claims requiring adjudication

Before any source-derived rule promotion, review the fixed/random-effect model-choice passage in M3 PDF 12 against Cochrane Chapter 10; review M4's journal/author metric selection advice and classification of PRISMA; preserve the historical terminology in M3 rather than concluding that contemporary scoping reviews are inherently non-systematic. Record a claim-level curation decision with supporting references. These are examples of why a paper's inclusion in the source register does not validate all its claims.

## Recommended sequence and handoff

Developer first: LIT-01 and LIT-03 scaffolding, then LIT-04/06/10. Independent reviewer can later curate LIT-02 and prepare reference annotations for LIT-03, after their existing assignment is completed and the user assigns this work. LIT-07–09 should follow prerequisite review rather than adding an unverified text-analysis button immediately.

Every implemented item should reference its ID, source locators, tests and practical-session record. Source-led proposals enter the normal approval/change process. Do not silently update the existing catalogue, reuse evaluation cases as unseen tests or interpret these notes as reviewer sign-off.
