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
