# Platform Enhancement Plan: toward a world-class SLR platform

**Date:** 2026-10-22
**Baseline:** working tree at version 0.5.0. That includes the CLI, screening and evidence ledgers, bibliometrics, the LitAtlas dashboard, the multi-query pipeline and `research/alert-triage`. The test suite passes (134 tests).
**Companion:** [reviewer_feedback.md](reviewer_feedback.md) covers security and code findings. This document covers product and methods gaps.

---

## 1. Where the platform stands

### Distinctive strengths

These are rare even in commercial tools. Keep them as non-negotiable design principles.

- **Provenance by default.** Raw API responses, SHA-256 manifests, input snapshots and hash-verified runs.
- **Append-only ledgers.** Criteria versioning and stale-write rejection for screening and evidence.
- **Source-grounded AI.** Quotes are checked against stored text, proposals never become decisions without a human, and the request is hash-bound to the response.
- **Honest limits.** Missing metadata stays missing, research gaps are labelled as hypotheses, and "not reported" differs from "absent".
- **Zero runtime dependencies and local-first operation**, plus a usable dashboard.
- **Bibliometrics and evidence synthesis in one tool.** Most competitors do one or the other.

### What "world class" means in this field (benchmarks)

| Capability area | Reference tools |
|---|---|
| Screening workflow and collaboration | Covidence, DistillerSR, Rayyan, EPPI-Reviewer |
| ML-prioritized screening | ASReview, EPPI-Reviewer, DistillerSR, SWIFT-ActiveScreener |
| Extraction, risk of bias, GRADE, meta-analysis | Covidence, RevMan, EPPI-Reviewer, Nested Knowledge |
| Living reviews and auto-updates | Nested Knowledge, DistillerSR |
| Bibliometric science mapping | bibliometrix/Biblioshiny, VOSviewer, CiteSpace |
| Reporting standards | PRISMA 2020, PRISMA-S, PRISMA-ScR, PRISMA-P, RAISE (responsible AI in evidence synthesis) |

### Gap summary

| Area | Status here | Gap to close |
|---|---|---|
| Search and retrieval | OpenAlex, Crossref, PubMed; imports; multi-query pipeline | Search builder, more sources, recall validation, citation chasing |
| Deduplication | DOI or exact source ID | Fuzzy matching with a human-verified pair queue |
| Screening | Dual review, adjudication, criteria versions | Active-learning prioritization, inter-rater statistics, pilot rounds |
| Full text | UTF-8 text only; retrieval status is recorded manually | Open-access lookup, PDF ingestion with page mapping |
| Appraisal | One illustrative custom framework | Validated tools (RoB 2, ROBINS-I, JBI, CASP, MMAT), risk-of-bias plots |
| Synthesis | Qualitative digest only | Meta-analysis, GRADE, Summary of Findings tables |
| Reporting | Database-only PRISMA SVG | Full PRISMA 2020 (other methods, updates), checklists, methods text |
| Bibliometrics | Four networks, trends, citations | Laws, thematic maps, bursts, country/institution analysis, VOSviewer export |
| Collaboration | Trusted local labels on one machine | Authenticated multi-user mode with enforced blinding |
| AI | OpenAI only, used for extraction | Provider-neutral, local models, accuracy evaluation, advisory screening |
| Distribution | Source install | PyPI, Docker, documentation site, validation studies |

---

## 2. Recommendations by priority

Effort key: **S** is about 1 week or less, **M** is 2-4 weeks, **L** is more than a month (one developer).

### Tier 1: Methodological core (highest impact on research quality)

**1.1 Inter-rater reliability statistics (S). [DONE 2026-10-22, uncommitted]** Implemented in `src/slr/agreement.py`, `screening.start_pilot` and the `slr review pilot` and `slr review agreement` commands. It adds `agreement.json` to the export and an agreement line to the PRISMA SVG. Tests are in `tests/test_agreement.py`, and the workflow is documented in `Docs/Screening_Guide.md`. Dashboard display is still to do: `dashboard.py` was being edited concurrently, and the activity feed currently labels pilot events as title decisions. All the data is already in the `events` table.
- Report Cohen's κ, PABAK and percentage agreement per stage and criteria version.
- Include them in `prisma.json`, the export and an Overview card.
- Add a *calibration round* mode in which both reviewers screen the same pilot sample of N records and see agreement before full screening.

**1.2 Active-learning screening prioritization (M).** This is the single biggest workload reducer.
- Rank each reviewer's queue by predicted relevance. Start with TF-IDF plus logistic regression in an optional `[ml]` extra, retrained after every K decisions.
- Never auto-exclude. Log the model version, training-set size and rank position for each decision in the ledger.
- Show a stopping-rule panel (e.g. the SAFE procedure, or "N consecutive irrelevant records") with an explicit warning that recall is estimated, not guaranteed.
- Validate against the open SYNERGY benchmark datasets before release.

**1.3 Candidate-pair deduplication (M).** DOI-only matching misses many duplicates, and the pipeline log already flags DOI-free repeats.
- Generate candidate pairs by blocking on normalized title, first author, year and pages, then score with token similarity.
- Send pairs above a threshold to a *human-confirmed* merge queue, recorded as events.
- Link preprints to the published versions (arXiv/bioRxiv to the journal DOI, using OpenAlex `locations` and `versions`).
- Keep the current conservative automatic rule unchanged.

**1.4 Full-text acquisition and PDF ingestion (M).**
- Look up open-access copies through Unpaywall or OpenAlex `best_oa_location`. Retrieve legal open-access copies only, and record the licence and URL.
- Upload PDFs and extract text per page, using `pypdf` in an extra and optionally GROBID for structure. Evidence anchors then refer to *real PDF page numbers*.
- Store the original PDF hash alongside the extracted text hash, and flag OCR-only pages as lower confidence.

**1.5 Search strategy builder and recall check (M).**
- Add a PICO/PECO/SPIDER concept builder that produces provider-specific query strings, plus PubMed MeSH suggestions via E-utilities.
- Record every executed string, database, platform, date, filter and result count, which is the PRISMA-S reporting table.
- Add a **seed-set recall check**: the user lists 10-30 known relevant papers, and the platform reports which ones each search found. This is the most practical way to show search adequacy.

**1.6 Citation chasing and the full PRISMA 2020 flow (M).**
- Add backward and forward snowballing from included studies using OpenAlex `referenced_works` and `cited_by`, with the records labelled as "other methods".
- Extend the PRISMA generator with the *other methods* branch and *updated review* variants. The guides list these as out of scope today.

**1.7 Structured protocol and amendments (S). [DONE 2026-10-22, uncommitted]** Implemented in `src/slr/protocol.py` as `slr protocol check/save/status/export`, with an example in `configs/example_protocol.json`, tests in `tests/test_protocol.py` and documentation in `Docs/Protocol_Guide.md`. Registry field labels are a best-effort mapping that users must verify against the live forms. A dashboard protocol editor is still to do.
- Add a PRISMA-P protocol form covering the question, eligibility, sources, screening and synthesis plan.
- Export fields for PROSPERO or OSF registration.
- Link protocol amendments to criteria versions so deviations are documented automatically.

### Tier 2: Synthesis and reporting (what turns screening into a publishable review)

**2.1 Validated appraisal instruments (M).**
- Ship framework files for RoB 2, ROBINS-I, the JBI checklists, CASP, MMAT and Newcastle-Ottawa.
- Check each instrument's licence before bundling. Where redistribution isn't allowed, ship the structure plus a link.
- Use domain-level signalling questions and algorithmic overall judgments only where the instrument defines them.
- Add traffic-light and weighted-summary plots in the style of robvis.

**2.2 Quantitative synthesis (L).**
- Add typed effect-data fields (2×2 counts, means/SD/n, adjusted estimates with CI) and conversions between effect measures.
- Implement fixed and random effects (DerSimonian-Laird and REML), I², τ² and prediction intervals.
- Add forest and funnel plots, Egger's test, and subgroup and leave-one-out sensitivity analyses.
- Also export to R `metafor` scripts and RevMan, so statisticians can verify results independently.

**2.3 GRADE certainty and Summary of Findings tables (M).** Rate each outcome on risk of bias, inconsistency, indirectness, imprecision and publication bias, with a written rationale stored in the ledger. Export SoF tables as HTML and DOCX.

**2.4 Manuscript-ready reporting (M).**
- Auto-fill the PRISMA 2020, PRISMA-ScR and PRISMA-S checklists with the location of each item in the outputs.
- Generate a *deterministic* methods paragraph from the manifests: sources, dates, counts, reviewer process and κ.
- Export DOCX and LaTeX tables.
- Package everything as an RO-Crate and offer a Zenodo/OSF deposit, which gives the review data its own DOI.

**2.5 Bibliometric parity with bibliometrix, VOSviewer and CiteSpace (M).**
- Add Bradford and Lotka law analyses, and author h, g and m indices.
- Add thematic maps (Callon centrality and density), thematic evolution across time slices, and three-field (Sankey) plots.
- Add country and institution collaboration networks from OpenAlex institutions and ROR IDs.
- Add Kleinberg citation-burst detection, historiographs, and OpenAlex field-normalized citations (FWCI).
- Export VOSviewer map/network files and Pajek, so users can switch to familiar tools.

### Tier 3: Platform and collaboration (from local tool to platform)

**3.1 Authenticated multi-user server mode (L).** This is the main step from "workbench" to "platform".
- Add a separate `slr serve` mode with OIDC/OAuth sign-in, roles (lead, reviewer, adjudicator, viewer) and *server-enforced* blinding.
- Offer PostgreSQL as an option and keep SQLite for local mode.
- Hash-chain the audit events (INFO-1 in the reviewer feedback).
- Provide a Docker Compose deployment.
- Keep today's loopback mode as the default so solo researchers keep zero-setup operation.

**3.2 Living systematic reviews (M).**
- Re-run saved searches on a schedule.
- Append *only new* records to an existing review with new IDs. Today, imports are blocked once decisions exist.
- Add an "updated review" PRISMA flow and change notifications.

**3.3 Source coverage and integrations (M, ongoing).**
- **Bibliographic sources:** Europe PMC, arXiv, Semantic Scholar and DBLP. Semantic Scholar and DBLP failed in session S01 (log entries E02 and E03), so harden those adapters first.
- **Licensed sources:** Scopus and IEEE Xplore with the user's own keys.
- **Registries:** ClinicalTrials.gov and WHO ICTRP.
- **Reference managers:** Zotero (Web API and RDF), plus EndNote XML and Mendeley imports.

**3.4 Provider-neutral and evaluated AI (M).**
- Add an adapter interface covering OpenAI, Anthropic, Azure and local models (Ollama/llama.cpp) for confidential full texts.
- Build an **evaluation harness** that compares AI extraction with human-approved gold data and reports precision and recall per field and model version.
- Track cost and tokens per request.
- Allow AI as an *advisory* screener only. Log its agreement with humans, and never let it count as one of the two required reviewers.
- Align the documentation with the RAISE recommendations.

### Tier 4: Engineering excellence (what makes it trustworthy and adoptable)

| # | Item | Effort |
|---|---|---|
| 4.1 | Publish to PyPI and a Docker image. Add a versioned MkDocs documentation site, CHANGELOG and semantic versioning. | S |
| 4.2 | CI: `ruff`, `mypy`, `pytest-cov` with a floor, `bandit`, `pip-audit`, CodeQL and SHA-pinned actions. Run `Scripts/check_dashboard_browser.py` in CI. | S |
| 4.3 | Property-based tests (`hypothesis`) for the CSV/RIS/PubMed parsers and DOI normalization. Add fuzzing for import files. | S |
| 4.4 | Scale testing at 50k-100k records. Paginate the dashboard API. Replace the per-record queries in `screening.snapshot` with a single grouped query. Add query plans and indexes as needed. | M |
| 4.5 | WCAG 2.2 AA accessibility audit of LitAtlas (keyboard, contrast, screen-reader labels). Prepare for i18n with externalized strings. | M |
| 4.6 | **Validation studies:** reproduce 2-3 published reviews end to end, using SYNERGY datasets for screening. Publish the recall, workload and agreement results, and submit a JOSS paper. This is what makes the platform citable and trusted. | M |
| 4.7 | Close the LOW items in `reviewer_feedback.md` and consolidate the duplicated helpers. | S |

### Keep the education strength

The repository began as a workshop resource, and that is an asset no competitor has.
- Add a *guided mode* in LitAtlas that explains each PRISMA step, linked to the slides and worksheets.
- Ship 2-3 complete sample projects (one systematic review, one scoping review, one bibliometric study).
- Include an instructor dashboard that compares student screening agreement on the same dataset.

---

## 3. Suggested release sequence

| Release | Theme | Contents |
|---|---|---|
| **0.6** | Screening quality | 1.1 inter-rater statistics and calibration, 1.3 candidate-pair dedup, 1.7 protocol, 4.2 CI hardening, 4.7 LOW fixes |
| **0.7** | Smarter search and screening | 1.2 active learning plus SYNERGY validation, 1.5 search builder and recall check, 1.6 citation chasing and the full PRISMA flow |
| **0.8** | Full text and appraisal | 1.4 open access and PDF ingestion, 2.1 validated instruments and RoB plots, 3.4 provider-neutral AI with the evaluation harness |
| **0.9** | Synthesis and reporting | 2.2 meta-analysis, 2.3 GRADE and SoF, 2.4 checklists, methods text, RO-Crate and Zenodo, 2.5 bibliometric parity |
| **1.0** | Platform | 3.1 multi-user server, 3.2 living reviews, 3.3 integrations, 4.1 PyPI, Docker and docs, 4.6 validation studies and JOSS paper |

**Quick wins to start with:** 1.1 (κ statistics), 1.7 (protocol form), the seed-set recall check from 1.5, the VOSviewer export from 2.5, and 4.2 (CI). Each takes a few days, builds on existing data and is visible to users immediately.

---

## 4. Guardrails to keep while expanding

1. A human remains the decision-maker for every inclusion, exclusion, extraction, appraisal and GRADE judgment. ML and AI only rank, suggest or flag.
2. Every new computation writes its methods, settings, inputs and hashes alongside its outputs, as the current modules do.
3. Missing data is never imputed silently. Estimated recall is labelled as an estimate.
4. Optional extras (`[ml]`, `[pdf]`, `[analysis]`, `[server]`) keep the core install dependency-free.
5. Local-first remains the default. The hosted mode is an addition, not a replacement.
