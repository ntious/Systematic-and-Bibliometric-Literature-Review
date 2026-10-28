# QF-3 design review: question-to-search concept and term contract

**Assignment:** QF-3-DESIGN-REVIEW (plan section 22). **Reviewer:** independent reviewer. **Date:** 2026-10-25.
**Status:** proposal for developer assessment. Nothing here is implemented. Every API, field and event named below is **proposed**, unless it is marked **current** with a file reference.

**Inspected snapshot.**
- **Source:** the developer working tree at 2026-10-25T23:19Z (HEAD `369e8cd` plus uncommitted files). This already includes the accepted reviewer repair-2 patches and the QF-1 reference document.
- **Where it was committed:** frozen as commit `408a752` on branch `reviewer/qf3-design` in the isolated repo `../SLR-reviewer-repair2`.
- **Baseline test run** (WSL Ubuntu 24.04): 379 passed, 1 skipped.
- **Files read:** `question_frameworks.py`, `questions.py`, `protocol.py`, `review_plan.py`, `protocol_ai.py`, `pipeline.py`, `search.py`, `pubmed.py`, `calibration.py` and related tests. All were read only.

**Assumptions about unfinished QF-2.** `question_frameworks.py` in the snapshot is still QF-1's v1: index-keyed maps, four statuses, no quotes, no `missing` status, and no shared protocol record. This proposal therefore depends only on a **minimal QF-2 interface** (§2.1). If QF-2 lands with different names, map them; do not treat this as available functionality.

---

## 1. Methodological basis

Every source below was checked on 2026-10-25 against its primary page, or against Europe PMC or Crossref. Where a guideline says something, it is labelled **[sourced]**. Where it is this reviewer's design choice, it is labelled **[engineering]**.

| # | Source (as verified) | What it supports | Link |
|---|---|---|---|
| S1 | Cochrane Handbook for Systematic Reviews of Interventions, ch. 4 *Searching for and selecting studies*, v6.5.1 (March 2025) | **§4.4.2:** search the main concepts, OR terms within a concept, AND the concepts together, and avoid NOT where possible. It is usually unnecessary, even undesirable, to search every aspect of the question; comparators and outcomes are often poorly indexed. **§4.4.4:** combine text words with controlled vocabulary; include spelling variants, synonyms and acronyms; truncation and proximity exist; strategies must be customised per database, because MEDLINE and Embase vocabularies differ. **§4.4.5:** avoid language restrictions and justify date limits. **§4.4.7:** use tested search filters where appropriate. **§4.4.8:** strongly recommends peer review before searches run. **§4.5:** save strategies exactly as run. | https://www.cochrane.org/authors/handbooks-and-manuals/handbook/current/chapter-04 |
| S2 | McGowan J, Sampson M, Salzwedel DM, et al. *PRESS Peer Review of Electronic Search Strategies: 2015 Guideline Statement*. J Clin Epidemiol 2016;75:40-46 | Peer review of a finished strategy by a second person, in six elements: translation of the research question; Boolean and proximity operators; subject headings; text word searching; spelling, syntax and line numbers; limits and filters. It is a **review method**, not a term generator. | https://doi.org/10.1016/j.jclinepi.2016.01.021 |
| S3 | Rethlefsen ML, Kirtley S, Waffenschmidt S, et al. *PRISMA-S*. Syst Rev 2021;10:39 (PMC7839230) | Sixteen reporting items. Item 8 asks for full search strategies for each source, exactly as run; item 9 limits and restrictions; item 10 search filters; item 13 dates of searches; item 14 peer review; item 16 deduplication. This is **reporting**, not validation. | https://doi.org/10.1186/s13643-020-01542-z |
| S4 | JBI Manual for Evidence Synthesis, §2.4.3 *Developing a search strategy* | Break the question into key concepts and use a logic grid. Gather synonyms across disciplines, including international, British/American and historical terms. Use subject headings where available and appropriate, together with keywords. Lists PICO, PCC, PICo, CoCoPop and PIRD structures. | https://jbi-global.atlassian.net/wiki/spaces/MANUAL/pages/652279828/2.4.3%2BDeveloping%2Ba%2BSearch%2BStrategy |
| S5 | JBI Manual §10.2.3 (scoping reviews) | PCC is suggested for scoping questions; one element may be unnecessary, and PICO/PECO may be used for some purposes. | https://jbi-global.atlassian.net/wiki/spaces/MANUAL/pages/355862687/10.2.3%2BDefining%2Band%2Baligning%2Bthe%2Bobjective%2Bs%2Band%2Bquestion%2Bs |
| S6 | Harris JL, Booth A, Cargo M, et al. Cochrane Qualitative and Implementation Methods Group guidance, paper 2. J Clin Epidemiol 2018;97:39-48 | For qualitative evidence synthesis, question formulation and searching are **iterative**, and the protocol is "a guide rather than a prescriptive route map". Several question frameworks and logic models are used. | https://doi.org/10.1016/j.jclinepi.2017.10.023 |
| S7 | Booth A. *Searching for qualitative research for inclusion in systematic reviews: a structured methodological review*. Syst Rev 2016;5:74 | The empirical evidence for qualitative search practice is weak, and key procedures need further evaluation. This argues against hard-coded rules. | https://doi.org/10.1186/s13643-016-0249-x |
| S8 | Methley AM, Campbell S, Chew-Graham C, et al. BMC Health Serv Res 2014;14:579 | In the studied health-database setting, SPIDER-structured searches were more specific and less sensitive than PICO. As accepted in section 21, this is **not** generalised beyond that setting. | https://doi.org/10.1186/s12913-014-0579-0 |
| S9 | Kugley S, Wade A, Thomas J, et al. *Searching for studies: a guide to information retrieval for Campbell systematic reviews*. Campbell Syst Rev 2017;13(1) | Social sciences: education, crime and justice, social welfare and international development. | https://doi.org/10.4073/cmg.2016.1 |
| S10 | Kitchenham B, Charters S. *Guidelines for performing Systematic Literature Reviews in Software Engineering*, v2.3, EBSE Technical Report EBSE-2007-01, Keele University and University of Durham, 9 July 2007 | **Non-health.** Break the question into facets (population, intervention, comparison, outcomes, context, study designs), list synonyms, abbreviations and alternative spellings, consider subject headings, and build strings with Boolean AND/OR. It attributes **PICOC** to Petticrew and Roberts, *Systematic Reviews in the Social Sciences* (2006). (Edition check requested in section 21: done, v2.3.) | https://legacyfileshare.elsevier.com/promis_misc/525444systematicreviewsguide.pdf |
| S11 | Denyer D, Tranfield D, van Aken JE. Organization Studies 2008;29(3):393-413 | CIMO (context, intervention, mechanism, outcome) for management and organisation questions. | https://doi.org/10.1177/0170840607088020 |
| V1 | NLM MeSH RDF / Linked Data (`id.nlm.nih.gov/mesh/lookup?form=descriptor&label=…`) | A controlled-vocabulary **authority** with stable descriptor UIs (D + digits) and yearly versions. Lookup evidence can be recorded. | https://id.nlm.nih.gov/mesh/ |
| V2 | ERIC Thesaurus (IES) | Education descriptors are assigned to every ERIC document. This is a second authority, showing that vocabularies are discipline-specific. | https://eric.ed.gov/?ti=all |
| P1 | OpenAlex *Search entities* (last updated 2026-10-03) | Plain `search` covers title, abstract, fulltext and keywords. Uppercase AND/OR/NOT, quoted phrases, `"…"~N` proximity, and stemming with stop-word removal are supported. Wildcards only with `.exact` variants; field variants `search.title`, `search.title_and_abstract`. | https://help.openalex.org/how-to-use-the-api/get-lists-of-entities/search-entities |
| P2 | PubMed Help | Automatic Term Mapping (turned off by tags, quotes and wildcards). Field tags `[tiab] [mh] [majr] [tw]`. Uppercase Boolean, evaluated left to right with parentheses. `*` needs 4 or more leading characters. Proximity `"a b"[tiab:~N]`. | https://pubmed.ncbi.nlm.nih.gov/help/ |
| P3 | Crossref REST API documentation (the GitHub README is marked deprecated, with current docs at api.crossref.org) | `query` is free-form and **relevance-ranked**; field queries (`query.bibliographic`, `query.author`…) are ANDed. **No Boolean, phrase or wildcard syntax is documented.** | https://github.com/CrossRef/rest-api-doc |

**Where these sources stop.** None of them supplies a universal keyword rule, or a way to validate synonyms semantically from strings. S7 explicitly calls the evidence base weak. The contract below therefore records **reasons and provenance**. It never records "correctness".

### 1.1 Four activities that must not be conflated

| Activity | Who | Output | In LitAtlas |
|---|---|---|---|
| **Question formulation** | Researcher, optionally with AI proposals | Approved questions and framework maps (QF-1/QF-2) | `questions.py` (current) |
| **Search development** [sourced S1, S4, S10] | Researcher or information specialist | Concepts, terms per concept, include/omit decisions, source-specific strings | **QF-3 (proposed)** |
| **PRESS-style peer review** [sourced S2] | A *second* person, by human judgement | Recorded review outcome per PRESS element | Proposed optional event (§3.4); never automated |
| **Reporting** [sourced S3] | Software assembles; the researcher verifies | PRISMA-S items, especially 8, 9, 10, 13 and 14 | Export (§4.3) |

### 1.2 How question components become search concepts

The rules below are labelled **[sourced]** or **[engineering]** according to their origin.

1. **A concept is not a component** [engineering, from S1 §4.4.2 and S4]. A concept may serve several components or several questions; for example, "secondary-school pupils" can serve two PICO questions. A component may yield no concept at all, such as an outcome deliberately not searched.
2. **Inclusion as a block is a decision with a reason** [sourced S1 §4.4.2]. The default proposal includes population and intervention/phenomenon/concept components, and **proposes omitting** comparator, outcome and design components as blocks. That proposal is never automatic: the researcher sees it and decides.
3. **Terms within a concept are alternatives** [sourced S1, S4, S10]: synonyms, acronyms, spelling (British/American) and historical variants, phrases and controlled headings. Concepts are combined, terms are ORed, and blocks are ANDed, **only where the provider supports it** (§4.4).
4. **Controlled headings need an authority** [sourced S1 §4.4.4, V1, V2]: MeSH for PubMed, ERIC descriptors for education, and others by discipline. A heading is a claim about an external vocabulary. It is `unverified` until a lookup records evidence.
5. **Iterative qualitative searching** [sourced S6, S7]: concept sets are versioned, and supplementary methods (citation searching) are recorded separately, not forced into blocks.
6. **No universal rules** [sourced S7, S8, section 21]. The software flags facts (§3.3). It never declares a strategy adequate.

### 1.3 Worked disciplines

These are synthetic examples; their fixtures are in `tests/test_qf3_acceptance.py`.

| Review | Question (synthetic) | Concepts (included blocks) | Deliberate omissions |
|---|---|---|---|
| Intervention, education (PICO) | "In secondary-school pupils, does retrieval practice compared with re-reading improve exam scores?" | pupils; retrieval practice | comparison (re-reading) and outcome (exam scores): poorly indexed, and they lose sensitivity [S1] |
| Qualitative, nursing (SPIDER) | "How do novice nurses experience their first night shifts, as reported in interview studies?" | novice nurses; night shift work | design/research type (interviews, qualitative): risks sensitivity [S8, setting-specific]; use a tested filter only if one is chosen [S1 §4.4.7] |
| Scoping, agriculture (PCC) | "What is known about community seed banks in arid regions of East Africa?" | seed banks; arid East Africa (context) | none, but context is flagged as possibly restrictive for researcher judgement |
| Software engineering (PICOC) [S10] | "In industrial agile teams, how does test-driven development affect defect density compared with test-last development?" | TDD (with acronym); industrial context | comparison and outcome |
| Management (CIMO) [S11] | "What mechanisms explain when participatory budgeting increases civic trust?" | participatory budgeting; civic trust | mechanism (often unindexed): kept as a screening criterion instead |

---

## 2. Versioned data and API contract (proposed: `search-concepts-v1`)

### 2.1 Minimal interfaces assumed from QF-2

QF-2 is not built. These are the inputs QF-3 needs:

- An **approved question set identity**: `question_approval = {draft_sequence, sha256}` (current; `questions._state`).
- Per question: `question_sha256` (current: QF-1 maps store it) and `question_index`.
- Per component: `framework` plus `component_id`, and a component **basis**: `literal-quote` (with an exact substring), `researcher-context` or `ai-inference-confirmed` (section 21's C3 refinement). The basis is **proposed** for QF-2.
- A **guidance digest** per framework entry (QF-1 C2; proposed).

If a question has no framework map, QF-3 still works with **free concepts** (`links: []`, `basis: unlinked`). Frameworks remain optional. Such a concept is flagged as unlinked, not rejected.

### 2.2 Records

```json
{
 "schema": "search-concepts-v1",
 "question_approval": {"draft_sequence": 7, "sha256": "…"},
 "concepts": [{
   "concept_id": "c-1",
   "label": "Retrieval practice",
   "links": [{"question_index": 0, "question_sha256": "…", "framework": "PICO", "component_id": "intervention",
              "basis": "literal-quote", "quote": "retrieval practice"}],
   "block": {"included": true},
   "terms": ["t-1", "t-2", "t-3"]
 }, {
   "concept_id": "c-3", "label": "Exam scores", "links": [ … "component_id": "outcomes" … ],
   "block": {"included": false, "rationale": "Outcome terms are poorly indexed; searching them would reduce sensitivity (Cochrane 4.4.2)."},
   "terms": []
 }],
 "terms": [{
   "term_id": "t-2", "concept_id": "c-1", "text": "testing effect", "kind": "synonym",
   "origin": {"type": "ai-proposal", "proposal_sequence": 41, "index": 2},
   "decision": {"state": "accepted", "event_sequence": 44, "actor": "A"}
 }, {
   "term_id": "t-9", "concept_id": "c-1", "text": "Retrieval practice", "kind": "controlled-heading",
   "origin": {"type": "researcher"},
   "vocabulary": {"authority": "ERIC", "identifier": null, "label": "Retrieval practice",
                  "status": "unverified", "lookup": null},
   "decision": {"state": "accepted", "event_sequence": 45, "actor": "A"}
 }],
 "source_strings": [{"adapter": "pubmed", "query": "…", "built_from": {"concept_ids": ["c-1", "c-2"], "term_ids": ["…"]},
                     "rendering": "builder-v1", "syntax": "executable", "unsupported": []}]
}
```

**Identity and binding.**
- IDs are stable within a review (`c-N`, `t-N`), assigned server-side and never reused.
- The **concept set digest** is the hash of the canonical record minus decision event numbers. It is bound to `question_approval`.
- Approval of the strategy binds to that digest. **Saving is never approval.**

**Enumerations.**

| Field | Values | Notes |
|---|---|---|
| `kind` | `free-text`, `phrase`, `synonym`, `acronym`, `spelling-variant`, `historical-term`, `controlled-heading` | Display labels only; nothing is inferred from them |
| `origin.type` | `researcher`, `ai-proposal`, `vocabulary-lookup` | AI and researcher terms pass identical validation and decision rules |
| `decision.state` | `proposed`, `accepted`, `edited`, `rejected` | `edited` keeps `original_text`; only `accepted`/`edited` terms enter strings |
| `vocabulary.status` | `unverified`, `verified`, `not-found`, `lookup-failed`, `lookup-unavailable` | Only `verified` may show an authority identifier as confirmed |
| link `basis` | `literal-quote`, `researcher-context`, `ai-inference-confirmed`, `unlinked` | `literal-quote` requires an exact substring of the hashed question |
| `syntax` | `executable`, `manual-only`, `unsupported` | Per adapter (§4.4) |

**Vocabulary evidence.** Each verification records an append-only event:

```json
{"authority": "MeSH", "identifier": "D012345", "label": "…", "version": "2026",
 "method": "researcher-entered" | "nlm-mesh-lookup",
 "retrieved_utc": "…", "endpoint": "https://id.nlm.nih.gov/mesh/lookup?…",
 "response_sha256": "…", "status": "verified"}
```

- `researcher-entered` verification is allowed: the researcher looked it up manually. It is labelled as such and needs no network.
- An **LLM output can never set `verified`**: the server rejects `vocabulary.status` in AI proposals.
- A failed or timed-out lookup is recorded as `lookup-failed`, never as verified, and never silently retried.

### 2.3 Events

These are proposed. They live in `plan_events`, alongside the protocol, so that they share revision and expected-identity checks.

| Kind | Content | Rules |
|---|---|---|
| `concept-save` | full concept set + digest + `question_approval` | Requires the current question approval and `expected_revision`. Creates a draft; no approval. |
| `term-ai-request` / `term-ai-proposal` / `term-ai-failure` | as `protocol_ai`, task `search-concepts`, `prompt_version` | Stage-specific opt-in, `allow_external` for cloud. A packet contains approved questions, framework components and the current concept set, never records or PDFs. |
| `term-decision` | `{proposal_sequence, index, decision, original_text, text}` | One decision per item. A stale guard applies, as in `protocol_ai.decide`. |
| `vocabulary-evidence` | as in §2.2 | Researcher-entered or lookup. Never from AI. |
| `strategy-approval` | `{concept_set_sha256, question_approval, source_strings_sha256}` | An explicit human act. Feeds the existing `search` section approval (§4.1). |
| `press-review` (optional) | `{reviewer, elements: {translation, boolean_proximity, subject_headings, text_words, spelling_syntax, limits_filters}: {outcome, notes}, concept_set_sha256}` | Paraphrased element names only (S2). The reviewer must differ from the last concept-set saver (configurable). Advisory; not a gate by default (§3.4). |

### 2.4 Proposed service API

New module `src/slr/search_concepts.py`. All functions below are **proposed**.

| Function | Purpose | Network |
|---|---|---|
| `validate(concept_set, question_state)` | Shape, ID uniqueness, link and quote checks, the omission-rationale rule, and enum and AI-field restrictions | none |
| `review_states(concept_set)` | Advisory flags (§3.3), returned with reasons and no score | none |
| `render(adapter, concept_set)` | Builds source strings from accepted terms of included blocks, and reports `syntax` and `unsupported` | none |
| `staleness(current, recorded)` | Which records and approvals are stale, and why (§4.1) | none |
| `record_vocabulary_evidence(db, body)` | Appends an evidence event (researcher-entered) | none |
| `lookup_mesh(label)` (optional, later) | NLM lookup through the existing `HTTPClient`, with explicit consent and evidence recording | yes, opt-in |

**Manual operation needs no AI configuration and no network.** Every core function is offline.

---

## 3. Researcher journey and safety boundaries

### 3.1 The table (one screen per approved question set)

| Concept | Linked to | Block | Terms (state) | Headings (status) | Issues |
|---|---|---|---|---|---|
| Retrieval practice | Q1 · intervention · quote "retrieval practice" | ✔ included | retrieval practice ✔ · testing effect ✔ · practice testing ⧗ | ERIC "Retrieval practice" (unverified) | 1 proposal pending |
| Exam scores | Q1 · outcomes | ✖ omitted: "poorly indexed; sensitivity" | — | — | — |

**Actions:**
- add, edit or rename a concept;
- link a concept to a question component;
- add, edit, accept or reject a term;
- add a heading;
- record lookup evidence;
- include, or omit with a rationale;
- render source strings;
- **approve strategy**, as a separate button that shows the impact summary.

AI suggestions appear as **proposed** rows with their rationale. They are accepted or rejected per item, exactly like manual rows awaiting review.

### 3.2 AI boundaries

- **Opt-in:** AI is off for this stage unless enabled here, with per-request consent for cloud providers. Nothing is sent when a page opens or a draft is saved.
- **What AI can propose:** concepts, terms and candidate headings only (`origin: ai-proposal`, `vocabulary.status` forced to `unverified`).
- **What AI cannot do:**
  - approve anything;
  - verify a heading;
  - set a block omission without a researcher-confirmed rationale;
  - add an adapter.
- **What the instructions tell the model:** "You have no vocabulary lookup tools; never claim a heading exists or is verified."
- **Validation:** AI items pass exactly the validators manual input passes.

### 3.3 Advisory review states

These are facts, never grades.

| Flag | Condition (deterministic) | Shown as |
|---|---|---|
| `uncovered-concept` | An included concept has no accepted term | "No accepted terms; this block would match nothing or be dropped." |
| `unmapped-term` | An accepted term is attached to no included concept (orphaned, or its concept was omitted) | "Not used in any search block." |
| `unlinked-concept` | Concept `links: []` | "Not traced to an approved question component (allowed; explain in the protocol if intended)." |
| `possible-duplicate` | Same NFKC-casefolded text in one concept | "Duplicate spelling; keep both only if their meanings differ." **Never auto-deleted.** |
| `restrictive-block` | The included block came from a comparator, outcome, design or research-type component | "May reduce sensitivity (Cochrane 4.4.2); confirm or omit with a reason." |
| `unverified-heading` | `controlled-heading` with a status other than `verified` | "Heading not verified against its vocabulary." |
| `adapter-unsupported` | `render` reports `unsupported` items for a selected adapter | "Part of this strategy cannot run on this source; record it as a manual search." |
| `stale-binding` | The concept set's `question_approval` is not current | "Questions changed; review the concept table." |

### 3.4 Gates versus warnings (with reasons)

| Rule | Type | Reason |
|---|---|---|
| A `literal-quote` link must be an exact substring of the hashed question | **validation error** | Otherwise it is a false provenance claim (QF-1 C3) |
| An omitted block needs a rationale of at least 20 characters | **validation error** | Omission is a methodological decision [S1] |
| AI items may not set `verified`, `included: false` or `approved` | **validation error** | Human control |
| Strategy approval requires the current question approval, a current concept set and no `stale-binding` | **gate** | Approval must bind exact content |
| Strategy approval with `uncovered-concept`, `unverified-heading` or `restrictive-block` present | **allowed, with each flag acknowledged in the approval event** | These are judgements, not errors; acknowledging them avoids silent rubber-stamping |
| PRESS review | **optional advisory**; a per-review setting may make it required before full-search authorization | PRESS is strongly recommended [S1 §4.4.8], but making it mandatory for students or solo reviewers is the owner's decision (§5) |
| Existing protocol, pilot and full-search gates | **unchanged** | QF-3 feeds the `search` section and never replaces it |

**Never:** turn every framework component into a mandatory AND block; translate provider-neutral Boolean silently; or claim adequacy, coverage percentages or recall.

---

## 4. Amendment, export and dependency matrix

### 4.1 What becomes stale

The concept set feeds the existing `search` section, whose hash covers `keywords`, `search_strategy`, `searches`, the criteria hash and the period (current: `review_plan._section_hash`). The proposal adds `search_concepts_sha256` to that payload.

| Change | Becomes stale | Unchanged (readable, verifiable) |
|---|---|---|
| Question wording (new draft or approval) | Question approval → QF-2 maps → concept links (`stale-binding`) → strategy approval → `search` section and final approval → pilot and full authorization | Earlier concept sets, approvals and all runs (historical) |
| Framework or component map | Links to the changed components only; strategy approval → `search` section → final | Unaffected concepts and terms; runs |
| Term added, edited or rejected, or block include/omit | Concept set digest → strategy approval → `search` section → final; **new pilot required** if the rendered strings change (`strategy_sha256`) | Runs; other questions' links |
| Vocabulary verification added | Concept set digest → strategy approval (re-approve quickly) | Rendered strings, if text is unchanged, so no new pilot |
| Source or query syntax (manual edit of a rendered string) | The string is marked `hand-edited` and no longer builder-derived. Strategy approval → `search` section → final → new pilot | Concept table |
| Record limits | As current (WA-04 open: the cap is not in `strategy_sha256`); the proposal follows the developer's WA-04 decision | — |

### 4.2 Legacy states

- A review with `keywords` and free-text `searches` but no concept set reports **`concept-set: not assessed`**. Nothing is inferred from existing keywords, and its current approvals stay valid under today's rules.
- An optional "import keywords as unlinked proposed terms" action creates `proposed` rows. It never approves them.
- Opening a page, saving, or completing a model request never grants approval.

### 4.3 Export, disclosure and verification

- **`search-concepts.json`:** the full current set, and every historical set with its digest and binding.
- **`search-concepts-history.json`:** all events, including rejected terms, original wording of edited terms, omission rationales, vocabulary evidence and PRESS reviews.
- **PRISMA-S support** [S3]:
  - item 8: rendered strings "as run" from the run manifests (current: manifests keep `searches`);
  - item 10: filters, if recorded;
  - item 14: the PRESS event or "none recorded";
  - all items keep their "needs author input" labels.
- **AI disclosure** (current `ai_disclosure.capture`) gains stage `search-concepts`, counting requests, proposals and decisions.
- **Verification bundle** (`replication.verify`) recomputes the digest, review states and rendered strings from the bundled ledger. A mismatch, or an altered binding, fails, so a stale set cannot appear current.

### 4.4 Provider capabilities

Capabilities come from the inspected code (`search.py`, `pubmed.py`) and the documentation in P1–P3.

| Adapter | Query sent as (current) | Builder support (proposed) | Unsupported, so `manual-only` |
|---|---|---|---|
| PubMed | `esearch term=` verbatim | Uppercase Boolean with parentheses; `"phrase"[tiab]`; `[mh]` only for `verified` MeSH headings; `*` only with 4 or more leading characters | Emtree and other vocabularies; proximity beyond `[tiab:~N]` |
| OpenAlex | `/works search=` verbatim (title, abstract, fulltext, keywords) | Uppercase Boolean, quoted phrases | Controlled headings (no MeSH field); wildcards (these need `.exact` field variants the adapter does not use); field restriction |
| Crossref | `/works query=` verbatim (relevance-ranked) | A single unstructured term list, **labelled relevance-only, not a Boolean block search** | Blocks/AND, phrases, wildcards, headings |
| Manual databases (Scopus, WoS, ERIC, Embase…) | not executed | Builder output as text for copy, labelled manual | Everything executable |

- **Every query in `searches[].queries` runs as a separate search** (current: `pipeline.run_plan`). The builder therefore renders **one string per adapter**, with blocks combined inside it, not one query per concept.
- **Pilot recovery metrics do not exist in the governed workflow.**
  - `calibration.py` (current) offers literal term-group cues and illustrative known-item capture, explicitly "not a recall estimate".
  - It is reachable only through the standalone pipeline's `relevance_policy`; `review_plan.executable` does not pass it.
  - QF-3 must not claim recall. Wiring known-item capture into the governed pilot is a separate decision (§5).

---

## 5. Acceptance specification and implementation recommendation

### 5.1 Executable acceptance cases

The cases are in `tests/test_qf3_acceptance.py`, in the reviewer checkout only.

- **Current-behaviour facts (11 tests, all pass; the adapter test runs once per adapter).** These are the facts the design relies on:
  - adapter request parameters;
  - per-query execution;
  - the flat `keywords` field;
  - the search-section hash staling on keyword edits;
  - calibration's "not recall" wording;
  - governed plans dropping `relevance_policy`;
  - query strings passed verbatim;
  - manual questions working with AI off.
- **Proposed contract (14 tests, strict `xfail(raises=ImportError)` against the proposed `slr.search_concepts`).**
  - Each test carries its synthetic fixture and expected result.
  - Once the module exists, a wrong behaviour shows as a **failure** and a correct one as **XPASS**, which strict mode turns into a failure until the marker is removed.
  - None of these is a passing test of implemented behaviour.

The tests below cover the twelve scenarios from section 22, plus the gates in §3.4.

| Scenario (section 22) | Test(s) |
|---|---|
| Manual and AI identical; AI off | `test_ai_and_manual_terms_pass_identical_validation`, `test_core_functions_need_no_ai_or_network` |
| Mixed frameworks; shared concept | `test_shared_concept_traces_to_two_questions` |
| Deliberate omission | `test_omission_needs_rationale_and_is_never_automatic` |
| Unmapped term; uncovered concept | `test_review_states_flag_unmapped_and_uncovered_without_scores` |
| Invented heading or synonym; verified; lookup failure | `test_ai_cannot_verify_headings`, `test_verified_heading_records_evidence_and_failure_is_not_verification` |
| Literal / context / inference | `test_literal_quote_must_occur_in_the_question` |
| Duplicates preserved | `test_possible_duplicates_are_flagged_not_deleted` |
| Edits stale dependents | `test_question_edit_stales_concept_set_and_strategy` |
| Unsupported operators | `test_render_labels_unsupported_syntax_per_adapter` |
| Legacy unassessed; no implicit approval | `test_legacy_keywords_are_not_assessed_and_saving_is_not_approval` |
| Export and replay bindings | `test_digest_changes_with_content_and_detects_altered_binding` |
| Cross-discipline wording | `test_restrictive_block_flag_uses_component_role_not_discipline` |

### 5.2 Phased implementation (developer-owned)

| Phase | Scope | Files | Depends on |
|---|---|---|---|
| Q3-A | Records, `validate`, `review_states`, `render` (offline), digest; `concept-save` and `term-decision` events | **new** `src/slr/search_concepts.py`; `review_plan.py` (add the digest to the `search` hash, plus `strategy-approval`) | QF-2 basis and component IDs (§2.1) |
| Q3-B | Dashboard table, approval with acknowledged flags, impact summary | **new** `src/slr/web/search_concepts.js`; minimal `protocol.js` hook | Q3-A |
| Q3-C | Export, disclosure and verification fields (§4.3) | `review_cli.py`, `ai_disclosure.py`, `replication.py` | Q3-A |
| Q3-D | AI term proposals (same contract) | **new** `search_concepts_ai.py` reusing `ai_providers`, `local_ai` | Q3-A |
| Q3-E (optional) | Researcher-entered and NLM-lookup vocabulary evidence; PRESS event | `search_concepts.py`; reuse `search.HTTPClient` | Q3-A |

**Priority:** Q3-A → Q3-C → Q3-B → Q3-D → Q3-E. Export and verification come before the UI, so nothing appears current without being verifiable.

### 5.3 Blockers, open decisions and follow-ups

- **Blocker:** the QF-2 component identity and basis (§2.1). QF-3 links cannot be validated without it.
- **Decisions for the developer or owner:**
  1. Should PRESS be required before full search, per review or never? The recommendation is optional by default, configurable per review.
  2. Should the builder emit strings automatically, or only on request? The recommendation is on request, with a hand-edit flag.
  3. Should the NLM MeSH lookup ship (opt-in network), or should only researcher-entered evidence be supported at first? The recommendation is researcher-entered first.
  4. Should the WA-04 cap binding be decided before Q3-A, since it affects which edits require a new pilot?
  5. Should calibration's known-item capture be wired into the governed pilot as an illustrative, non-recall panel (a separate assignment)?
- **Bounded follow-ups (not QF-3):**
  - WA-05 (question history in the review export) should land before Q3-C, so exports are consistent.
  - WA-08 (import-source provenance) interacts with manual-search strings.
- **Optional enhancements (not required):**
  - search filters from a curated list, with sources;
  - ERIC or other thesaurus lookups;
  - provider-specific proximity rendering.
