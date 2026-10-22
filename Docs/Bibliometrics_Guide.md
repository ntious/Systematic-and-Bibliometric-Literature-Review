# Bibliometric analysis methods (0.3.0)

## Run an analysis

```bash
slr analyze --run outputs/live-review --output outputs/analysis
python -m pip install -e '.[analysis]'
slr analyze --input Examples/bibliometrics_records.json --output outputs/bibliometrics-demo --figures
slr analyze --db outputs/review.sqlite --output outputs/included-analysis --figures
```

Choose exactly one input. `--run` verifies a completed retrieval/import manifest and reconciles its records/duplicate counts. `--db` takes a transactional snapshot of screening-included reports and saves the criteria version and full snapshot; incomplete screening is rejected unless `--allow-incomplete` is set. `--input` accepts normalized JSON directly and labels its upstream provenance unverified. All outputs require a new directory. Analyses do not modify input records, review databases or earlier runs.

Analysis counts reports, not underlying studies. Multiple reports linked to the same study in a screening ledger remain separate bibliometric documents. Before analysis, normalized DOI duplicates are removed using the existing conservative policy: first metadata wins, provenance is retained, and other metadata remains in `input.json`. Duplicate records without a valid DOI require human review.

## Metadata and coverage

The shared Record schema adds `author_ids`, `keywords`, `references` (string arrays) and nullable `reference_count`. All default to empty/unknown for older data. Author IDs are aligned with author names; unknown positions use empty strings. Older saved retrieval manifests and screening ledgers remain readable. Existing old runs cannot acquire missing references automatically; retrieve anew or create an enriched import and retain your enrichment provenance.

- OpenAlex retains author ORCID/OpenAlex IDs, supplied keyword labels and referenced-work IDs. These are provider metadata, not necessarily author-supplied keywords.
- Crossref retains author ORCIDs and DOI-bearing reference entries plus the provider's reported reference total, when supplied. Unstructured references remain in raw API responses. Broad subject classifications are not relabeled as keywords.
- PubMed retains available author ORCIDs, keyword-list entries and DOI identifiers in reference lists. MeSH descriptors are not silently treated as keywords. XML/raw responses retain additional fields.
- CSV supports `keywords`/`Author Keywords`, `references`/`Cited References`, `author_ids`, and `reference_count`, in addition to the earlier fields. String arrays can be JSON arrays; keywords/references also accept semicolon-separated entries. Use JSON arrays for author IDs with unknown positions. RIS retains repeated KW and CR tags. CSV/JSON preserve author IDs; the basic RIS exporter does not encode positional author IDs or reference totals.

Reference strings must be explicit DOI (bare, doi: or resolver URL), OpenAlex work ID/URL, or pmid:/PubMed URL. The software does not guess DOI matches from unstructured citations. Such strings remain in the input snapshot and count as unresolved entries. DOI strings embedded in larger bibliographic text require explicit preprocessing; preserve an audit trail of that step.

DOI and OpenAlex/PMID identifiers are joined only when a corpus record/provenance explicitly links them. Otherwise namespaces remain distinct, even when they might refer to the same work. Provider work-ID conflicts fail validation rather than choosing an arbitrary identity. Self-reference identifiers resolving to the citing record are removed. Repeated references in one report count once.

Author IDs prefer supplied ORCIDs or OpenAlex IDs. Otherwise names use Unicode NFKC, whitespace normalization and case folding. Name-only entries are not merged into identified authors just because names match. Homonyms may still merge in name-only data, and spelling/initial variants may split the same person. Inspect node tables before interpretation; this version does not implement curated alias mappings or fuzzy disambiguation.

Keyword matching also uses Unicode NFKC, whitespace normalization and case folding. No stemming, synonyms, title/abstract keyword extraction or model-generated labels are used. Do not combine heterogeneous keyword sources without considering what each provider supplies.

`coverage.json` reports unresolved entries, usable reference counts, author-ID availability, namespaces and a document-ID map. Each graph JSON reports reports with/without usable metadata and graph size before/after thresholds. Reference-list coverage means availability of at least one usable identifier, not completeness of the underlying bibliography. Compare each document's usable references with its nullable reported reference total and inspect raw data; absent lists never establish zero real references.

## Graph definitions and weights

All four graphs are undirected and use full counting. Within one input report, authors, keywords and references are sets, so repetitions cannot inflate counts.

| Network | Node | Raw edge count | Frequency used in cosine denominator |
| --- | --- | --- | --- |
| Co-authorship | Author identity | Reports shared by both authors | Reports per author |
| Keyword co-occurrence | Normalized keyword | Reports containing both keywords | Reports per keyword |
| Co-citation | Resolved reference identity | Input reports citing both references | Input reports citing that reference |
| Bibliographic coupling | Input report (`D000001`, etc.) | Unique usable references shared by the reports | Unique usable references per report |

With `--normalization cosine` (default), weight(i,j) = raw_count(i,j) / sqrt(frequency(i) * frequency(j)). `--normalization none` uses the raw count as the weight. Missing references cannot contribute to either numerator or denominator. A high cosine value from a sparse reference subset should not be interpreted as robust similarity.

`--min-occurrences 1` filters node frequency. In coupling, this is the number of usable references, rather than report occurrences. `--min-edge-count 1` filters the raw count, regardless of normalization. Thresholds are applied before normalization and clustering. Nodes meeting the frequency threshold remain in the graph even if isolated. Node tables provide degree and total retained edge weight (`strength`).

Clustering uses sorted asynchronous weighted label propagation: start with one label per node, visit nodes in lexical order, choose the neighboring label with the largest weight sum, retain the current label on a numerical tie when possible, otherwise choose the lexical minimum. Stop when no labels change or after 100 passes. Cluster labels are renumbered deterministically. The convergence flag, pass count and algorithm are saved. Isolates form separate clusters. This is a simple exploratory partition, not VOS clustering, modularity optimization or validated topical classification; ordering and thresholds can affect it.

Before pair construction, `--max-pair-events` (default 2,000,000) limits the total full-count pair events across all four graphs. Exceeding the budget fails without emitting a misleading truncated result. The budget is checked before frequency thresholds, so increasing thresholds alone does not avoid preprocessing costs. Select a smaller corpus or explicitly raise the budget after considering resource use.

## Hand-calculated synthetic example

`Examples/bibliometrics_records.json` is synthetic and is not research evidence. Three connected reports have:

| Report | Authors | Keywords | References |
| --- | --- | --- | --- |
| D1 | Alice, Bob | AI, Learning | x, y |
| D2 | Alice, Carol | AI, Ethics | x, z |
| D3 | Bob, Carol | Learning, Ethics | x, y, z |

A fourth report has Dana and an isolated keyword, with unknown year/references. The repeated AI keyword in D1 still contributes one occurrence.

- Alice and Bob share one report and each appear in two: raw co-authorship = 1, cosine = 1/sqrt(2*2) = 0.5.
- x and y are co-cited by D1 and D3; x appears in three lists and y in two: raw = 2, cosine = 2/sqrt(6).
- D1 and D2 share only x and have two usable references each: coupling raw = 1, cosine = 0.5.
- D1 and D3 share x and y: coupling raw = 2, cosine = 2/sqrt(6).

Tests assert these values independently of the implementation.

## Trends and citations

Publication trends count known publication years and separately report missing years. `keyword_years.csv` counts each observed keyword once per report per known year; it describes observed frequencies, not thematic evolution inferred by a model. The heatmap displays the top 12 keywords among reports with known years, breaking frequency ties lexically, and uses equally spaced columns for observed years. Missing keywords cannot be inferred as true absences.

Citation summaries stay separated by the retained record's provider. They report known and missing counts, the sum and mean of known counts, and the h-index of the known-count subset. These are corpus-level descriptive statistics, not author h-indices or field/age-normalized impact measures. All-missing citation statistics stay null; a known zero stays zero. Missing values are not imputed. Citation totals from different providers are not added together. Retrieval timestamps are available through input provenance; older provider snapshots can have different citation ages.

## Outputs and figures

Each network has JSON, nodes/edges CSV, and GraphML. The analysis also saves input/retained records, duplicates, source provenance, coverage, methods, summary tables, a local `report.html`, and a completion manifest with file hashes. Failed rendering/writes mark the output manifest failed. `documents.csv` maps internal report IDs to source identifiers and titles.

With the optional `analysis` extra and `--figures`, Matplotlib writes SVG and PNG for four networks, publication trends and keyword/year frequency. Graphs use sorted circular positions: geometric distances have no analytical meaning. Colors indicate clusters from the entire retained graph; the 20-color palette repeats for larger cluster counts. Edge width is proportional to the chosen normalized/raw weight plus a constant visibility offset. All nodes have the same display size.

`--max-figure-nodes` defaults to 40 (range 1–100). Graph previews select nodes by descending strength, then occurrences, then identifier, and show the induced edges. This display limit never removes nodes from data exports or changes clustering. Captions and `figures.json` state the subset, omitted nodes, data file and method settings; labels may be abbreviated but full labels remain in node tables. Citation/keyword/reference coverage should be assessed before sharing figures. Figures are reproducible in values and layout, not necessarily byte-identical across Matplotlib/font versions.

## Sources

Metadata contracts: [OpenAlex works](https://help.openalex.org/data/works/), [OpenAlex authorships](https://help.openalex.org/data/authorships/), [Crossref metadata schema](https://github.com/CrossRef/rest-api-doc/blob/master/api_format.md), and [NCBI E-utilities](https://www.ncbi.nlm.nih.gov/books/NBK25499/). For comparison with a dedicated bibliometric tool, see the [VOSviewer documentation](https://www.vosviewer.com/documentation); this implementation does not reproduce its layout, fractional-counting or normalization algorithms.
