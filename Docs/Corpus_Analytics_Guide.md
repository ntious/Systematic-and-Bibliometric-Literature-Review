# Corpus summary and publication-venue analysis

Open **Research analytics** in LitAtlas. Select all captured reports or the currently included subset. An included subset is labeled provisional while screening is incomplete. These are report-level statistics, not a count of underlying studies or a claim that the search is exhaustive.

## Summary of results

| Measure | Definition |
|---|---|
| Papers | Retained report records in the selected scope |
| Authors (observed) | Distinct explicit author identities, otherwise normalized reported names |
| Publication venues | Distinct primary journals, proceedings, repositories or other reported venues; not retrieval databases |
| Affiliations (observed) | Distinct institution identifiers, otherwise normalized affiliation names |
| Unique keywords | Distinct case-folded, Unicode-normalized keywords; the card also reports per-paper keyword occurrences |
| Subject areas | Distinct labels within each reported subject taxonomy; taxonomy subtotals are disclosed |
| Citations (reported) | Sum of available retained-record citation counts, with metadata coverage and provider subtotals |
| Affiliation countries | Distinct reported affiliation-country labels/codes; not nationality or study location |

Each card shows how many reports supply that metadata. Missing metadata stays unavailable (—); a true zero is distinct from unavailable data. A wholly empty selected corpus has known zero counts. Whitespace-only labels are missing.

Names are not automatically disambiguated. Different identifiers or name-only variants may split a person/institution; identical names may conflate different entities. Provider citation counts and capture dates differ. The citation sum is descriptive of retained metadata; it is not field-normalized impact or an independently verified global total.

OpenAlex retrieval preserves embedded source IDs/ISSNs/publisher, authorship institutions and countries, and topic **field** labels. OpenAlex fields are not Scopus ASJC areas. Crossref preserves supplied publisher, ISSNs, author affiliations and subjects. PubMed preserves supplied affiliation strings without guessing countries from addresses. CSV/RIS/JSON imports preserve supplied metadata; older normalized snapshots do not acquire information they never captured. Start a new retrieval/import snapshot to capture richer metadata without rewriting an earlier research run.

CSV arrays use JSON arrays or semicolon-separated values. Supported new columns include `venue_id`, `issns` (or `ISSN`), `publisher`, `affiliations`, `affiliation_ids`, `countries`, `subject_areas` (or `Subject Areas`) and `subject_taxonomy`. IDs must align positionally with names when supplied. RIS `SN`, `PB` and `AD` preserve reported ISSNs, publisher and affiliation/address strings respectively. No geography is inferred from free-text addresses.

## Top publication venues

The table defaults to the top ten venues by **TP**, publications in the selected corpus. Search by venue, publisher or ISSN; switch to top 25 or top 100. Ties use normalized venue names and stable identity order. Matching venue IDs and ISSNs can link records across retrieval providers. Exact normalized names are used only when identifier evidence is unambiguous; no fuzzy name matching is performed. Reports without venue metadata remain visible in the coverage count and do not create a fictional additional venue.

The table supports CiteScore, SNIP, SJR, quartile, publisher, source H-index, metric year/category and metric provenance. These external measures are not computed from the corpus. A small corpus H-index is not substituted for a venue's provider-reported H-index.

## Import an external metric snapshot

Choose **Import venue metrics** and upload a UTF-8 CSV up to 5 MB that you are authorized to use. There is no automatic scraping or estimation. `Examples/synthetic_venue_metrics.csv` demonstrates the schema using fictional journals/providers and must not be treated as real metrics.

Required columns:

- At least one identity: `venue_id`, `issn` or `journal`.
- `year`: four-digit metric year.
- `metric_source`: the provider/source attribution for the reported values.
- `retrieved_date`: the date you retrieved/received this snapshot, formatted `YYYY-MM-DD`.

Optional columns: `citescore`, `snip`, `sjr`, `quartile`, `category`, `publisher`, `h_index`. Use finite nonnegative decimal values; H-index must be an integer. Leave an unavailable metric blank. Use `*` or `N/A` only when explicitly not applicable. A reported Q1–Q4 quartile requires its category; it cannot be interpreted as a universal category-independent ranking.

The dashboard selects the latest year available in the uploaded snapshot and displays that year; choose another year explicitly. If multiple metric rows match a venue/year, values remain blank as ambiguous until a category resolves the match or the input is corrected. Missing rows remain missing. A supplied mismatching identifier does not silently fall back to a similar title. Unmatched selected snapshot rows are counted.

Each import saves original bytes, parsed rows, a hash manifest and import time in the ignored local workspace. Failed imports preserve the previous valid snapshot. Uploading a replacement creates a new snapshot and changes the selected reference; it does not modify earlier snapshots or screening decisions. The table retains the original provider attribution, year, category and retrieval date. If metrics come from different providers, make that attribution explicit in `metric_source`; do not mislabel one provider's values as another's.

## Exports and CLI

**Export analysis** downloads a ZIP containing summary JSON/CSV, the complete ranked venue CSV, definitions, exact input-record snapshot, the original external-metric CSV when supplied, and artifact hashes. The scope is saved in the report. Exports include every venue in the selected scope, independent of the UI search/display limit. These may include actual research data; generated filenames and local output folders are ignored by Git and excluded from release packages.

```
slr analyze --input Examples/corpus_records.json --output outputs/corpus-example \
  --venue-metrics Examples/synthetic_venue_metrics.csv --metric-year 2025 \
  --metric-category Computing
```

The same corpus calculation produces the dashboard, CSV/JSON exports and the CLI's static HTML summary/venue tables. Existing network outputs remain available. Source-record snapshots accompany the exports so totals can be checked against the captured metadata.

Browser validation:

```
python Scripts/check_corpus_browser.py --output outputs/corpus-browser-qa
```

This uses isolated synthetic data and checks scope changes, ambiguity handling, category/year selection, missing versus not-applicable values, search, ZIP contents and mobile layout. It makes no live provider requests.

## Provider documentation

- OpenAlex describes primary source/venue identities and embedded publisher relationships in its [sources documentation](https://help.openalex.org/data/sources/).
- Elsevier describes CiteScore, SNIP and SJR as journal-level measures in [Measuring a journal's impact](https://www.elsevier.com/en-gb/researcher/author/tools-and-resources/measuring-a-journals-impact). Provider/year attribution is required; these measures are not replaced with calculations over this review's selected papers.


## Online lookup and free SCImago downloads

The Research analytics page now offers **Import SCImago** and **Fetch online**.

SCImago's [Journal Rankings](https://www.scimagojr.com/journalrank.php) offers a public **Download data** export. Select the desired year, download the CSV, then use Import SCImago and enter that year and the download date. Uploads are limited to 5 MB; filter the download if necessary. The application accepts the semicolon-delimited SCImago headers (`Title`, `Issn`, `SJR`, `SJR Best Quartile`, `H index`, optionally `Categories` and `Publisher`), handles decimal commas, normalizes ISSNs, and preserves the original download. The CSV's year is user-attested, not independently verified.

Category entries such as `Security (Q2)` remain separate rows. If only **SJR Best Quartile** is available, it is labelled **SJR best quartile / Best across reported categories**. A best quartile must not be assigned to every listed category. Identical metric rows for print and electronic ISSNs are treated as one match. Multiple different categories require a category selection. H-index is a captured provider value, not an annual or corpus H-index. CiteScore and SNIP are not supplied by this importer.

SCImago returned HTTP 403 to automated browsing during development. This implementation uses the public download/import route; it does not claim successful automated SCImago retrieval.

For official API lookup, set credentials in the dashboard server environment before starting it:

- `ELSEVIER_API_KEY`, with optional `ELSEVIER_INSTTOKEN`: [Elsevier Serial Title API](https://dev.elsevier.com/documentation/SerialTitleAPI.wadl), for annual CiteScore, SNIP and SJR. An API key does not itself guarantee entitlement. Only values explicitly returned for the requested year are accepted; provisional CiteScore Tracker values are excluded. Historical years may remain unavailable.
- `CLARIVATE_API_KEY`: [Web of Science Journals API](https://github.com/clarivate/wosjournals-python-client), for category-specific **JCR JIF** quartiles. Approved API access is required. Suppressed reports and wrong-year responses are rejected. JCR JIF quartiles differ from SJR quartiles.

Lookup is explicit, runs as an application background job, checks exact ISSNs, and logs errors in a downloadable session Markdown file. It targets 1–100 top venues in the selected corpus scope. Missing ISSNs are skipped. Credentials remain in request headers on the server and are not accepted from the browser. Complete failure preserves the active snapshot. A successful or partial lookup **replaces** the active snapshot; older snapshots remain locally available. It does not merge different providers into one row. To display combined provider values together, import a curated CSV with the appropriate sources documented.

Optional normalized CSV columns `source_url` (HTTPS, without credentials/query/fragment) and `quartile_basis` (`SJR`, `SJR best quartile`, `JCR JIF`, `JCR JCI`, `CiteScore`) support explicit attribution. Legacy rows without a basis display “Basis unspecified”. The table numbers source footnotes with provider, metric year, retrieval date and links. Export bundles include `metric-sources.md`; venue CSVs also carry source URLs and quartile bases. CLI HTML links its source-footnote file. Real metrics, downloaded files and provider credentials should remain private.
