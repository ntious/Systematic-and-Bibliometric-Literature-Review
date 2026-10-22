# Application pipeline and practical-session logging

The dashboard's **Import literature → Search databases** form accepts one query per line. It submits one job to the application. The background worker runs the package pipeline, which calls the existing retrieval service for each query/source, preserves subrun artifacts, verifies hashes, aggregates and DOI-deduplicates results, checks metadata quality, exports provisional bibliometrics and registers a new screening corpus. It generates no screening votes or evidence approvals.

Follow progress in the dashboard footer. After refresh, the review shows a **Download session log** button for each pipeline job with a report. It is also available while a logged job is running. Completed/failed jobs persist across restarts. Interrupted jobs are marked failed; they are not resumed.

## CLI entry points

```
slr pipeline --plan configs/example_pipeline.json --output outputs/new-pipeline-session
slr pipeline inspect --session outputs/new-pipeline-session
```

The first command runs the application pipeline without a browser; output must be a new directory. The CLI returns a verified retrieval folder that can be connected through `slr review init` / the dashboard's existing ledger workflow. The second verifies saved aggregate artifacts, generates `quality.json` and appends findings to the existing session log without changing the corpus.

Plans are JSON objects with `queries` (1–20 unique strings), `sources` (supported adapters: `openalex`, `crossref`, `pubmed`), optional `year_from`/`year_to`, and `max_records_per_source` (per query/source). Databases without an implemented adapter need authorized native exports; listing a database in a research protocol does not make it callable.

## Artifacts and failure behavior

Each session preserves:

- `plan.json`, `SESSION.md`, `session.json`: identity, UTC events, stages, severity, errors, evidence paths, remedies/lessons and final execution status.
- `search-NN.toml`, `search-NN/`: query configuration and existing service's raw responses, normalized records, exports and manifests, when available.
- `retrieval/`: verified aggregate artifacts, query provenance, failures and DOI duplicate log.
- `quality.json`: missing abstracts, repeated provider identities and outstanding formal-screening gates.
- `analysis/`: provisional networks, methods and metadata coverage, if computation succeeds.

A source failure is recorded and other planned requests continue. A partial result reports `partial`; the dashboard may register the verified successful subset with an explicit partial outcome. If no source returns records or verification fails, the existing review stays selected. Analysis failure is logged and marks the session partial; valid retrieval can still be used independently. Failed HTTP bodies and partial pages inside a failed existing adapter call are not yet retained by that adapter; the report records that boundary rather than inventing artifacts.

Warnings include caps, missing abstracts, repeated provider IDs and unchecked exact dates/version linkage. Historical DOI-only runs may retain repeated DOI-free source IDs. New runs use versioned identity handling and date auditing as described below. Expanded database coverage and relevance validation remain research gates.

Jobs live in workspace `jobs.json`. Markdown reports and structured events are written after each event using atomic replacement. Do not point multiple simultaneously running dashboard servers at the same workspace: the local persistence model is single-process. Use a distinct workspace for parallel application instances.

The cross-session practical-test register is kept locally in `Docs/Practical_Test_Log.md`; actual protocols, plans and session snapshots live in ignored `research/` and `outputs/` folders. They are excluded from Git and release archives. Logs may contain research queries, paths and exception messages; review explicitly before sharing.

## S03 remedies: dates, identities and verified comparisons

Plans may supply `date_from` and `date_to` as exact `YYYY-MM-DD` strings. The dashboard provides optional exact-date fields. Retrieval still applies the configured years at the provider; the pipeline then audits captured publication metadata locally against the exact window. `retrieval/captured.json` retains all captured records before date filtering and identity deduplication. `retrieval/date-audit.json` records per-record status and preprocessing counts. `retrieved.json` and identification counts describe the date-scoped input, including uncertain dates retained for human checking. Consult captured counts when reporting raw search yield.

Dates are provider-reported. A partial date is a possible interval; it is excluded only if the entire interval is outside the window. An interval crossing the cutoff and an unknown/invalid date remain in the corpus with an uncertainty flag. Metadata errors and differing publication versions still need human assessment.

New aggregate manifests declare `doi-or-source-id-v1`: matching DOI or exact nonempty provider source/ID, with provenance retention. Identity matching does not merge conflicting nonempty DOI claims. Blank IDs and title resemblance are insufficient. Historical manifests retain the original DOI-only behavior, so old runs remain verifiable. Preprint/journal identity resolution remains a separate task.

```
slr pipeline compare --baseline outputs/old-session --session outputs/new-session
```

The comparison verifies both aggregate manifests, writes `comparison.json` and `COMPARISON.md` in the new session, and appends a session event. It compares captured provider-ID multisets, retained counts, repeated identities and the newer date audit. It does not rewrite either corpus or establish metadata truth, relevance or research validity.

## Query calibration

Upload an optional calibration policy JSON in the dashboard's search form. The application runs diagnostics after verified aggregation and provides a **Download calibration sample** button. `configs/example_calibration.json` is a generic example. Actual review policies belong in ignored `research/` or `private/` folders.

The policy contains named term `groups`, an optional `sample_per_stratum` (default 2), and optional `known_items` with titles/DOIs. Literal, case-insensitive, word-boundary title/abstract matches indicate whether the metadata contains each group's cues. This is a diagnostic proxy: it is not semantic relevance, eligibility, precision or recall. Missing abstracts and absent cues never generate exclusion decisions.

The software writes `calibration/REPORT.md`, `report.json`, per-record diagnostics, a frozen policy, a hash manifest and `human-review.csv`. Sampling is deterministic within each query and metadata/cue stratum; records shared between queries appear once with their sampled-for queries. All human judgment, rationale, reviewer and review-time columns are blank. Stratification is useful for calibration but does not yield an unbiased precision estimate without an appropriate evaluation design. Known-item coverage is explicitly illustrative, not an independently adjudicated recall test.

To diagnose an existing verified run without editing it:

```
slr pipeline calibrate --run outputs/prior-session/retrieval --policy configs/example_calibration.json --output outputs/new-calibration
```

The output directory must be new. Source artifact hashes and the frozen policy hash identify the exact input and diagnostic configuration. Use the same policy when comparing query revisions; source coverage, retrieval caps and metadata differences still limit interpretation. Final relevance validation requires human review of the sample and an independently selected reference set.

## Public repository boundary

Source code, synthetic fixtures, generic example configurations and usage guides are public candidates. Actual research protocols/plans, ledgers, downloaded source material, raw API results, internal feedback and practical-session logs are local research records. `.gitignore` covers these paths and common credential/runtime filenames; `MANIFEST.in` separately excludes them from release archives. Git ignores do not remove files already tracked or erase prior Git history. The privacy audit checks tracked paths and fresh wheel/source archive members. Review new public files before publishing; no pattern scan can establish that every possible sensitive value is absent.

Compare two verified diagnostic packets produced under the same frozen policy:

```
slr pipeline compare-calibration --baseline outputs/baseline-calibration --revision outputs/new-session/calibration --output outputs/query-comparison
```

The software rejects mismatched policies or changed artifacts. If a query revision loses illustrative known-item coverage, the report is marked `needs-investigation` and advises against automatic adoption. It does not infer a measured recall decrease from a non-independent reference list. When the revision belongs to an application session, its Markdown session log also records the comparison.

See [Local_Data_Policy.md](Local_Data_Policy.md) for the repository/package privacy boundary.
