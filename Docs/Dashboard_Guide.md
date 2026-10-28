# LitAtlas dashboard (0.6.0)

LitAtlas puts the repository's retrieval, screening, bibliometrics and evidence workflows in a modern local interface. The interface calls the same Python services as the CLI; it does not replace their validation rules.

## Start

```bash
python -m pip install -e .
slr dashboard --workspace outputs/dashboard --demo
```

Visit [http://127.0.0.1:8765](http://127.0.0.1:8765). No Node build, CDN, external fonts or JavaScript runtime installation is required. The core dashboard uses the Python standard library and browser-native HTML/CSS/JavaScript. Stop it with `Ctrl+C`. Choose another local port with `--port 8766` if needed.

`--demo` seeds an **empty** workspace with two explicitly synthetic examples: an in-progress screening review and a completed screening review with evidence proposals. It never overwrites a nonempty workspace. The fixed fictional records, citation counts and source texts are not research evidence. Use **New review** to create your own protocol; the demo banner disappears for real reviews.

## Views

### Overview

Four cards summarize gathered records (before deduplication), resolved title screening, included reports/studies and reviewed evidence fields. The workflow row opens the corresponding view. Publication bars use known years; clicking one filters the library. Metadata coverage counts reports with at least one author, keyword or usable metadata list, not completeness of those data. Latest activity comes from actual saved events, not generated trend claims.

A finished screening pass is not an exhaustive literature search. The protocol view identifies capped retrievals; source coverage still needs methodological review.

### Study library

Search titles, abstracts, DOI, authors and keywords. Filter by source, year or decision; sort by year, known citation count or title. Switch table/cards and open a source detail drawer. The CSV export covers the current filtered result set, not just the displayed page, and neutralizes spreadsheet formula prefixes. JSON/bibliographic exports in the ZIP preserve the source data through the existing export helpers.

**Import literature** accepts CSV, RIS or normalized JSON, up to ten files and 5 MB aggregate in the UI (8 MB server request cap). Public-database search is available in the import dialog for an empty review. Query syntax, provider access, rate limits and coverage limitations follow the CLI adapters; OpenAlex pagination may require `OPENALEX_API_KEY` in the server environment.

Imports into a workspace-created review append the previous retrieved metadata before DOI deduplication. Once any screening decision exists, imports/retrieval replacement are blocked. Create another review and combine the earlier `retrieved.json` with new inputs if the corpus changes. Connected CLI ledgers without their original retrieval folder cannot append new metadata through this UI; importing just retained records cannot reconstruct earlier duplicate counts.

Failed imports/searches leave the current ledger selected and unchanged. Stale tabs must reload when a replacement corpus has a new ledger identity, even if the new criteria version is also 1. Original run/ledger artifacts remain on disk for inspection.

### Screening

Choose a reviewer label to open that reviewer's independent queue. The queue endpoint omits the other reviewer's votes. The administrative overview still shows consensus status and aggregate activity; this is a trusted shared-machine workflow, not authenticated blinding.

Include/exclude title/abstract or full-text records. Exclusions need a primary reason. Conflicts and mismatched exclusion reasons require the assigned third reviewer and an adjudication rationale. Full-text eligibility requires title inclusion and a recorded successful retrieval. The **Retrieval** tab records retrieved/not retrieved (with a reason for the latter); it does not download an article. **Study links** requires the adjudicator and maps included reports to study IDs.

Keyboard `I`/`E` activates include/exclude in an independent queue when no text field/dialog is focused. Criteria versions are submitted with every action; stale decisions are rejected by the existing service.

### Bibliometrics

Explore all captured reports or the current included subset. Switch co-authorship, keywords, co-citation and bibliographic coupling; choose cosine or raw weights and frequency/raw-edge thresholds. Node inspection exposes actual frequency, retained degree, total link weight and strongest connections. Pan, scroll/zoom, and reset the map.

The live map displays up to 70 high-strength nodes (42 in the overview); graph JSON downloads retain every node/edge and the calculation methods/coverage. The grouped exploratory layout does not make geometric distances meaningful. Colors identify label-propagation groups; the eight-color UI palette repeats. This is not a VOSviewer map, topic-model output or a claim of a research gap. Use `slr analyze --figures` for the package's reproducible SVG/PNG exports.

### Evidence studio

Select a completed screening review, then start an evidence ledger with the default or an uploaded framework. The default shipped extraction/appraisal framework is illustrative, not a validated risk-of-bias instrument. A ledger is available only when there are included, study-linked reports.

Attach UTF-8 source text as full text, abstract or excerpt; form-feed separators define supplied pages. Add extraction/appraisal proposals with field/domain, value or explicit not-reported status, source/page/quote, uncertainty and rationale. Proposals remain pending. The inspector highlights matching source text and shows grounding flags. Quotes establish literal occurrence; the reviewer must confirm semantic support and context.

Manual proposals require approval by an actor other than their author. AI proposals can be reviewed by any assigned reviewer. Approvals need a rationale and explicit support confirmation. Unsupported items cannot be approved. Rejections and later replacements append review history; another approved item in the same field/domain must be rejected before replacement. Revision checks reject racing updates.

**Prepare AI request** saves and downloads a packet; it does not make a model call. **Import model response** validates the saved request/hash, schema, provenance and anchors and creates pending proposals. Hosted model calls remain an explicit `slr evidence run-ai` CLI operation using server-side environment credentials, never a browser field. No API key is returned in dashboard JSON.

New criteria make existing evidence ledgers historical. Their history remains readable, but writes are blocked. Create a fresh evidence ledger through the CLI and reconnect the matching current pair when starting a new evidence pass. In this release, an existing registered evidence ledger is not replaced from the UI.

### Review protocol

Inspect the research question, saved criteria, reviewer responsibilities, capture mode and retrieval limits. Revising criteria preserves the earlier history and starts a fresh screening pass; it does not silently carry earlier votes or evidence approvals forward.

## Existing reviews and persistence

```bash
slr dashboard --workspace outputs/my-workspace \
  --review-db outputs/evidence-example/screening/review.sqlite \
  --evidence-db outputs/evidence-example/evidence.sqlite
```

Evidence must belong to that screening review. A registry in `workspace.json` remembers connected ledgers by local path. Workspace-created runs, ledgers, sources and export folders live beneath the selected workspace. Connected CLI ledgers stay in their original locations; UI decisions update those ledgers. Close the application before moving/copying an entire workspace. Absolute connections and frozen evidence scope paths must remain available to reopen the same active scope.

Multi-line searches run through the application pipeline and expose downloadable, timestamped Markdown session logs. See [Pipeline_Guide.md](Pipeline_Guide.md). Job history persists in `jobs.json`; interrupted jobs are marked failed on restart. Retrieval jobs run in a bounded thread pool within the server process. The UI polls their actual status and reattaches to running jobs after a browser reload while the same server is alive. Jobs do not resume after a server restart. A currently running network request may finish before the Python process exits. Completed retrievals are registered only after success; a failed/interrupted attempt does not replace the selected corpus.

**Export review/evidence** downloads a ZIP with screening CSV/JSON, included bibliography formats, PRISMA output and any evidence snapshots/source text. This can include private source passages; it is a deliberate local download, not publication. Existing artifact manifests travel with the bundle.

## Keyboard and accessibility

- `Ctrl/Cmd+K`: command palette for views and study lookup.
- `Escape`: close a study drawer or dialog.
- `I` / `E`: independent screening actions when not editing text.
- Tab/Enter: navigation, controls and selectable network nodes.
- Theme toggle: light/dark preference stored locally; no research data is cached in local storage.

Responsive navigation, a skip link, focus indicators, drawer focus containment and reduced-motion styles are included. The browser check covers a 390-pixel-wide viewport and verifies no document-level horizontal overflow.

## Local request boundary

The server binds only to `127.0.0.1`, checks Host and Origin, requires an ephemeral per-process header token for data/mutation routes, sends no wildcard CORS header, and includes a restrictive content policy. Data access is limited to workspace registry entries explicitly created or connected at startup; there is no HTTP route for arbitrary filesystem paths or arbitrary model endpoints. Reload the page after restarting the server to obtain the new session token.

This is not a production authentication system or a hosted multi-user service. Reviewer labels coordinate a trusted local team. The code does not deploy the dashboard, publish private research data, add external analytics, or expose environment credentials to the browser.

## Verification

```bash
python -m pip install -e '.[dev]'
python -m pytest
python -m build

# Optional browser QA (isolated temporary workspace):
python -m pip install -e '.[ui-test]'
python -m playwright install chromium
python Scripts/check_dashboard_browser.py --output outputs/dashboard-qa
```

On Linux, install the browser's documented system dependencies if they are not already available. The browser check exercises navigation, filters, study drawer, map inspection/zoom, conflict resolution, independent evidence approval, grounding blocks, ZIP/CSV downloads, command palette, theme, new review/import, screening, and mobile navigation. It uses synthetic data, makes no public-database or model requests, and writes screenshots to the requested QA directory. The ordinary test suite additionally checks local request controls, stale ledgers, corpus persistence and atomic retrieval completion/failure.

### Research analytics

The **Research analytics** view adds eight corpus summary measures and publication-venue rankings. Choose all captured reports or the included subset, search venues, import a dated metric CSV, and select metric year/category. Imported CiteScore/SNIP/SJR/quartiles/source H-indices remain separate from corpus TP counts. Export complete ranked tables and input/provenance snapshots. See [Corpus_Analytics_Guide.md](Corpus_Analytics_Guide.md) for definitions, metadata coverage, CSV schema and missing-value handling.

## Guided AI setup

Open **Settings** from the sidebar, including before creating your first review. Choose **Local · open models** or **Cloud · API providers**. AI is optional and starts off.

For local use, Settings reads the app host’s currently available RAM, CPU threads and free storage, respecting a Linux memory-container limit when reported. It filters a small curated catalogue to models that meet conservative estimates, marks a recommended fit, and explains excluded choices. The estimate reserves storage for the runtime, model and headroom; it is not a speed or research-quality benchmark. GPU capacity is not measured. Smaller Llama, Qwen and Gemma models have different licenses; the model link shows the relevant details.

Select a model, review its license, then click **Download and set up selected model**. The app downloads the official portable Ollama runtime, verifies the archive SHA-256 published by its release API, installs it within the private workspace, starts a loopback service with cloud functionality disabled, downloads the model and tests a sample structured response. Progress is shown per stage. Internet access is needed for downloads; local inference then needs no API key. Resource availability is checked again on the server before setup. No administrator installation or shell commands are required. Turn AI off to cancel a pending setup; interrupted downloads can be retried.

Automatic portable setup handles Linux/Windows x64 and ARM64 where an official archive exists, and macOS archives. Linux x64 is the platform used for the practical validation; Windows/macOS require native acceptance testing before claiming equivalent coverage. Storage and CPU-generation time can be substantial. Setup fails visibly when an archive, digest or model is unavailable; it never silently switches to a cloud provider.

For cloud use, choose one of five providers: OpenAI, Anthropic, Google, Mistral or DeepSeek. Follow its API-key link, paste a key in the password field and check available text models. Choose a returned model and save it. Keys stay in server memory by default; the optional Remember checkbox uses a supported operating-system credential store and explicitly falls back to session-only storage if unavailable. Keys are never written to workspace settings, returned in API responses or included in review exports. Use Forget to remove a provider’s key. An ordinary chat-app subscription may not include API access. **Test selected model** submits only a synthetic sample and may incur an API charge. Provider adapters have offline contract tests; access to any specific model still depends on the provider account.

In Evidence Studio, prepare and inspect a saved request, then choose **Run selected AI**. A cloud run asks for explicit consent to send that packet’s source text. Local runs use the configured local model. Generation is a background job; imported proposals remain pending human review and pass the existing evidence validation. Changing settings does not approve research decisions. Keep raw model outputs and check any ungrounded or incomplete suggestions.

Private setup data, runtime files, model weights and connection-check records live in `.litatlas-ai/` inside the selected workspace. This folder is ignored by Git and excluded from release archives and review exports. Keep enough disk space for large downloads.

Local source-generation requests use a bounded 8192-token context and a conservative input-size check, with up to 1024 output tokens. Oversized source packets are rejected with guidance to use shorter sections or a cloud model; automatic full-paper chunking is not implemented. Question-only setup/experiment requests use a 4096-token context unless otherwise recorded. A successful connection/JSON test establishes connectivity and format only, not research accuracy.

## Topic and research questions

Open **Topic & questions** in a review. Enter a topic and one question per line; a topic-only draft is allowed before question generation. Save the draft, then optionally enable AI for a generation/refinement request. LitAtlas supplies versioned instructions; only the saved topic/questions accompany those instructions. Cloud requests require consent for the displayed provider/model. This action does not browse online or verify novelty.

Review suggestions individually: accept lets you add a candidate question or replace an existing question, use edited wording records your revision, and reject retains the proposal only in history. Edit/remove earlier questions in the draft editor as needed. A separate **Approve topic and research questions** action approves the saved version; edited drafts require approval again. Local actor names are labels, not authenticated identities.

Download the revision/AI-use JSON record for original submissions, request/response provenance, decisions and approvals. Verify its disclosure wording before use. The full review ZIP also includes this record. Continue to **Review protocol** for the guided protocol, section approvals, bounded pilot and human-reviewed main-search flow.


## Guided protocol, pilot and main search

The **Review protocol** page now provides seven editable sections, section approvals and a separate final version approval. It carries forward the approved topic/questions. Dates are researcher-entered; source choices reflect actual retrieval capabilities. Manual sources are documented separately. Saving changed eligibility starts a new criteria version and screening pass, retaining earlier decisions.

Run a bounded pilot after final approval, inspect its sample and source diagnostics, and record your strategy decision. A pilot never fills the study library. Main search requires current approvals and an approved pilot strategy; the old direct-search dialog now leads here. Changing questions, criteria or protocol while a run is active can invalidate registration. Existing nonempty corpora are preserved.

AI remains optional and off for each section request until explicitly enabled there. LitAtlas supplies the prompt; local requests use the installed model. The UI discloses cloud transmission when that mode is selected. Model suggestions never approve a protocol. See [Protocol Guide](Protocol_Guide.md) for version/history, exceptions and CLI scope.

For observed local-model failures, recovery advice and outstanding safeguards, see [LLM guardrails and lessons](LLM_Guardrails_and_Lessons.md). Connection success, resource fit, valid JSON and human approval each establish different things; none by itself certifies research quality.


### Guided next steps

Each review stage now includes a next-step card. After approving the current topic/questions, use **Next: Review protocol**; unsaved edits block that link, and saving a changed draft requires fresh approval. Protocol approval points to the bounded pilot/search controls, with an alternative to import existing papers. Captured papers lead to screening; completed screening and study linking lead to evidence extraction/appraisal; completed evidence review leads to results/reporting and the verification-bundle export. A review with no included reports leads to reporting its empty result.

Incomplete stages explain what remains and keep the later next action disabled. The sidebar stays available for revisiting stages and exploratory views. Navigation does not approve decisions, execute AI, run searches or certify a completed scientific synthesis. Results charts describe the captured metadata; authors still verify reporting and evidence.


### Background AI activity

An animated **AI is working…** region appears immediately for topic/question, protocol-section and evidence AI requests. It remains outside the current page while you navigate, identifies the task/model, and offers **View task**. Running requests for the same review are blocked in both the UI and backend; other reviews remain independent. Model installation/download has its separate Settings progress view.

The animation stops when the server records completion or failure. Successful requests show **Suggestions ready — review them** and open the correct stage; current-stage suggestions refresh automatically only when there are no unsaved draft edits or open modal. Otherwise use **Show suggestions** after saving your work. Failed requests show the recorded error and **Review and retry**; this opens the task and does not automatically call the model or resend data. Existing consent and provider/model checks still apply to every retry. No percentage or completion time is invented. If polling loses connection, the last known running status is labelled as uncertain while the app rechecks. Completion never means researcher approval.


### Protocol AI prerequisites and required fields

An approved question set opens an initially unsaved protocol (v0). AI section suggestions require a saved draft, which binds each request to the exact version. Use **Save initial draft to enable AI**; incomplete fields are allowed at this point. This action saves a draft only, never approves it or calls a model. If AI is off, the page links to Settings and labels the action **Save initial protocol draft** for manual work. The visible explanation distinguishes missing question approval, first save and AI configuration.

Red asterisks mark requirements for approval, not requirements for saving an incomplete draft or requesting suggestions. Optional fields are labelled; source query/limit markers apply only to selected automated sources. Synthesis requires its comparison criterion and at least one of the two method fields. Extraction, appraisal and synthesis may use the existing explicit not-applicable rationale path. Dates still require the researcher's own input. Topic and question labels similarly distinguish topic required for saving from questions required for approval.


### Complete the protocol section by section

Use the protocol's drafting navigator to work on sections in any order; this only scrolls the page. Each section lists missing input and provides **Save section edits** (which uses the shared versioned draft/amendment save) and an approval-dependent **Next** action. With an existing draft, give the amendment rationale in the save panel before saving changes. Unsaved edits disable section continuation and final approval. Reverting those edits restores the saved-state controls.

The progress count reports current section approvals, not methodological quality. Eligibility, source and search approvals also check the common executable search plan and publication period; draft these connected fields before approving them. After all seven sections are current, the last section leads to the separate final approval panel. Final approval permits only the bounded pilot; pilot strategy review and main-search authorization remain distinct decisions. An input-presence message is not proof that provider syntax or a study-design choice is correct.


### Verify an exported review in the dashboard

Open **Verify a review** in the sidebar; no active review is required. Choose the ZIP from Export review and click **Verify bundle**. The viewer uses the same verifier as the CLI and shows each integrity/replay check, the manifest fingerprint, software versions and explicit limits. Download the result JSON if needed. Tampered bundles show failed checks; malformed uploads show an error and remove stale results. Verification does not import papers, approve a review, call AI or establish scientific validity.

Uploads stay with the local application and temporary files are removed after checking. The viewer allows 64 MiB compressed / 128 MiB expanded; use the CLI for larger bundles. The server retains its localhost/session-token protections. Results remain in the page's memory until cleared or the app page closes; this is not a public upload or telemetry service.


### Record framework-guided question reasoning

The optional framework section in **Topic & questions** supports an initial PICO/PCC/SPIDER catalog and a documented custom/no-listed-framework-fits path. Choose per question, read the purpose/source/limitations, explain your choice, and record component notes as identified, unclear, not applicable or unreviewed. These are researcher statements, not automated scientific grades. The initial catalog is awaiting independent design review; it is not exhaustive.

Save reasoning as a new question draft, then explicitly approve it. The previous wording, maps and approvals remain in history. Save draft can also save combined wording and edited maps; changing wording without resaving maps clears current maps conservatively. All mappings include exact question hashes and source metadata, and appear in question disclosure/verification bundles. Unmapped legacy work is not retrospectively assessed. Manual use requires no AI setup.

Framework-aware AI refinement and keyword/concept mapping are not included in this increment. Generic AI still receives saved topic/questions only; accepted AI wording can be mapped manually using the same controls. Framework choices do not certify novelty, relevance, scientific quality or search completeness.


### Pilot availability and authoritative eligibility amendments

Pilot strategy review now rechecks that the run started through the governed pipeline and that its manifest, artifacts and authorization still match. Deleted or altered pilot results appear as unavailable without preventing protocol-page access; authorize a new pilot if necessary. Earlier ledger events remain unchanged.

After saving a guided protocol, amend screening criteria through Review protocol's eligibility fields and save with an amendment rationale. Direct criteria edits are refused across services/CLI/dashboard to prevent drift or silent reversion. Criteria version replacements and their effects are recorded in history. Legacy reviews without a guided protocol keep their previous direct revision path.

### Framework reasoning records

In Topic and questions, select a guide per question or document a custom/no-fit choice. For each identified component choose literal question support (paste an exact quote) or researcher-added context. A quote check verifies that the words occur, not that the interpretation is correct. Missing and unclear components remain visible; no scientific quality score is assigned. Custom structures support up to eight component names: click Apply component names before saving.

Saving reasoning creates a new draft requiring explicit approval. Wording changes clear all current mappings unless revised mappings are saved with the wording. Approved mappings appear in Review protocol; changing them requires saving a protocol amendment to synchronize that version. Mixed-framework reviews retain each question's own guide. Legacy records are not retrospectively assessed. Verification bundles preserve guidance versions, support types, decisions and unresolved states. Keyword/concept mapping is a later phase.

### Easier protocol entry and saving

Use one inclusion/exclusion rule per line, beginning with `Include:` or `Exclude:`. Existing prose remains editable. Under report eligibility, choose languages and publication types, click **Add selection**, and remove choices with their × buttons. **Other** accepts a custom value. No restrictions are assumed: choose **No language restrictions** or **Any publication type** when that is your plan. Specify additional report exclusions separately. The controls populate the editable report-eligibility text; existing researcher-written text is preserved. These are eligibility instructions, not automatically applied retrieval filters.

Enter keywords on separate lines or separate them with semicolons. Each database-query line is a complete query and runs separately. Keywords and the source/term rationale document the strategy; they do not automatically generate executable queries.

The extraction-field picker offers general fields and optional subject groups. Topic wording can suggest which group to browse; this is a simple text cue, not AI or a methodological assessment. Click fields to add them, remove unwanted fields, or add a custom field. The resulting protocol list stays editable, one field per line. Confirm the actual extraction form before collecting evidence.

**Save draft edits** saves all edited sections on the page. The first save may be incomplete and enables section AI suggestions if a model is configured. Later saves ask for an amendment reason in a dialog if you have not already entered one. A saving indicator and saved version confirm the action; an unchanged draft reports that nothing needs saving. Save errors retain edits. Saving does not approve any section or call AI; request optional AI suggestions separately, then review the response.
