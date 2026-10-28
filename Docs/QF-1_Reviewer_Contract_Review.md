# QF-1 reviewer design validation: question-framework contract

**Reviewer:** independent reviewer.
**Date:** 2026-10-25.
**Scope:** design only.
**Inputs:** `Docs/Question_and_Search_Framework_Design.md` and the provisional manual foundation (`src/slr/question_frameworks.py`, the `frameworks` action in `src/slr/questions.py`, `src/slr/web/question_frameworks.js`). These were taken from the developer snapshot at baseline `9a19310`.

**Executable acceptance cases:** `tests/test_qf1_acceptance.py`.
- Seven cases pass against the current foundation.
- Eight proposed contract items are strict xfails. I confirmed with `--runxfail` that each one fails for its intended reason, not by accident. When an item is implemented, its test becomes an unexpected pass, and the marker should then be removed.

**Out of scope:** no shared UI or developer files were edited, and no models were called. I reviewed the reasoning and provenance model, not a quality score, and I propose none.

## 1. Verdict

The foundation's stance is right:
- Frameworks are reasoning guides, not grades.
- Approval is explicit and bound to the exact version.
- Wording changes clear the current maps, and history is preserved.
- AI wording and manual wording get the same record.
- No score is stored.

I recommend **accepting it as the QF-2 base, with the contract changes below**. The two most important are C1 and C3:
- **C1:** there must be one framework vocabulary. The protocol and the questions currently disagree.
- **C3:** components must be traceable to the question by quote, so that an invented component is detectable without any semantic judgement.

## 2. Source verification

Each source was checked on 2026-10-25 against the publisher page or Europe PMC; PubMed blocks automated reads.

| Catalog claim | Source as verified | Finding |
|---|---|---|
| PICO; search blocks need not include every component | Cochrane Handbook ch. 4 "Searching for and selecting studies", **v6.5.1 (March 2025)**, §4.4.2: searching on every aspect is "usually unnecessary… and may even be undesirable"; comparators and outcomes are often poorly indexed. | Correct. **Pin v6.5.1** in place of "Living guidance". **Add to limits:** §4.4.2 (MECIR 4.4.b) says PICO is "generally not suitable" for diagnostic test accuracy, prognosis, qualitative or methods questions. |
| PCC for scoping reviews; not every element is needed | JBI Manual, ch. 10 (Scoping reviews), §10.2.3. | Correct. The same page also allows **PICO/PECO** for some scoping purposes. The catalog's "not a universal requirement" wording fits. |
| Search-strategy structures | JBI Manual §2.4.3 "Developing a Search Strategy" lists **PICO, PCC, PICo, CoCoPop, PIRD**. | Supports a broader catalog (C6). This is the citation for PICo, CoCoPop and PIRD. |
| SPIDER for qualitative questions; needs wider testing | Cooke A, Smith D, Booth A. Qual Health Res 2012;22(10):1435-43, doi:10.1177/1049732312452938. The abstract says it "needs to be refined and tested on a wider range of topics". | Correct. **Add** Methley et al., BMC Health Serv Res 2014, doi:10.1186/s12913-014-0579-0: SPIDER had the highest specificity but the lowest sensitivity, and the authors advise against it for comprehensive searches. This matters for QF-3: SPIDER components must never become mandatory search blocks. |
| PRESS reviews searches; it does not generate them | McGowan J et al. J Clin Epidemiol 2016;75:40-6, doi:10.1016/j.jclinepi.2016.01.021. Six elements: translation of the research question; Boolean and proximity operators; subject headings; text word search; spelling, syntax and line numbers; limits and filters. | Correct. Cite it as the "2015 Guideline Statement (published 2016)". |
| (proposed) CIMO for management and organisation design questions | Denyer D, Tranfield D, van Aken JE. Organization Studies 2008;29(3):393-413, doi:10.1177/0170840607088020 (Crossref). | Verified. This is a non-health structure. |
| (proposed) PICOC for software engineering | Kitchenham B, Charters S. Guidelines for performing SLRs in software engineering, EBSE Technical Report EBSE-2007-01 (2007). | **Not fetched; recalled by the reviewer.** Confirm the edition before embedding it. It suits this platform's computing and education users. |

These are structures and citations, not copied instruments, so licensing is not a concern for names, component labels and short paraphrases. Do not embed checklist text verbatim.

## 3. Contract changes

**C1 · One framework vocabulary (High).**
- `protocol.FRAMEWORKS = ('PICO','PECO','PCC','SPIDER','other')` and `objectives.framework/elements` form a second, unsynchronised framework statement beside the question maps.
- A protocol saved as PICO is accepted while the approved question map says PCC. This is the same class of defect as WA-01: an approved artefact contradicts what was approved.
- Proposal:
  - Derive `objectives.framework` and `objectives.elements` from the approved maps on protocol save, as WA-01 now does for `objectives.question`.
  - Alternatively, reject a contradiction.
  - Use one catalog module for both.
- Case: `test_protocol_framework_cannot_contradict_the_approved_question_maps`.

**C2 · Versioned, hashable catalog entries (Medium).**
- `catalog_version` is a single string, so guidance text can change without a version bump.
- Proposal: each entry gets `id`, `version` and `sources[{citation, url, doi?, version_consulted, consulted_date}]`. Each map records `guidance_sha256` (a canonical digest of the entry). A catalog change then never silently re-labels old maps.
- Case: `test_map_records_a_hash_of_the_guidance_it_used`.

**C3 · Quote anchors for "identified" (High for AI use).**
- Today a component is free text, so "identified: smallholder women farmers" is accepted for a question that never mentions them. That is the design's case "AI invents an absent component".
- Proposal: `identified` requires `quote`, an exact substring of the hashed question (offsets optional). `unclear` may quote. A deterministic check rejects or flags quotes that are not in the question.
- This is a traceability check only, consistent with the design's "presence/traceability, not semantic suitability".
- Case: `test_identified_component_must_quote_the_question`.

**C4 · Status vocabulary (Medium).**
- The current statuses are `unreviewed`, `identified`, `unclear` and `not_applicable`.
- The design distinguishes *missing* (should be stated but isn't) from *justified absent*. Today that falls into `unclear` or `not_applicable`.
- Proposal: add `missing`. It must carry an explanation and appears as an unresolved issue at approval. Approval is not blocked, because judgement stays human.
- Case: `test_missing_status_is_distinct_from_unclear_and_not_applicable`.

**C5 · Custom structures with named components (Medium).**
- `custom` has a single `researcher_defined` text, so CIMO, PICOC, ECLIPSE or a discipline-specific structure must be crammed into one note.
- Proposal: custom takes 1–8 researcher-named components (`label`, with optional `source`) and requires a rationale. "No structure fits" remains a valid custom choice with zero components plus a rationale.
- Case: `test_custom_structure_names_its_own_components`.

**C6 · Catalog breadth (Medium; content decision).**
- Add, with the sources above:
  - **PICo** (JBI qualitative);
  - **PECO** (exposure questions; already permitted in the protocol);
  - **CoCoPop** and **PIRD** (JBI §2.4.3);
  - **CIMO** (management and organisation);
  - **PICOC** (software engineering, after edition check).
- Each entry gets a `purpose`, `not_suitable_for` and `search_note`. The `search_note` covers, for example, SPIDER's sensitivity risk and PICO's comparator/outcome caution.
- Keep the catalog advisory. Never auto-select from it.
- Cases: `test_catalog_covers_non_health_and_jbi_listed_structures` and `test_catalog_limits_reflect_verified_sources`.

**C7 · Explicit per-question state in exports (Medium).**
- Exports should distinguish `unmapped`, `selected-not-reasoned` (every component `unreviewed`), `reasoned`, and `reasoned-with-unresolved` (any `missing` or `unclear`).
- Do not use the word "assessed" for anything short of `reasoned`.
- Legacy approvals export as `unmapped`, never inferred.
- Case: `test_each_question_reports_an_explicit_assessment_state`.

**C8 · Minor points.**
- (a) Replacing one question drops the maps for every question. That is acceptable and conservative, but say so in the notice ("all mappings were cleared because the question set changed").
- (b) `origin` is always `researcher`. Reserve `ai-suggested` with a linked decision event for QF-3, using the same validation path.
- (c) Index-based keys break on reordering. Keying by `question_sha256` plus index is safer.

## 4. Proposed component contract (v2 sketch)

```json
{"catalog": {"id": "PCC", "version": "1", "label": "PCC", "purpose": "...", "not_suitable_for": "...", "search_note": "...",
             "components": [{"id": "population", "label": "Population"}, {"id": "concept", "label": "Concept"}, {"id": "context", "label": "Context"}],
             "sources": [{"citation": "JBI Manual for Evidence Synthesis, 10.2.3", "url": "...", "version_consulted": "...", "consulted_date": "2026-10-25"}]},
 "map":     {"question_index": 0, "question_sha256": "...", "framework": "PCC", "guidance_sha256": "...", "origin": "researcher",
             "rationale": "...", "state": "reasoned-with-unresolved",
             "components": {"population": {"status": "identified", "text": "...", "quote": "community seed banks"},
                            "context": {"status": "missing", "text": "Region named, setting type not stated"}}}}
```

Status rules:
- `identified` requires `quote` (an exact substring) and `text`.
- `unclear`, `missing` and `not_applicable` require `text`.
- `unreviewed` requires nothing.
- `state` is derived on the server, never supplied by the client.

## 5. Cross-discipline acceptance cases

The table maps each case in the design's minimum list (§"Minimum cases") to a test.

| # | Case | Status | Test |
|---|---|---|---|
| 1 | Manual and AI wording treated equally | passes | `test_ai_accepted_wording_uses_the_same_reasoning_record` |
| 2 | Multiple questions, mixed frameworks (education intervention / nursing qualitative / agricultural scoping / municipal policy) | passes | `test_mixed_purpose_review_maps_each_question_separately` |
| 3 | No listed framework fits | passes (custom) · C5 proposed | as above · `test_custom_structure_names_its_own_components` |
| 4 | AI invents an absent component | **gap** | `test_identified_component_must_quote_the_question` |
| 5 | Justified absence vs unexamined blank | passes | `test_not_applicable_needs_a_reason_and_differs_from_unreviewed` |
| 6 | Question edit stales the reasoning | passes | `test_question_edit_clears_current_maps_but_keeps_history` |
| 7 | Old review honestly unassessed | passes now · explicit state proposed (C7) | `test_legacy_draft_is_not_reported_as_assessed` |
| 8 | Manual use with AI off | passes | `test_manual_mapping_works_with_ai_off` |
| 9 | No score or validity claim | passes | `test_no_score_or_validation_claims_in_stored_maps` |
| 10 | Protocol and question framework agree | **gap** (C1) | `test_protocol_framework_cannot_contradict_the_approved_question_maps` |

**QF-3 term-mapping cases.** No API exists yet, so these are specified here rather than coded:
- **Unmapped user term:** a term attached to no component is flagged, not dropped.
- **Deliberately excluded concept:** for example, an outcome block omitted for sensitivity. It needs `included: false` plus a reason, and is not reported as "uncovered".
- **Unverified vocabulary claim:** an AI-suggested "MeSH: X" without lookup evidence is stored as `unverified` and shown that way.
- **Question edit:** stales the concept and term records and the dependent search-section approval.
- **SPIDER-derived blocks:** carry the Methley sensitivity warning.
