# Screening and eligibility guide

## Initialize and review independently

Run the retrieval example in the README first. `slr review init` verifies the completed run's file hashes and reconciles retrieved records, DOI duplicates and retained records before creating a database. Existing databases are never overwritten. Each database holds one review with two reviewer labels and a distinct adjudicator. Record IDs such as `R000001` are stable within that review.

A criteria file is saved verbatim (apart from outer whitespace), with a SHA-256 hash, UTC creation time and version. `slr review queue --db outputs/demo.sqlite --reviewer alice` returns criteria and the next available stage for each record without the other reviewer's votes. Review title and abstract using `--stage title`; the software does not fetch full texts.

Reviewer labels are not authentication. Anyone with database/file access can inspect the history or submit another label. This is a trusted local workflow, not a multi-user service or a guarantee of blinding. Share only the appropriate queues when coordinating independent reviewers, and restrict access to administrative status/history exports until independent decisions are complete.

## Decisions and adjudication

Two matching include votes advance a record. Exclusion requires a nonempty primary reason from each reviewer. If exclusion reasons differ, the result is a conflict even when both reviewers voted exclude. Use consistent protocol-defined reason labels.

```bash
slr review decide --db outputs/demo.sqlite --version 1 --record R000002 --actor alice --stage title --decision exclude --reason "Wrong population/context"
slr review decide --db outputs/demo.sqlite --version 1 --record R000002 --actor bob --stage title --decision include
slr review adjudicate --db outputs/demo.sqlite --version 1 --record R000002 --actor carol --stage title --decision exclude --reason "Wrong population/context"
```

Adjudication requires two conflicting votes and a nonempty reason, and only the assigned third reviewer may adjudicate. The same rules apply to full-text eligibility. An unresolved conflict never advances a record.

Before full-text decisions, mark an included title record `retrieved`, or `not_retrieved` with a reason. Reports not retrieved are separate from full-text exclusions. Decisions can only be entered after retrieval has been recorded. The retrieval command records a human assertion; it does not download documents.

```bash
slr review retrieve --db outputs/demo.sqlite --version 1 --record R000001 --actor alice --status not_retrieved --reason "Library request unsuccessful"
```

This command is an alternative to the README's `retrieved` example, not a correction after retrieval has already been saved.

## Pilot calibration round and inter-rater agreement

Before full title/abstract screening, the adjudicator can draw a reproducible pilot sample that both reviewers must screen first:

```bash
slr review pilot --db outputs/demo.sqlite --version 1 --actor carol --size 25 --seed 2026
slr review agreement --db outputs/demo.sqlite
```

- The sample is `random.Random(seed).sample(sorted record IDs, size)`. The seed, size and method are stored on each pilot event. Without `--seed`, a seed is derived from the review ID and criteria version, so the draw is still reproducible.
- A pilot can start only before any title decisions in the current criteria version, and only once per version.
- While the pilot is open, reviewer queues show only pilot records (marked `"pilot": true`), and title decisions on other records are rejected. Once both reviewers have decided every pilot record, normal screening opens. Pilot conflicts are adjudicated like any other conflict.
- Review the pilot agreement and discuss disagreements (and refine wording through a criteria revision if needed) before continuing. A criteria revision starts a new screening pass, so a new pilot can be drawn for it.

`slr review agreement`, `slr review status` and the export's `agreement.json` report agreement for each stage. The counts use only records that both reviewers decided independently in the current criteria version. Adjudications are excluded. Each stage reports:

| Field | Meaning |
|---|---|
| `pairs`, `table` | Number of paired decisions and the 2×2 table (`reviewerA/reviewerB`) |
| `observed_agreement` | Proportion of pairs with the same decision |
| `cohen_kappa` | (observed − expected) / (1 − expected), where expected agreement comes from each reviewer's include rate. `null` when undefined (no pairs, or both reviewers used one identical category throughout). |
| `pabak` | Prevalence- and bias-adjusted kappa, 2 × observed − 1 |
| `exclusion_reason_agreement` | Of pairs both excluded, how many share the same primary reason |

The pilot also reports `title_agreement` restricted to its sample. When most records are excluded, kappa can be low even with high observed agreement (the prevalence paradox), so report it together with observed agreement, PABAK and the table. Conventional labels such as "substantial" are not validity thresholds. The PRISMA SVG adds one agreement line per stage.

## History and criteria changes

Writes are transactional. Decisions and criteria have database triggers preventing updates/deletes through ordinary SQL, and duplicate submissions are rejected. This retains an inspectable history; a database owner can still bypass application controls, so this is not a tamper-proof audit system. Back up the SQLite file while the CLI is idle.

```bash
slr review criteria --db outputs/demo.sqlite --version 1 --file configs/revised_criteria.md
```

Provide a revised file with distinct criteria text. Revision increments the version, retains prior events, and returns every record to title screening. Votes, retrieval assertions and study links from earlier criteria versions are not carried into current counts. `--version` must match the current version for every write. An accidental vote cannot be silently edited: use a documented revised criteria pass or initialize a new ledger and retain the old one. Fine-grained correction events are not implemented in this release.

## Reports, studies and selection counts

One retained record represents one report in this release. The adjudicator must assign a study ID to each included report. Multiple reports may share the same study ID; included-study counts are the number of distinct assigned IDs. Reports without study IDs keep the workflow incomplete.

`slr review export` requires a new output directory. It writes:

- `review.json`: record states, original retrieval/import manifest, criteria history and all decision events.
- `screening.csv`: article titles, stage outcomes, reasons, retrieval status and study IDs.
- `prisma.json` and `prisma.svg`: derived selection counts and an original self-contained flow graphic.
- `records.json/csv/bib/ris`: currently included reports, including provisional results from incomplete reviews.
- `manifest.json`: criteria version, workflow completion and file hashes.

Pending votes, unresolved conflicts, missing retrieval assertions and missing study links are shown explicitly. During an incomplete review, `records_screened` counts resolved title decisions; it does not count a single unpaired vote as completed screening. At completion these conservation checks hold:

```text
identified = duplicates_removed + records_to_screen
records_to_screen = records_excluded + reports_sought
reports_sought = reports_not_retrieved + reports_assessed
reports_assessed = reports_excluded + reports_included
```

This renderer covers new database/register-only reviews. It does not model other search methods, previous-review studies, automation exclusions, or multiple bibliographic records for the same report without a DOI match. Resolve those cases outside this workflow before preparing a publication diagram. `complete` refers to screening the captured snapshot; retrieval limits or missing databases can still make the search incomplete. Inspect the origin manifest and protocol.

The graphic is an original rendering informed by [PRISMA 2020](https://www.prisma-statement.org/prisma-2020-flow-diagram), not a claim that using the software ensures full PRISMA reporting compliance. Cite Page MJ et al. BMJ 2021;372:n71, doi:10.1136/bmj.n71.

## Imports

Use UTF-8 (with or without BOM). CSV supports `title`/`Title`/`Article Title`/`Document Title`, DOI, Year/Publication Year, Abstract, Authors/Author Full Names, Journal/Source Title/Publication Title, EID/UT/Accession Number/source_id, URL/Link, and Citations/Cited by. Headers are case-insensitive. Author names are separated by semicolons; normalized JSON arrays in CSV author cells are also supported. Missing years and citations remain null. Malformed years, missing titles, duplicate headers and mismatched row lengths fail validation. Exact vendor headers outside this list need conversion first.

RIS supports TY/ER delimiters; TI/T1, AU/A1, DO, PY/Y1, AB/N2, JO/JF/T2, UR and ID/AN. Indented continuation lines are joined. Unsupported tags are retained in the original file but not normalized into additional metadata fields. CSV and RIS imports normalize core bibliographic metadata, not extraction/appraisal data. Original files and source row numbers remain available for inspection.

Normalized JSON arrays (such as a completed run's `records.json`) allow combining inputs from different adapters. Provide original `retrieved.json` files if you need identification counts to include duplicates previously removed in those runs; importing already deduplicated exports cannot reconstruct earlier removals. Imported records are not re-filtered by date or query. Search query/date/coverage metadata must be retained separately with your protocol. The CSV in `Data/` summarizes searches rather than individual papers and is not a record-level import fixture.

## Complete offline demonstration

After installing the package, run:

```bash
python Scripts/screening_demo.py --output outputs/screening-demo
```

This synthetic demonstration screens both records, includes one report linked to one study, excludes the other at title screening, and exports a complete flow. It uses no network or real research decisions.
