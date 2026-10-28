# Question and search-concept framework design

Design proposal recorded 2026-10-25. This document distinguishes implemented behavior from proposed work. It does not claim the application currently validates research questions or search terms against the frameworks below.

## Current implementation audit

- `questions.py` accepts topic/questions, records optional AI proposals and explicit human decisions, and binds final approval to a saved draft. It validates response structure and history, not scientific suitability against a named question framework.
- `protocol.py` permits `objectives.framework` (PICO, PECO, PCC, SPIDER or other) and `objectives.elements`, with structural checks and reporting fields. This is storage/checklist support, not a framework assessment engine. The guided question editor does not currently expose structured framework mapping.
- Protocol keywords and source-specific queries are saved and approved. Structural syntax/provider checks do not establish adequate synonyms, valid controlled vocabulary or question-to-term coverage.
- Neither researcher-written nor AI-generated questions/keywords receive a consistent, source-backed framework assessment today. Existing approvals must not be retrospectively described as having received one.

## Source-backed foundations and limits

1. **PICO / intervention questions.** Cochrane discusses deriving search concepts from review objectives and eligibility. It also warns that PICO does not suit every question and that including comparator/outcome terms can lose relevant records. Use appropriate concepts, not every component as a mandatory search block. [Cochrane Handbook, chapter 4](https://www.cochrane.org/authors/handbooks-and-manuals/handbook/current/chapter-04).
2. **PCC / scoping questions.** JBI recommends population, concept and context while recognizing that some questions need a different format or may not require every component. A framework choice must be justified, not imposed across disciplines. [JBI, defining and aligning objectives/questions](https://jbi-global.atlassian.net/wiki/spaces/MANUAL/pages/355862687/10.2.3%2BDefining%2Band%2Baligning%2Bthe%2Bobjective%2Bs%2Band%2Bquestion%2Bs).
3. **SPIDER / qualitative or mixed-method questions.** Sample, phenomenon of interest, design, evaluation and research type provide an alternative structure. The original paper describes limitations and a need for wider testing; this is not a universal quality test. [Cooke, Smith and Booth, 2012](https://pubmed.ncbi.nlm.nih.gov/22829486/).
4. **Search development differs from question formulation.** JBI describes several question structures according to review purpose. [JBI, developing a search strategy](https://jbi-global.atlassian.net/wiki/spaces/MANUAL/pages/652279828/2.4.3%2BDeveloping%2Ba%2BSearch%2BStrategy).
5. **PRESS reviews the search strategy.** It is a peer-review method, not a keyword generator or an automated certification. Its domains inform checks for question translation, Boolean/proximity operators, headings, text words, syntax and limits. [PRESS 2015 guideline](https://pubmed.ncbi.nlm.nih.gov/27005575/).

These are methodological frameworks/guidelines, not a single theory that proves a question is scientifically valid. PRISMA reporting checklists must not be presented as question-validation tools.

## Proposed researcher journey

### A. Select and justify the structure

Offer a review-purpose choice and explain suitable framework options with their sources. Allow the researcher to change the recommendation, select a documented custom structure, or record why no listed framework fits. Multiple questions may need different structures; do not assign one framework automatically to an entire mixed-purpose review.

### B. Map each question, regardless of author

Show the exact question and its components side by side. Record component text/anchors, missing or unclear elements, and researcher-confirmed applicability. A justified absent component is not the same as an unexamined blank. Manual mapping works without any model. AI can suggest mappings/refinements but cannot approve a framework or invent component facts. Use the same review procedure for AI and human wording.

The UI should say: “Assessed using PCC: population identified, concept identified, context needs clarification,” with the method/version/source. Never show “scientifically validated,” “novel,” or a fabricated numerical quality score. Deterministic checks establish presence/traceability only; semantic suitability remains a human judgment.

### C. Approve questions and their assessment record

Bind the approved question version, selected framework/version, component map, unresolved issues and the researcher's rationale. Preserve the original question, AI proposals, edits and human decisions separately. Do not silently rewrite old approvals; existing reviews have assessment status unavailable until explicitly assessed.

### D. Develop traceable search concepts and terms

Start from the approved question components. For each candidate search concept, record:

- Question/component IDs and exact approved-version hash.
- Synonyms, spelling variants, acronyms and phrases, with their manual/AI/vocabulary provenance.
- Whether the concept is included as a search block; reasons for omissions that preserve sensitivity.
- Controlled-vocabulary authority, lookup evidence/date and verified versus unverified status. An LLM suggestion alone does not prove a MeSH or thesaurus term exists. Use vocabularies appropriate to the discipline/database.
- Human decisions to accept, edit, reject or add terms.

Manual terms use the same concept-mapping checks as AI suggestions. Flag unmapped terms, uncovered chosen concepts, duplicates, unsupported vocabulary claims and potentially restrictive outcome/comparator blocks. Do not infer synonym correctness from word matching, or claim coverage because every question word is present. Group alternatives within concepts and combine concepts according to each database's actual capabilities; provider-neutral Boolean syntax is not assumed.

### E. Review the strategy and pilot

Show the question-to-component-to-term-to-source-query chain. Distinguish application checks from optional human PRESS review. Record seed-item recovery and pilot findings when that capability is implemented; missing pilot evidence is not a passed validation. Search execution remains behind existing explicit protocol/pilot authorization.

### F. Export and amendment behavior

Export named framework, citation, version, rationale, maps, generated/manual term provenance, unresolved flags and decisions. Question/framework changes stale the dependent concept/keyword assessment and affected search approvals; preserve earlier runs and assessments. Framework support must be included in question/protocol/AI disclosures and verification bundles without claiming assessments for legacy data.

## Bounded implementation and reviewer division

- **QF-1, reviewer design validation:** check primary-source applicability across intervention, qualitative, scoping and non-health reviews; propose the versioned catalog/component contract and synthetic acceptance cases. No shared dashboard edits or real model calls. No wholesale checklist copying; check licensing before embedding instruments.
- **QF-2, developer foundation after contract review:** manual per-question framework selection/mapping, explicit assessment state and provenance. No automatic scientific score or historical migration approval.
- **QF-3:** concept/term mapping and human decisions, then optional provider-neutral AI suggestions using the same contract.
- **QF-4:** source-specific strategy checks, pilot integration and export/verification regressions.

Minimum cases: manual and AI wording treated equally; multi-question mixed frameworks; no listed framework fits; AI invents an absent component; unmapped user term; valid concept deliberately excluded from search; unverified controlled-vocabulary claim; question edit stales terms; old review remains honestly unassessed; manual use requires no AI configuration.


## Implementation update — 2026-10-25

The initial audit above describes the pre-implementation state. A first optional manual foundation is now implemented: per-question guide/custom choice, researcher rationale/component states, exact-version reapproval, stored source metadata and export preservation. Initial PICO/PCC/SPIDER catalog is provisional pending independent QF-1 review. There is no automatic semantic assessment, score, framework-aware AI prompting or question-to-keyword mapping yet. QF-2 has begun as a reversible manual foundation; the broader catalog and final contract remain open to reviewer corrections. Existing approvals are not retrospectively reassessed.


## QF-1 disposition — 2026-10-25

Independent review is complete; see QF-1_Reviewer_Contract_Review.md and plan section 21. Next contract increment prioritizes consistent per-question framework provenance in protocol/export and source-grounded component statements. Literal-support claims require question quotes, while researcher context and AI inference require their own explicit provenance; quote matching cannot establish semantic correctness. Mixed frameworks must not be collapsed into one global framework. Remaining versioning/status/custom-component/catalog/export proposals require a versioned implementation with legacy preservation. The 8 expected-failure acceptance cases are unfinished work, not passing functionality.

## QF-2 completion — 2026-10-25

The manual reasoning contract is now `question-frameworks-v2`. Each new mapping stores the exact question hash, catalog and entry versions, a complete guidance snapshot and its canonical SHA-256. Identified components require an explicit support type: an exact substring quote from the question, or researcher-supplied context. Context need not occur in the question and is never represented as an extracted quote. Unsupported AI-inference provenance cannot be recorded through this manual contract. Literal matching establishes occurrence only, not semantic correctness. Generic AI question suggestions remain separate and do not generate or approve framework maps.

Components distinguish unreviewed, identified, missing, unclear and not applicable. Custom reasoning permits zero to eight named components; zero requires the same substantive rationale as every framework selection and documents a no-fit choice. Exported per-question states are unmapped, selected-not-reasoned, reasoned and reasoned-with-unresolved. Earlier catalog mappings retain their original content and are labelled legacy-unassessed in the new derived view. “Reasoned” describes recorded human explanations, not a methodological grade or independent validation.

Approved per-question maps are authoritative for saved protocols. Every protocol save path, including standalone ledger saves and accepted AI protocol edits, copies those maps and removes contradictory global framework/elements fields when mappings exist. Mixed frameworks remain separate records. Existing protocol content is not silently rewritten on read: mapping changes require question reapproval and a protocol amendment before final approval can become current. Unmapped legacy/standalone protocols retain their earlier global fields. Optional mapping remains optional; unresolved reasoning is visible and does not create an unagreed execution gate.

The question editor exposes support type, literal quotes, named custom components and missing states. The protocol page displays the approved per-question reasoning. Wording edits clear all current maps unless revised maps are explicitly saved with the wording; history survives. Bundles carry the framework contract version and replay the recorded history. Pre-v2 bundles use the original framework interpretation solely for historical verification, never live search authorization; v2 histories cannot downgrade to that compatibility path.

### Additional source checks and catalog scope

The catalog now offers PICO, PCC, SPIDER, PICo, PECO, CoCoPop, PIRD, CIMO and PICOC, plus custom/no-fit. This is a curated set, not an exhaustive taxonomy or an automatic suitability recommender. Purpose/limitations and a warning against mandatory component-to-search-block conversion accompany every entry. Applicability wording is paraphrased guidance and conservative application advice, not a reproduced assessment instrument.

- [JBI search development, section 2.4.3](https://jbi-global.atlassian.net/wiki/spaces/MANUAL/pages/652279828/2.4.3%2BDeveloping%2Ba%2BSearch%2BStrategy), page updated May 5, 2025, checked October 25, 2026: confirms PICo, CoCoPop and PIRD component definitions and the need to choose an approach for the question.
- [JBI question alignment, section 10.2.3](https://jbi-global.atlassian.net/wiki/spaces/MANUAL/pages/355862687/10.2.3%2BDefining%2Band%2Baligning%2Bthe%2Bobjective%2Bs%2Band%2Bquestion%2Bs), checked October 25, 2026: confirms PCC and circumstances where PICO/PECO may be justified.
- [Denyer, Tranfield and van Aken, 2008](https://journals.sagepub.com/doi/10.1177/0170840607088020), publisher abstract checked October 25, 2026: confirms CIMO's context, intervention, mechanism and outcome structure. The restricted full text was not claimed reviewed.
- [Kitchenham and Charters, EBSE-2007-01](https://ebse.webspace.durham.ac.uk/wp-content/uploads/sites/49/2022/08/Systematic-reviews-5-8.pdf), version 2.3, July 9, 2007, section 5.3.2, checked October 25, 2026: confirms PICOC and its software-engineering discussion. The first university mirror timed out; the Durham source supplied the edition and relevant passage.

QF-3 concept/term provenance, controlled-vocabulary verification and optional AI concept proposals remain the reviewer's design assignment in plan section 22. They are not claimed implemented by QF-2.
