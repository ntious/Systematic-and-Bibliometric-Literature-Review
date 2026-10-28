# Human oversight workflow: agreement and implementation plan

Started: 2026-10-23.

This document records workflow decisions agreed during the step-by-step design discussion. It is a planning record, not a claim that the features are implemented. Accumulate the agreed requirements here before scheduling implementation across the full workflow.

## Discussion status

- Step 1 — Application entry: accepted in principle; detailed implementation requirements have not been discussed here.
- Step 2 — Topic and research questions: agreed as recorded below; implementation pending.
- Step 3 — Protocol: agreed on 2026-10-23; implementation pending.
- Step 4 — Pilot search and review: agreed on 2026-10-23 as recorded below; implementation pending.
- Steps 5–11: pending detailed discussion. Earlier proposals remain proposals until reviewed.

## Step 2 — Topic and research questions

### Agreed purpose

Support researcher judgment with optional AI assistance, explicit human approval and an inspectable contribution history. Entering a topic must not automatically produce an approved review or paper.

### Three supported paths

1. **Researcher writes independently:** enters a topic and research questions without AI assistance.
2. **AI refines a researcher draft:** the researcher enters a topic and draft questions, then explicitly enables AI to suggest refinements and identify ambiguities in either the topic or questions.
3. **AI generates candidate questions:** the researcher enters a topic and explicitly requests AI-generated research questions, which remain proposals until reviewed.

AI is off until enabled by the researcher. Enabling AI or requesting a response does not accept its output. All three paths require explicit approval of the final topic and research questions.

### AI caveat

Display this notice with AI-assisted proposals before approval:

> AI suggestions may contain errors, unsupported assumptions or unsuitable questions. Check their accuracy, scope and suitability before approving.

### Researcher control and approval

- Show the original text beside proposed revisions, with changes highlighted.
- Allow the researcher to accept, edit or reject individual suggestions.
- Accepting a suggestion changes the working draft; it does not grant final approval.
- Provide a separate **Approve topic and research questions** action.
- Bind approval to the exact approved version, with the recorded approver and approval time.
- Subsequent changes create a revised draft requiring approval again. Retain the previous approved version and its history.

### Contribution and revision history

Preserve, without overwriting earlier versions:

- The researcher's original topic and questions, including a topic-only starting point.
- Each AI request and response, provider, model identifier and time.
- Suggestions accepted, edited or rejected and the resulting text.
- Subsequent researcher revisions and their sequence.
- The final approved version, recorded approver and approval time.

The history must distinguish submitted researcher text, AI proposals, researcher edits and approval. Preserve the lineage when the researcher edits an AI proposal before accepting it.

### Export for educational disclosure

Provide an **AI assistance and revision record** containing:

- The original submission.
- AI proposals and the researcher's responses and revisions.
- The final approved topic and questions.
- The approval record.
- An editable draft AI-use disclosure derived from recorded actions, which the researcher must verify before using.

Do not assign percentages of authorship or intellectual contribution from edit counts. The record documents actions within LitAtlas; it cannot establish whether pasted text involved AI outside the application. In the current local application, approver names are recorded labels, not verified identities.

### Implementation backlog — pending

- [ ] Add the three topic/question paths and explicit opt-in AI controls.
- [ ] Add the AI caveat and side-by-side revision comparison.
- [ ] Add individual accept, edit and reject actions with separate final approval.
- [ ] Store original submissions, AI interactions and researcher revisions with version lineage.
- [ ] Bind approvals to exact versions and require renewed approval after changes.
- [ ] Export the contribution history, approved version and editable disclosure draft.
- [ ] Test that AI output cannot silently replace or approve researcher text; rejected proposals stay out of the approved version; revisions require renewed approval; and exports accurately reproduce the recorded history.

Provider selection, retention settings and detailed technical design remain implementation decisions to resolve later. This agreement does not authorize sending existing research content to an external AI provider automatically.

## Step 3 — Guided protocol with optional AI proposals

Status: researcher proposal and refinements agreed 2026-10-23. Planning only; no new runtime behavior implemented.

### Proposed workflow

Enter this stage after approval of the step-two topic and question version. Offer AI assistance for the protocol explicitly, even if the researcher used AI in step two; allow a fully manual route. Carry forward the approved questions as versioned context, rather than silently rewriting them.

Guide the researcher through these sections:

1. Eligibility: explicit inclusion and exclusion criteria, including publication period and other scope restrictions.
2. Information sources: supported retrieval sources and separately labelled manual-import sources.
3. Keywords and source-specific search strategies: editable terms, queries, filters and retrieval limits.
4. Screening procedure: reviewers, calibration, decision reasons and conflict resolution.
5. Extraction fields: what information will be collected and how missing information is represented.
6. Appraisal: the applicable framework, judgments and reviewer procedure.
7. Synthesis plan: how approved evidence will be organised, compared and interpreted.

Ask for the intended publication period before generation. AI may propose dates only as visibly unconfirmed suggestions; neither AI guesses nor interface defaults count as researcher approval. Distinguish publication period from the date a search is executed.

For each proposed criterion or other editable item, provide accept, edit, remove and add controls. Removing a suggestion excludes it from the active protocol but preserves its history. Regeneration must not overwrite accepted researcher work. Carry forward the step-two AI caveat and contribution-history requirements.

For sources, populate choices from actual application capabilities, not AI claims. Show whether a source supports automated metadata retrieval, manual export/import, full-text availability where known, or is unsupported. Let users add supported choices; unsupported databases may be documented as planned manual searches without pretending that the pipeline can search them. Metadata access does not promise full-text access. Generate source-appropriate queries and validate supported syntax; do not assume identical Boolean behavior across adapters.

### Approval without excessive clicks

Individual accept/edit/remove actions curate a draft. Each section then has one explicit approval action. Required sections may be marked not applicable with a rationale where methodologically appropriate. A final summary approves the exact protocol version and unlocks the main retrieval run. Drafting and saving remain available before approval. Any pilot-search exception must be explicitly defined and labelled separately before implementation.

Enforce the approval gate in the service/CLI as well as the interface. Bind the executable plan to approved questions, protocol version/content hash, sources, queries, dates and limits. A saved protocol is not automatically an approved protocol.

### Amendments and repeat runs

Default to the current approved version, with previous versions available in history. Editing creates a new draft, retaining the prior approved version. Record the actor label, time, changed items, AI involvement and amendment rationale. Approval applies only to an exact version.

Each run keeps its own identifier, approved input versions, executed configuration, dates, results and failures. A rerun creates a new run; it never overwrites the earlier one. Show the version associated with each result. Changes trigger an impact summary and renewed approval for affected sections and the final protocol. Criteria changes can require a new screening pass; a wording-only edit should not automatically rerun every stage. Changes to the approved questions require checking the dependent protocol approvals.

### Comparison with current code — 2026-10-23

- `src/slr/protocol.py` already supports structured protocol fields, assigned actor labels, append-only versions, content hashes, amendment descriptions/rationales and links to criteria versions. It does not implement section approval states or the proposed protocol AI interaction history.
- `src/slr/pipeline.py` accepts sources, queries, publication years and limits and records sessions. Automated retrieval currently supports OpenAlex, Crossref and PubMed. Execution is not bound to an approved protocol version.
- `src/slr/web/app.js` currently displays the question, criteria and people; provides criteria revision; and launches searches with selectable sources and dates. It does not provide the proposed guided protocol editor or section/final approval gates. The search form currently supplies 2020–2025 defaults, which should become explicit researcher choices under this design.
- Existing criteria revisions preserve earlier decisions and start a new screening pass; existing evidence can become historical. This is a foundation for impact tracking, not the full cross-stage dependency model proposed here.

### Implementation backlog — pending

- [ ] Build the guided section editor and explicit protocol-stage AI opt-in.
- [ ] Store item-level proposal actions and researcher/AI contribution lineage.
- [ ] Require researcher-confirmed period, sources, queries and limits.
- [ ] Add a capability-backed source picker with manual-import and unsupported states.
- [ ] Add section approvals, justified not-applicable states and final version approval.
- [ ] Bind runs to approved question/protocol versions and enforce matching approval in backend entry points.
- [ ] Add amendment impact review, approval invalidation and version-bound reruns.
- [ ] Export the full protocol contribution, approval, amendment and run history.
- [ ] Test that unapproved/changed inputs cannot launch a main run; AI cannot approve; unsupported sources cannot be passed off as automated retrieval; and reruns preserve earlier results.

Human oversight can clarify decisions and distribute work into manageable sections. Reduced workload or stress is a design objective to evaluate with researchers, not an established outcome.

## Step 4 — Pilot search and researcher review

Status: agreed 2026-10-23, accepting the earlier step-four proposal. Implementation pending.

### Sequence and approval boundary

Step-three approval authorizes the bounded pilot using the approved draft search strategy. It does not immediately authorize the full main search. This clarifies the earlier step-three wording about unlocking a main run: the main-run gate also requires step-four approval of the pilot-reviewed strategy.

The software may suggest search terms, translate syntax for supported databases and execute the pilot. Show the researcher/reviewer the exact queries, sources, execution dates, publication filters, retrieval limits, sample results and any failures or truncation. A small pilot does not establish comprehensive coverage.

The researcher reviews whether the results fit the approved question and scope, edits the strategy if necessary, and explicitly approves the exact strategy version for the full search. Changes retain their provenance and amendment history; affected step-three approvals must be renewed. The software must not silently broaden or narrow eligibility criteria to improve result counts.

Imported libraries use a corresponding preview and acceptance route: show detected format, record counts, missing fields and proposed repairs before accepting the import. Import acceptance does not establish that the software executed or validated the original external search.

### Implementation backlog — pending

- [ ] Distinguish pilot authorization from full-search authorization in the interface and backend.
- [ ] Bind each bounded pilot to its approved question/protocol/search configuration and retain the executed settings and diagnostics.
- [ ] Provide a pilot review screen showing sample results, queries, filters, limits and failures.
- [ ] Record researcher feedback, strategy revisions and explicit full-search approval for the reviewed version.
- [ ] Reject main runs whose strategy differs from the approved pilot-reviewed version; preserve earlier pilot runs when repeating the pilot.
- [ ] Provide an import-preview acceptance route without representing imports as executed searches.
- [ ] Test that pilot completion alone cannot authorize the full search and that changes cannot bypass renewed approval.

## Step 4 alternative — Import an existing PDF collection

Status: agreed 2026-10-23; implementation pending. Researchers may bypass software-executed searching, not subsequent review stages.

Offer automated search, import existing references/PDFs, or combine both. Support multi-file PDF selection; offer folder selection where the browser supports it, with multi-file selection as the fallback. Show progress, per-file outcomes and actionable failures without silently dropping documents. Batch-size limits and processing behavior need explicit implementation design.

Preserve original documents and hashes. Extract candidate title, authors, year, DOI and available abstract; show uncertain or missing metadata for human correction. An absent abstract must not be presented as an abstract generated from the paper. Detect unreadable, scanned or password-protected files and explain whether text extraction or OCR is available. No capability should be promised before implementation and testing.

When references are also supplied, suggest PDF-to-reference matches and require confirmation of uncertain matches. Record the collection's source, collection date and any available external search history; allow unknown values. Never invent search dates, queries or coverage. Import acceptance approves intake, not study inclusion. Uploaded PDFs are not consent for external AI transmission.

After intake, apply the same record checks, duplicate review, title/abstract screening, eligibility criteria, full-text assessment, evidence extraction, appraisal and synthesis workflow. Missing abstracts need an explicit review route rather than automatic exclusion. Preserve each original file even when duplicate records are linked or consolidated. Multiple reports about one study are not automatically duplicates.

### Implementation backlog — pending

- [ ] Add PDF multi-file intake and supported-browser folder selection with progress and per-file diagnostics.
- [ ] Preserve file hashes and provenance; extract candidate metadata and support corrections and confirmed reference matches.
- [ ] Provide explicit handling for unavailable abstracts, failed extraction and OCR requirements.
- [ ] Add collection preview/acceptance and optional combined import-plus-search route.
- [ ] Feed accepted intake into the normal review pipeline without auto-inclusion or invented search history.
- [ ] Validate against the private root `Papers/` collection and synthetic edge cases; document practical errors and outcomes.

The root `Papers/` sample collection contains 11 PDF-named files as inspected on 2026-10-23. Its contents have not yet been parsed or validated. It is excluded from Git and source distributions as private practical-test input.

## Cross-stage agreement — Optional AI guidance and human control

Status: agreed 2026-10-23; implementation pending across the workflow.

At each substantive decision stage, offer optional AI guidance using the approved context for that stage. AI may propose, explain ambiguities and help format input, but cannot approve its own output or advance a consequential decision without researcher approval. A manual route must always remain available. AI-enabled preferences may persist, but external requests must be explicit and disclose which research content will be sent; enabling AI does not mean accepting suggestions.

Researchers can accept, edit, reject/remove proposals, or add their own input. Preserve the original input, AI proposals, researcher changes, approval and version lineage. Rejected or removed proposals remain in history but stay out of active approved inputs. Regeneration must not overwrite researcher-approved work. Keep current approved values prominent and history accessible.

Guide researchers with clear field labels, examples, templates, allowed values and immediate actionable validation. Where a framework or source requires particular syntax, explain the requirement before submission and help correct input. AI suggestions must pass the same validation as manual input. Do not force a researcher to use AI to satisfy a format requirement.

Use one meaningful approval per decision section rather than confirmation for every mechanical task. Routine parsing and diagnostics can run automatically with visible outcomes; their completion does not grant scholarly approval. Enforce approval and version checks in backend operations, not merely through interface buttons. Later edits require review of affected downstream approvals and preserve previous runs.

### Implementation backlog — pending

- [ ] Define a shared proposal/edit/approval/history model and reusable stage controls.
- [ ] Add contextual input guidance and validation for supported frameworks and source syntax.
- [ ] Apply AI provenance, consent and human-approval rules consistently to both search and imported-PDF paths.
- [ ] Test manual-only completion, AI failure recovery, approval boundaries and retention of prior approved work.

## Agreed additions — Domain recommendations and supplementary papers

Status: agreed 2026-10-23; implementation pending.

### Domain-aware extraction recommendations

For AI/ML cybersecurity reviews, recommend extraction fields covering dataset provenance, leakage controls, external validation, operational setting, class imbalance, false-alert burden and analyst involvement. These are candidate fields, not mandatory judgments or automatically approved protocol changes. Adapt suggestions to the question: AI alone does not imply a cybersecurity review, and not every cybersecurity study evaluates an ML model.

With AI enabled, it may identify a likely domain and propose suitable fields with explanations. Ask the researcher to confirm or correct that classification. Allow acceptance, editing, removal and researcher-defined additions; record the provenance of the field definitions and their approval.

With AI disabled, provide the same opportunity through curated local domain templates and transparent keyword/rule suggestions or researcher-selected domains. This route must not call a model or send topic text externally. Domain detection is tentative; always permit correction or explicit selection. Missing or unsupported domains retain the general manual extraction editor.

Adding fields after extraction has started creates a framework revision and identifies previously extracted records needing review. Preserve earlier values, definitions and approval history; do not silently declare earlier extraction complete against new requirements.

### Required provenance documentation for external collections

Ask researchers to document how imported papers were assembled, including available database/platform names, exact external strategies, search dates, filters/period, citation searching, personal collection or colleague referral, and any supplied exports/logs. Permit source-level or batch-level documentation with record-specific exceptions. Preserve original supplied descriptions and later corrections.

For informal collections, explicitly record the assembly method. If strategies or dates are unavailable, require an honest unknown/not-recorded declaration rather than fabricated search details. Distinguish externally supplied search documentation from independently verified execution. Acceptance of documentation does not certify comprehensive coverage.

### Subscription papers and additions after searching

Allow researchers to upload papers they have obtained through subscriptions or purchase, alongside open-access papers and imported references. Do not equate a source's open metadata coverage with full-text availability. Access status is distinct from scientific eligibility. Preserve files locally; uploading does not authorize redistribution or external model transmission.

Support adding papers before, during or after a software search. Each addition belongs to an identifiable intake batch with origin, time, metadata, file hash where applicable and researcher-provided acquisition context. Keep this supplementary route available without overwriting prior search runs or their counts.

Run supplementary records through intake validation, duplicate checks and the same applicable title/abstract and full-text eligibility workflow. Do not auto-include a paper because it was manually added. Retain source memberships when duplicate records are consolidated, link multiple reports of one study appropriately, and prevent double counting. Flow-diagram categorisation must reflect the actual identification route, not simply whether a PDF was uploaded.

If additions affect an already completed review, mark dependent screening, extraction, synthesis and exports as requiring an impact review. Preserve previous frozen exports; create a new approved version after the affected work is completed. Existing eligibility criteria apply unless explicitly amended with rationale and renewed approval.

### Implementation backlog — pending

- [ ] Add curated domain templates, tentative domain suggestions and researcher confirmation for manual and AI-assisted routes.
- [ ] Add versioned extraction-field proposals and impact checks for later framework changes.
- [ ] Capture external search/assembly documentation, including explicit unknown declarations.
- [ ] Support subscription-PDF intake and supplementary intake batches after searches.
- [ ] Preserve mixed-source provenance, duplicate accounting and record/report/study distinctions.
- [ ] Reopen affected work after late additions and produce versioned updated outputs.
- [ ] Test that manual mode makes no model calls, domain suggestions never auto-approve fields, and supplementary papers cannot bypass screening.

## Next discussion — Step 5

Review retrieved records, coverage and duplicate-handling guardrails.

## Methodological comparison — 2026-10-23

This comparison consolidates the eleven-stage proposal against established guidance. It does not mark the remaining stages or these additional recommendations as agreed or implemented. PRISMA is a reporting guideline, not a certificate of methodological quality. Cochrane guidance primarily addresses intervention reviews; apply relevant principles without imposing clinical-only frameworks on cybersecurity or education reviews.

| Stage | Consolidated workflow | Methodological addition or clarification |
| --- | --- | --- |
| 1. Entry | Choose review type, team, purpose and input route. | Distinguish systematic review, scoping review and bibliometric analysis; select suitable methods rather than promise a universal template. |
| 2. Question | Manual drafting, optional AI refinement or AI-generated candidates; researcher approves an exact version. | Choose a question framework appropriate to the discipline and review type. Clear questions do not alone establish feasible methods. |
| 3. Protocol | Approve eligibility, sources, queries, screening, extraction, appraisal and synthesis plans. | Make the protocol available prospectively, register where appropriate, justify restrictions and record amendments. If work already began, disclose that timing rather than imply prospective planning. |
| 4. Acquisition | Approved pilot then main search, or accepted imported references/PDF collection, or both. | Review search sensitivity as well as apparent relevance; consider information-specialist review. Include appropriate external searches, citation searching and grey literature as needed. A convenience PDF collection does not establish systematic search coverage. |
| 5. Records | Inspect coverage, failures and duplicates; preserve provenance and reversible decisions. | Distinguish duplicate records from separate reports of the same study; link reports to studies. Counts must distinguish records, reports and studies. |
| 6. Initial screening | Calibrate title/abstract criteria, record independent votes and resolve disagreements. | Recommend two human reviewers; disclose departures. AI does not count as an independent second human. Avoid revealing AI judgments before independent votes by default to limit anchoring. |
| 7. Full-text eligibility | Confirm correct documents, apply criteria and record exclusion reasons. | Support independent dual assessment of final eligibility, resolution and explicit reports-not-retrieved/awaiting-assessment states. Lack of free access should not silently become scientific ineligibility. |
| 8. Extraction and appraisal | Pilot forms, preserve source anchors, review proposals and resolve disagreements. | Use study-design-appropriate appraisal; independently duplicate critical outcome extraction or apply the checking procedure required by the chosen method. Citation counts, venue quartiles and AI confidence are not risk-of-bias judgments. |
| 9. Synthesis | Human-approved grouping, analysis and interpretation based on accepted evidence. | Address heterogeneity, incompatible metrics, missing results, reporting bias, sensitivity and certainty where applicable. Meta-analysis and GRADE are not universally appropriate; state and justify the selected method. |
| 10. Reporting | Generate traceable methods drafts, evidence tables, flow counts and AI-use history. | Use the applicable PRISMA checklist/extensions; report limitations, protocol deviations, funding and conflicts. Bibliometrics complement rather than replace substantive synthesis. |
| 11. Final review | Human sign-off on a frozen export with unresolved work visible. | Assess search currency, screen any update results, and retain a reproducible versioned package. Separate approval, completeness and methodological quality. Share original PDFs only where permitted. |

### Additional candidate tasks from the comparison

- [ ] Support review-type-specific guidance and method profiles.
- [ ] Record prospective protocol availability/registration or honest retrospective timing.
- [ ] Add search-coverage assessment, justified restrictions, citation-search provenance and update-search tracking.
- [ ] Support independent reviewer assessment without implying AI is a second human reviewer.
- [ ] Distinguish journal metrics, appraisal judgments and body-of-evidence certainty.
- [ ] Add synthesis-method justification, limitations and reporting-bias considerations.
- [ ] Present approval, workflow completeness and methodological quality separately.

### Primary guidance consulted

- [PRISMA 2020 statement](https://www.bmj.com/content/372/bmj.n71.long): reporting guidance and its limits as a quality assessment tool.
- [PRISMA-P](https://www.prisma-statement.org/protocols): protocol reporting.
- [PRISMA-S](https://www.prisma-statement.org/prisma-search): literature-search reporting.
- [Cochrane Handbook, Chapter 4](https://www.cochrane.org/authors/handbooks-and-manuals/handbook/current/chapter-04): searching, selection and report/study distinctions.
- [Cochrane Handbook, Chapter 5](https://www.cochrane.org/authors/handbooks-and-manuals/handbook/current/chapter-05): structured data collection and extraction.
- [Cochrane Handbook, Chapter 14](https://www.cochrane.org/authors/handbooks-and-manuals/handbook/current/chapter-14): certainty of evidence for intervention outcomes.
- [JBI Manual for Evidence Synthesis](https://jbi-global-wiki.refined.site/space/MANUAL/): methodologies for different evidence-synthesis types.


## Analysis knowledge base — implementation increment, 2026-10-23

The researcher authorised a source-backed ontology/knowledge base for cross-disciplinary question-to-analysis recommendations. Initial implemented service: `slr knowledge init/catalogue/recommend`, dedicated SQLite graph, 32 method/display options and 13 source records. Matching rules remain local unvalidated hypotheses, not published facts. All execution adapters are marked not integrated, all recommendations remain unapproved, and no screening/evidence ledger is modified. See `Docs/Analysis_Knowledge_Guide.md` for source limitations, CLI examples and the validation backlog. Full dashboard/extraction binding, richer question profiles, expert validation, formulas and analysis execution remain pending. No other users' conversations are available or used as evidence.

## Book-informed proposals — 2026-10-23

See `Docs/Book_Design_Review.md` for a review of the user-supplied textbook extract. Candidate additions include a purpose/audience/resource brief, review profiles, mixed-method strands, typed methodological sources, contextual teaching support and question-to-claim coverage. These are proposals for consideration, not new agreed requirements. Only the front matter, introductory chapter and references are present in the supplied 113-page PDF; later chapters listed in its contents have not been reviewed.

## Additional supplied documents — 2026-10-23

See `Docs/Additional_Document_Design_Review.md` for the eHealth methods chapter and Industry 4.0 review example. Further proposals concern iterative workflows, source conflicts, objective-to-field links, conflicting counts, acquisition limits, date policies, attribution of method mentions and origins of figures. The engineering review is now a development case, not unseen validation data. No new methods or source assertions have been automatically promoted into the knowledge database.

The Lamé introduction and Metaverse definition review were also inspected. A consolidated register in `Docs/Literature_Informed_Action_Backlog.md` now contains LIT-01 through LIT-14 with priorities, suggested future ownership, dependencies and acceptance criteria. Suggested ownership has not dispatched work. These documents are development material and remain separate from the forthcoming held-out review sample. Later additions remain proposals unless already agreed elsewhere in this plan.

Further reading: Pollock/Berge and Chigbu et al. reviewed locally on 2026-10-23. The action register now includes LIT-15–18 for stakeholder relevance, result-selection rules, evidence-linked gaps and search/extraction semantics. Claim-level concerns remain pending curation; no knowledge rules automatically changed.

## Implementation update — 2026-10-24: topic/question workspace

Step 2 now has a dashboard workspace (`Topic & questions`) backed by `slr.questions`: manual/topic-only drafts, built-in versioned generation/refinement instructions, explicit stage opt-in, provider/model-bound cloud consent, individual proposal accept/edit/reject, final human approval and downloadable contribution history. AI response arrival does not alter the draft or approval. Subsequent draft changes require renewed approval. Request input, rationale, provider/model, output, actor labels and timestamps remain inspectable. Imported/search-replaced corpora carry forward this review-level history.

Candidate question acceptance explicitly offers add or replace; replaced wording remains in history. Researchers can also edit/remove earlier wording before final approval. The original request and candidate are shown side by side; word-level diff highlighting remains a follow-up. Existing review name/question values are offered as a starting draft and are not automatically approved. Online literature exploration is not implemented in this stage: generation/refinement has no browsing tools and must not claim novelty verification. Exact protocol/pilot/main-search dependency gates remain pending; this is not a claim that step 3 or step 4 is enforced.

Prompt contracts live in application code and are sent automatically with the saved researcher input; users need not write prompts. The current provider selection remains usable while the final embedded/custom-model interface is discussed. No fine-tuning or arbitrary-model installer was introduced.

Reviewer follow-up RC-R4 is specified in `platform_enhancement_plan.md`, section 9.


## Implementation update — 2026-10-24: guided protocol and pilot increment

The dashboard now implements the seven-section editor over the existing protocol ledger, individual approvals and justified N/A for extraction/appraisal/synthesis, and a separate exact-version final approval. Approval checks include the question approval and criteria actually shown to the actor. A changed draft never gains approval by saving or accepting an AI proposal. Changed eligibility is synchronized to an appended screening-criteria version; earlier screening decisions remain historical.

Protocol approval authorizes a bounded pilot. Pilot runs are separate from the captured corpus, expose query/source/date/limit diagnostics and sample records, and require a recorded researcher strategy review before a main search. The dashboard main registration path refuses unbound live runs, checks authorization before and during retrieval and again before registration, and preserves question/protocol/plan/criteria history across corpus replacement. Existing/imported corpora remain accessible with explicit provenance labels.

The built-in per-section AI contract is `protocol-section-v3`, using native typed replacement values. Section input is treated as data; no browsing/novelty claims are permitted. Dates are entered manually. Provider/model/hash identity, stage opt-in, cloud consent, allowed fields, type checks, individual decisions, unchanged-value handling and failure records are implemented. Actual local Llama validation used synthetic input; it does not establish the suitability of proposed methods.

Remaining: CLI approval-management parity; governed reruns/combined intake for an existing nonempty corpus; source-backed online exploration; PDF collection intake; word-level diffs; native-platform acceptance tests and broader cross-domain/model validation. These updates supersede earlier pending-status descriptions only for the implemented dashboard scope. The seven approvals do not replace full PRISMA-P reporting or methodological review. Reviewer IDs are now RC-PROTOCOL-1 (this increment) and RC-PROTOCOL-2 (CLI/acceptance follow-up), avoiding the older RC-R4 topic-exploration ID collision.

## Implementation update — CLI parity, 2026-10-24

The next increment adds `slr review create`, `slr questions` and `slr plan` so a review can exist, be drafted and approved before retrieval. Plan actions bind to an inspected context file rather than silently reading newer approval identities. Pilots remain separate; CLI pilot inspection verifies recorded artifacts before human strategy review. Main searches register transactionally into the same empty ledger, preserving identity and every prior history.

Standalone live CLI commands now require `--unregistered` and remain unbound. `slr review init` refuses live/unregistered/approved snapshots that bypass or discard the governed history. Existing databases and imported external libraries remain accessible and explicitly unverified; stricter intake screening requirements are still a separate migration decision. Low-level Python retrieval functions remain unbound utilities. Native-platform hard-link publication and governed nonempty-corpus reruns remain validation/design work.

The independent reviewer proposal was reconciled in enhancement-plan section 10, including D1–D6, the RC-R4 ID collision, and two reproduced importer findings assigned for repair before integration. See the Protocol Guide for command examples.
