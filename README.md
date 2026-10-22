# Systematic and Bibliometric Literature Review

The workbench now supports retrieval, licensed-export imports, two-reviewer screening, full-text eligibility, adjudication, study-selection exports, and reproducible bibliometric networks.

Workshop resources and a reproducible Python foundation for literature retrieval and review preparation.

## Open the interactive dashboard

```bash
python -m pip install -e .
slr dashboard --workspace outputs/dashboard --demo
```

Open [LitAtlas at localhost:8765](http://127.0.0.1:8765). The dashboard includes an overview, searchable study library, independent screening queues, conflict resolution, interactive bibliometric maps, and a source-grounded evidence studio. Dark mode, a command palette (`Ctrl/Cmd+K`), filtered exports and responsive layouts are built in.

`--demo` seeds an empty workspace with clearly labeled synthetic reviews. Use **New review** to create your own protocol and import CSV/RIS/JSON records, or start a public-database retrieval. Your real reviews are stored locally and remain separate from the examples. Omit `--demo` for an empty workspace.

Connect existing CLI ledgers without copying their decisions:

```bash
slr dashboard --workspace outputs/my-workspace --review-db outputs/screening-demo/review.sqlite
# Add --evidence-db outputs/evidence-example/evidence.sqlite only when it belongs to that same screening review.
```

The server binds to `127.0.0.1` and uses local request protections. Reviewer identities remain trusted local labels; this is not a hosted multi-user service. Read the [dashboard guide](Docs/Dashboard_Guide.md) for workflow details, data storage and verification commands.

## Run the review pipeline

Requires Python 3.11 or newer. The core package has no third-party runtime dependencies.

```bash
python -m venv .venv
# Linux/macOS:
source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install -e .

# Offline demonstration with clearly synthetic metadata:
slr --config configs/example_review.toml --fixture Examples/demo_records.json --output outputs/demo

# Live search (network access required):
slr --config configs/example_review.toml --output outputs/live-review
```

Every run requires a new output directory. Edit the TOML configuration to choose the query, sources, publication years, and maximum retrieved records per source. For OpenAlex cursor pagination, set `OPENALEX_API_KEY` in your environment. Credentials are sent in an authorization header, never stored in configuration or logs. Set the optional `mailto` field to identify your requests. Keys are not required for Crossref. See the official [OpenAlex authentication documentation](https://help.openalex.org/api/authentication/) and [Crossref API documentation](https://www.crossref.org/documentation/retrieve-metadata/rest-api/).

The Python module and historical script entry points accept the same arguments:

```bash
python -m slr --config configs/example_review.toml --fixture Examples/demo_records.json --output outputs/module-demo
python Scripts/literature_search.py --config configs/example_review.toml --fixture Examples/demo_records.json --output outputs/script-demo
```

## What a run produces

- Raw API response pages (live mode) or a normalized fixture snapshot (offline mode).
- `retrieved.json`: all normalized records before deduplication.
- `records.json`, `records.csv`, `records.bib`, `records.ris`: unique records for downstream research tools.
- `duplicates.json`: DOI matches and the retained/removed identifiers.
- `identification.json`: retrieved, removed, and remaining counts derived from the records.
- `summary.json`: publication counts by year, excluding unknown years.
- `manifest.json`: UTC timestamps, query and filters, source totals, retrieval caps, completion status, package version, and SHA-256 hashes of output artifacts.

A failed run is marked as failed and must not be used as a completed search. Previous completed sources remain available, but failure mid-source does not preserve that source's partial pages. Output directories are never overwritten.

## Research methods and limitations

Search syntax is interpreted by each provider: Crossref free-text search is not a portable Boolean search engine. Test source-specific queries with a librarian and retain your review protocol separately. Publication date coverage and citation counts differ across databases. OpenAlex and Crossref do not replace licensed Scopus or Web of Science searches.

Deduplication compares normalized DOIs only. It keeps the first record and merges source identifiers into its provenance; alternate metadata remains in raw pages and `retrieved.json`. Records without valid DOIs remain separate even when titles match. Review them manually. Citation counts remain provider-specific, and missing citation data stays missing.

The offline fixture contains synthetic records and bypasses API search and date filters. Its manifest explicitly identifies fixture mode. The sample configuration caps retrieval; inspect the `truncated` flags before treating a live search as exhaustive. APIs change over time, so saved raw responses are necessary for inspection and later reprocessing.

Identification counts describe review preparation. They are **not a complete PRISMA flow diagram** and do not imply that screening or eligibility assessment occurred. Human screening, dual-reviewer conflict resolution, full-text eligibility, PubMed retrieval, and PRISMA-style selection exports are available through the commands below. Bibliometric networks and coverage-aware summaries are available through `slr analyze`. Source-anchored extraction, configurable study appraisal, human-reviewed evidence digests and optional AI proposals are available through `slr evidence`. A dashboard remains a future milestone. No AI-generated research claims are produced by this package.

## Screen and assess eligibility

```bash
slr review init --run outputs/demo --db outputs/demo.sqlite --name "Demo review" --reviewers alice bob --adjudicator carol --criteria configs/example_criteria.md
slr review queue --db outputs/demo.sqlite --reviewer alice
slr review decide --db outputs/demo.sqlite --version 1 --record R000001 --actor alice --stage title --decision include
slr review decide --db outputs/demo.sqlite --version 1 --record R000001 --actor bob --stage title --decision include
slr review retrieve --db outputs/demo.sqlite --version 1 --record R000001 --actor alice --status retrieved
slr review decide --db outputs/demo.sqlite --version 1 --record R000001 --actor alice --stage fulltext --decision include
slr review decide --db outputs/demo.sqlite --version 1 --record R000001 --actor bob --stage fulltext --decision include
slr review link-study --db outputs/demo.sqlite --version 1 --record R000001 --actor carol --study S1
slr review status --db outputs/demo.sqlite
slr review export --db outputs/demo.sqlite --output outputs/screening-report
```

The second synthetic record remains pending in this example, so the export is explicitly incomplete. See [the screening guide](Docs/Screening_Guide.md) for exclusions, adjudication, criteria revisions and a complete demonstration. Exports include a self-contained SVG flow diagram, counts, decision history, a screening table, and included-report metadata in four formats.

## Import licensed database exports

```bash
slr import --input scopus.csv web-of-science.ris --source licensed-export --output outputs/imported
```

CSV accepts normalized columns and common Scopus/Web of Science headers; RIS supports tagged records and wrapped fields. Use separate invocations for distinct source labels, then combine their `records.json` files with another import if needed. Imports preserve original files and file hashes. Source labels describe where records came from; they do not establish database coverage, search dates or query completeness. Keep that information in your protocol. See the screening guide for supported fields and limitations.

## Search PubMed

```bash
slr --config configs/pubmed_review.toml --output outputs/pubmed
```

The PubMed adapter saves the ESearch response, query translation and EFetch XML batches. Requests run at one per second with the shared retry policy. The client caps each PubMed query at 10,000 records; use narrower date partitions or NCBI EDirect for larger searches. Configure your contact email using `mailto`. See [NCBI E-utilities documentation](https://www.ncbi.nlm.nih.gov/books/NBK25499/).

## Bibliometric analysis

```bash
# Data/graph exports use only the core package:
slr analyze --run outputs/live-review --output outputs/bibliometrics

# Optional figures and synthetic demonstration:
python -m pip install -e '.[analysis]'
slr analyze --input Examples/bibliometrics_records.json --output outputs/bibliometrics-demo --figures

# Analyze included reports after screening is complete:
slr analyze --db outputs/demo.sqlite --output outputs/included-bibliometrics --figures
```

The last command rejects incomplete screening unless you explicitly add `--allow-incomplete` for provisional included reports. Use `--min-occurrences`, `--min-edge-count`, and `--normalization none|cosine` to define thresholds and weights. The output includes four networks (co-authorship, keyword co-occurrence, co-citation, bibliographic coupling), JSON/CSV/GraphML data, publication trends, keyword-by-year counts, provider-specific citation summaries, methods, coverage, provenance, hashes, and a local `report.html`. With `--figures`, six figures are saved as SVG and PNG.

No references or keywords are invented when metadata is missing. Author names are not automatically disambiguated, and source-specific reference identifiers are joined only when explicit identities in the corpus support that mapping. See [the bibliometric methods guide](Docs/Bibliometrics_Guide.md) for formulas, metadata limitations, clustering and a hand-calculated example.

## Evidence extraction and AI assistance

```bash
# Complete offline example, including screening, extraction and appraisal:
python Scripts/evidence_demo.py --output outputs/evidence-example

# Start from a completed screening ledger:
slr evidence init --screening-db outputs/demo.sqlite --db outputs/evidence.sqlite --framework configs/evidence_framework.json
slr evidence add-source --db outputs/evidence.sqlite --record R000001 --file paper.txt --kind fulltext --label "Supplied article text"
slr evidence prepare --db outputs/evidence.sqlite --record R000001 --task extract
slr evidence status --db outputs/evidence.sqlite
slr evidence export --db outputs/evidence.sqlite --output outputs/evidence-report
```

The initializer requires completed screening and study links; the earlier partial README screening example needs to be finished first. The complete offline demo produces an eligible ledger you can also use.

Extraction/appraisal proposals retain source quotes, supplied page numbers, uncertainty, rationale and producer metadata. A human must approve support before an item enters the working draft. Missing fields and unreported information are distinct. Gap suggestions stay hypotheses and must cite currently approved evidence. Criteria changes block new writes to stale evidence ledgers.

Manual proposals and imported model responses need no API account. An optional `run-ai` command uses a user-selected OpenAI model and `OPENAI_API_KEY`; invoking it sends the saved source/prompt packet to OpenAI. It saves raw responses and never imports or approves them automatically. See [the evidence guide](Docs/Evidence_Guide.md) for the response schema, commands and review rules. The example appraisal framework is illustrative, not a validated risk-of-bias instrument.

## Workshop materials

The original educational resources remain in their existing case-sensitive directories:

- `Data/`: search examples and datasets.
- `Docs/`: learning outcomes, tool lists, and resources.
- `Examples/`: review examples and synthetic pipeline fixture.
- `Slides/`: workshop presentations.
- `Scripts/`: the literature-search compatibility entry point.
- `ai-introduction-writing-workshop/`: introduction-writing exercises and prompts.

R/bibliometrix, VOSviewer, Rayyan, Zotero, and Mendeley are separate research tools, not Python runtime requirements. Install them separately when following the relevant workshop exercises.

## Development

```bash
python -m pip install -e '.[dev]'
python -m pytest
python -m build
```

CI tests Python 3.11–3.13, builds the distribution, and runs the offline example. Tests use mocked API responses and require no credentials. See [CONTRIBUTING.md](CONTRIBUTING.md) and [the roadmap](Docs/Implementation_Roadmap.md).

## License and contact

GPL-3.0, as provided by [LICENSE](LICENSE). Earlier MIT statements were inconsistent with that license and have been corrected.

Workshop contact: Dr. Nti, ntiik@ucmail.uc.edu, University of Cincinnati, USA.

### Practical research pipeline

Run multi-query searches through the dashboard or `slr pipeline --plan PLAN.json --output NEW_DIRECTORY`. The application preserves per-session Markdown error/lesson reports and raw retrieval evidence. See [Pipeline guide](Docs/Pipeline_Guide.md) for usage; private practical-test logs remain local and ignored.
