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
