# Implementation roadmap

## Delivered: reproducible search foundation

- Installable standard-library Python package and command-line interface.
- OpenAlex and Crossref adapters with cursor paging, throttling, bounded retries, and date filters.
- Shared metadata, normalized DOIs, conservative deduplication, and retained source provenance.
- JSON, CSV, BibTeX and RIS exports, identification counts, and yearly publication summaries.
- TOML review configuration, raw response retention, UTC search manifests and artifact hashes.
- Offline synthetic demonstration, automated unit/integration tests and CI.
- Accurate file paths, GPL licensing statements and separation of external research tools.

## Delivered: screening and eligibility (0.2.0)

- SQLite review ledger with stable record IDs and append-only events.
- Two named reviewers, a separate adjudicator, reviewer-specific queues, explicit retrieval status, full-text decisions and primary exclusion reasons.
- Criteria snapshots, hashes and version checks; a revision preserves history and starts a new screening pass.
- Study IDs linking multiple included reports to one study.
- Derived counts and an original PRISMA 2020-style SVG for new database/register-only reviews, with pending and conflict counts.
- Administrative CSV/JSON history and included-report exports with artifact hashes.
- UTF-8 CSV/RIS/normalized JSON imports with preserved input files and provenance.
- PubMed ESearch/EFetch, date filters, query translation, raw XML and bounded batch retrieval.

Scope: this is a local CLI workflow; identities are labels rather than authenticated accounts. It does not implement updated-review or other-methods PRISMA branches, or automate full-text downloads. Counts describe the imported/retrieved snapshot, not search exhaustiveness.

## Delivered: bibliometric analysis (0.3.0)

- Core `slr analyze` CLI for verified retrieval/import runs, screening-included reports, and explicit standalone JSON.
- Author IDs, keywords, resolved reference IDs and optional provider-reported reference totals across metadata adapters/imports; compatibility with earlier normalized snapshots.
- Binary report incidence and full-count co-authorship, keyword co-occurrence, co-citation and bibliographic coupling.
- Configurable frequency/raw-edge thresholds; raw counts or cosine weights; deterministic weighted label propagation with convergence reporting.
- Namespace-aware reference matching using explicit corpus identities; unresolved entries and missing metadata remain visible.
- JSON, CSV and GraphML network exports; document IDs, coverage, methods, input snapshots, duplicate logs and artifact hashes.
- Publication trends, observed keyword-by-year frequency and provider-specific citation summaries.
- Optional Matplotlib SVG/PNG figures, a local HTML report and an explicit display-node cap that does not truncate exported graph data.
- Synthetic fixture tests with hand-calculated graph weights, missingness and backwards compatibility.

Scope: report-level analysis, full counting, conservative identity matching, simple deterministic communities. It does not infer research gaps, implement VOSviewer algorithms, calculate field/age-normalized citation impact, or equate missing reference lists with zero scholarly references.

## Delivered: evidence and AI assistance (0.4.0)

- Versioned, immutable extraction fields and configurable appraisal domains with no invented aggregate score.
- SQLite evidence ledger bound to a completed screening snapshot, included reports and study IDs.
- Plain-text source snapshots, source hashes, supplied-page anchors and exact quote/character checks.
- Manual and model proposals with uncertainty, rationale, producer/model metadata, prompt hashes and pending human review.
- Explicit review confirmation, optimistic review revisions, rejection/replacement history and rejection of ungrounded approvals.
- Source/evidence IDs restricted to the saved model request; unsupported responses remain flagged for inspection.
- Gap hypotheses anchored to approved extraction items, with revalidation when supporting approval is revoked.
- Optional OpenAI Responses runner with a user-selected model, structured JSON, no tool calls, no automatic retries, and saved request/raw response artifacts. It does not import responses automatically.
- Approved evidence CSV, bibliography exports, source snapshots, a citation-linked working digest, review coverage, a local HTML report and artifact hashes.
- Offline synthetic demonstration and mocked model-adapter tests; screening decisions remain human-controlled.

Scope: exact text matching checks quote occurrence, not semantic entailment; human support confirmation is required. The illustrative appraisal framework is not validated. Documents must be supplied as UTF-8 text; no PDF OCR/download or automatic meta-analysis is performed. Qualitative uncertainty is not calibrated probability. Hypotheses remain hypotheses, and the digest is not an automatically validated publication synthesis.

## Delivered: interactive dashboard (0.5.0)

- LitAtlas: a responsive, locally served research workbench with an ink sidebar, light/dark themes, command palette and keyboard navigation.
- Overview metrics derived from screening/evidence ledgers, publication timeline, metadata coverage and actual decision activity.
- Persistent review registry, protocol setup, criteria revisions, CSV/RIS/JSON imports and background public-database retrieval.
- Study library with search, source/year/status filters, sorting, table/cards, detail drawer and safe filtered CSV exports.
- Reviewer-specific queues, paired title/full-text decisions, conflict adjudication, explicit retrieval and study linking through the existing workflow services.
- Interactive co-authorship, keyword, co-citation and coupling maps with thresholds, normalization, node inspection, zoom/pan and complete graph JSON downloads.
- Evidence ledger setup, custom framework upload, source-text capture, manual extraction/appraisal, independent approvals, grounding flags, request preparation and model-response import.
- ZIP downloads containing screening, bibliography, PRISMA and available evidence history with existing manifests.
- Synthetic exploration workspace isolated from real reviews; no remote publication, analytics or external UI assets.
- Loopback binding, per-process request token, Host/Origin checks, bounded requests, stale-ledger/version checks and optimistic evidence-review revisions.
- Backend regression tests and a reproducible, isolated Chromium end-to-end check across desktop/mobile flows.

Scope: a trusted local application, not authenticated internet hosting. Credentials are never returned to the browser; model calls remain an explicit CLI operation. Retrieval jobs run within the server session and are not resumable across restarts. Imports are restricted once screening decisions exist so report IDs cannot silently change.

## Practical pipeline validation increments

- Application-owned multi-query retrieval through dashboard background jobs and CLI, with persistent Markdown/JSON session journals and job history.
- Explicitly versioned source-identity deduplication while preserving verification of historical DOI-only runs.
- Conservative provider-date window audits, retained uncertain dates and verified before/after session comparisons.
- Policy-frozen literal query diagnostics, deterministic stratified blank human-review packets and illustrative known-item checks.
- Verified diagnostic comparison that flags lost known-item coverage without claiming semantic relevance, precision or recall.
- Private research/session paths excluded from Git and release archives; generic examples and source remain publishable candidates.

Scope: automated diagnostics do not replace independent human screening, relevance validation or research appraisal. Real data and practical error registers remain local unless deliberately reviewed for sharing.

## Corpus analytics increment

- Eight covered-corpus measures: papers, observed author identities, venues, observed affiliations, unique keywords, taxonomy-aware subject areas, available citations and affiliation countries.
- Richer provider/import metadata with preserved missingness and compatibility with earlier snapshots.
- Ranked venues with cross-provider venue-ID/ISSN evidence, top-ten display, search and all/included scope selection.
- Dated external journal-metric snapshots with explicit identity matching, provider/year/category provenance, unresolved ambiguity and missing versus not-applicable status.
- Complete CSV/JSON/input-snapshot exports, static HTML tables and desktop/mobile browser checks.

Scope: identity/name metadata remains imperfect; citations reflect provider snapshots. External journal metrics are imported, not inferred from the review corpus. Older snapshots are not silently enriched or rewritten.
