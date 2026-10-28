# Screening methods drafts

Create a deterministic draft from a screening ledger:

```sh
slr report --db private/review.sqlite --output outputs/methods-draft
```

Optionally supply `--run outputs/search-run` to reverify retrieval-file hashes and confirm that the run matches the ledger's embedded origin. Without this option, the report uses the embedded manifest and explicitly says that retrieval files were not reverified.

The command reads the source database through a SQLite backup, including committed WAL data. It computes screening counts, agreement, and protocol history from the same frozen copy. It does not change screening decisions or call an AI service. Criteria and saved protocol content must match their stored hashes.

The output contains:

- `methods.md` and escaped, standalone `report.html`: a human-review draft of recorded screening state.
- `prisma.svg`: the existing selection-flow rendering, with unresolved work visible.
- `report-inputs.json`: the frozen input records, events, criteria, protocol and embedded retrieval manifest.
- `report-provenance.json`: statement identifiers, JSON pointers and hashes of their supporting values.
- `prisma-coverage.json`: selected reporting items with available ledger support and remaining manual work.
- `manifest.json`: output-file hashes and separate artifact-generation and review-completion statuses.

The coverage table covers selected items only. It does not certify compliance with the [PRISMA 2020 checklist](https://www.prisma-statement.org/prisma-2020). Authors must complete the full checklist and assess whether each statement accurately describes their research. Protocol declarations are plans; a saved registration identifier is not verified registration. Local reviewer labels do not authenticate independent reviewers. Undefined agreement statistics remain undefined.

Offline fixtures and imported libraries are identified explicitly. Neither establishes that a database search was executed. Live-search logs still require inspection for failures, caps, dates and coverage. Counts distinguish included reports from linked studies. Incomplete screening produces a provisional draft.

Replay the captured inputs without reopening the database:

```sh
slr report --snapshot outputs/methods-draft/report-inputs.json --output outputs/methods-replay
```

Keep the companion provenance file beside the snapshot. Its hash detects accidental changes; it is not a signature or proof of authentic decisions. Identical inputs produce identical output bytes. Existing output directories are never overwritten.

These bundles contain potentially private records and reviewer activity. Keep them under an ignored local output directory and review them before sharing. The command does not generate evidence findings, risk-of-bias judgments or synthesis prose. The current evidence exporter remains available separately; integrating its approvals into the manuscript outline is a later increment.


### AI assistance, deviations and deduplication limitations

Reports now include `ai-disclosure.json` and a researcher-verification draft summarizing recorded question/protocol requests, responses, proposals and accept/edit/reject events. The review export also includes the associated extraction/appraisal ledger when available. For CLI methods reports, supply `--evidence-db path/to/evidence.sqlite` to include those stages; a ledger from another review is rejected. Prepared requests do not prove a model call took place. Separate analysis-recommendation experiments are not linked to a review and are marked unknown. Missing model digests, prompt versions or historical ledgers remain unavailable, never inferred as no AI use. This is recorded-ledger coverage, not automatic telemetry or a complete account of outside AI use.

The methods report includes current screening authorization and all recorded protocol-deferred exceptions/revocations. Researchers must verify the disclosure, explain external AI use and confirm the deviations are described accurately. Saved historical report snapshots retain their original coverage; replay does not invent new observations.

Counts, flow diagrams and review exports now identify the recorded deduplication method: historical `doi-v1` matches normalized DOI; `doi-or-source-id-v1` additionally matches exact source/ID with the existing DOI-conflict protections. Neither performs fuzzy title/author matching. Cross-export records without matching identifiers may remain, so counts may overstate distinct reports. Retained reports are not necessarily distinct studies.


### Private verification bundle

The dashboard's **Export review** now includes a frozen screening SQLite ledger, available evidence ledger, recorded question/protocol history, AI disclosure, methods report and SHA-256 inventory. It uses SQLite backup, including committed WAL data, instead of copying a potentially active database file. Inspect the bundle before sharing: it includes potentially sensitive records, reviewer labels, recorded AI inputs and historical local paths. It does not automatically copy model runtimes, credentials or external PDF files.

```sh
slr replicate --db review.sqlite --output outputs/verification-bundle
# Optionally add --evidence-db evidence.sqlite
slr verify outputs/verification-bundle
slr verify downloaded-review-export.zip
```

The verifier reads ZIP entries without extracting supplied paths. It rejects missing/unlisted/modified files, duplicate ZIP names, unsafe paths and symlinks, with a 1 GiB / 10,000-file limit. It recomputes screening counts and agreement from the frozen ledger, checks the report's screening binding, re-renders deterministic report outputs, checks protocol approval state, and recomputes question/AI disclosures from the bundled ledgers. It returns nonzero on failure. Existing output directories are refused.

Three different claims must stay separate: **verifiable** files match their inventory; **replayable** recorded histories can be inspected; selected **re-executable** deterministic calculations reproduce. The bundle is an initial application-specific format, not a complete RO-Crate implementation. It does not rerun retrieval or AI, verify full external retrieval files, certify scientific validity, or authenticate independent reviewers. Evidence files are hash-checked; their full scientific judgments are not independently recomputed. A manifest fingerprint is local integrity evidence, not a signature or public trust anchor; a person who rewrites the entire bundle can produce a new fingerprint. Reports can be incomplete and still produce an internally consistent bundle. Verification currently uses the installed application version, so preserve the recorded software version and investigate differences after upgrades.
