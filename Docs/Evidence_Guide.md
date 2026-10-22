# Evidence extraction and AI assistance (0.4.0)

## Scope and setup

This workflow takes human-included reports from a **completed** screening ledger. Initialize with a review-specific extraction/appraisal framework before introducing model output:

```bash
slr evidence init --screening-db outputs/screening-demo/review.sqlite --db outputs/evidence.sqlite --framework configs/evidence_framework.json
```

The framework is a JSON object with an `id`, a nonempty `fields` array (`id`, `description`) and an `appraisal` object (`id`, `description`, `domains`). Each domain supplies `id`, `description`, and allowed `judgments`. Choose an instrument appropriate to the review and document its version. The shipped framework is **illustrative only**, not a validated risk-of-bias instrument. There is no composite appraisal score.

Each evidence database saves the framework, criteria version, full screening snapshot, its hash, included report metadata and study links. The schema is frozen for that ledger. New criteria/frameworks require a new ledger; do not relabel old decisions as new ones. All write commands check that the original screening snapshot is still current. Rejection/revision in screening, changed criteria, or an unavailable screening file blocks new writes. Historical exports remain available with `scope_current=false`; they are visibly labeled historical and incomplete. The ledger currently remains bound to the original absolute screening path, so moving the screening database makes it historical until that path is restored.

Identities are trusted local labels inherited from screening, not authenticated users. Any assigned reviewer/adjudicator can propose or review evidence; this release does not enforce independent dual extraction or prevent self-review. Use your review protocol to assign responsibilities. Database triggers prevent ordinary updates/deletes but are not protection against a database owner bypassing the application.

## Add source text

```bash
slr evidence add-source --db outputs/evidence.sqlite --record R000001 --file paper.txt --kind fulltext --label "Article text supplied by reviewer"
```

Supported kinds are `fulltext`, `abstract` and `excerpt`. Supply UTF-8 text with form-feed characters (`\f`) separating supplied pages. Without separators it is one supplied page. These numbers describe the supplied text, not verified PDF pagination. If OCR or PDF conversion was used, check the text and preserve conversion provenance separately. No document download, PDF parsing or OCR occurs here.

Original byte hashes and immutable decoded page snapshots are retained. A UTF-8 BOM is removed on decoding; exports reconstruct normalized UTF-8 text and hash those exported bytes separately. Duplicate source bytes for the same report are rejected. Sources for excluded/unknown records are rejected. Existing sources do not change when the original file changes; attach a new labeled source to preserve a revision.

Quotes are checked on the exact supplied page and report. Matching uses literal text, preserving whitespace; it records the first matching character range (zero-based, end-exclusive) and the number of occurrences. It does not check whether that quote entails the proposed value. A human must assess semantic support, context, numerical meaning, uncertainty and appraisal judgments.

## Manual proposals

`slr evidence propose --db ... --task extract --record R000001 --actor alice --file proposals.json` accepts the response object below. Use task `appraise` and a configured domain key for appraisal. Partial sets of fields are allowed; missing fields remain `not_reviewed` in coverage.

```json
{
  "items": [
    {
      "key": "sample_size",
      "status": "reported",
      "value": "120 postgraduate students",
      "anchors": [{"source_id": 1, "page": 1, "quote": "120 postgraduate students"}],
      "evidence_ids": [],
      "uncertainty": "low",
      "rationale": "Reported sample in the supplied methods text."
    }
  ]
}
```

Every item requires exactly those keys. `uncertainty` is `low`, `medium`, `high` or `unknown`; these are qualitative statements, not calibrated probabilities. A reported value requires nonempty text and at least one matching source anchor. For appraisal it must also match that domain's allowed judgment labels.

Use `status: "not_reported"`, `value: null`, an explanation and usually empty anchors when the supplied sources do not establish a field. This is different from zero, a negative finding, or absence in the complete article. Human reviewers must confirm the scope of that uncertainty before approval. Effect sizes remain source-reported text with scale, interval and context; the software does not invent, calculate or pool effect estimates.

## Prepare model requests

```bash
slr evidence prepare --db outputs/evidence.sqlite --record R000001 --task extract
slr evidence prepare --db outputs/evidence.sqlite --record R000001 --task appraise
```

The JSON printed to stdout contains the saved `request_id`, `request_sha256` and packet. The packet includes instructions, task, criteria, framework, expected keys, source pages, output schema and prompt version (`evidence-v1`). The digest covers the full packet. A character budget (60,000 by default) rejects oversized input instead of truncating it silently. Choose a labeled excerpt or explicitly raise `--max-chars` when appropriate.

Source text is included as data, and instructions explicitly tell the model to ignore instructions inside it. The model receives no tools. This reduces accidental instruction following but does not guarantee semantic correctness; all imported outputs remain proposals.

## Optional model runner

```bash
# Set OPENAI_API_KEY through your environment; do not put it in a tracked file.
slr evidence run-ai --db outputs/evidence.sqlite --request 1 --model YOUR_MODEL_ID --output outputs/model-response-1
```

Choose an available model supporting structured outputs. There is no default model or automatic model substitution. This command sends the saved packet, including supplied source text, to OpenAI. Manual entry, prompt export and importing responses do not make network requests. Credentials are used only in the authorization header and are not saved. The command requests `store: false`; this flag alone is not a guarantee of zero provider retention.

The runner uses the Responses API with strict JSON Schema in `text.format`, no tools, a 4,096 output-token budget by default (`--max-output-tokens`), and a 90-second HTTP timeout. There is no automatic retry: a timeout may occur after processing has begun. Incomplete, refused and invalid JSON outputs fail without importing any proposals. An existing output directory is never overwritten.

A successful run saves the exact provider request body (excluding credentials), prepared packet, raw response, response envelope and a hashed manifest. It records the requested and returned model, response ID, time and usage when provided. Inspect `response.json`, then explicitly import it:

```bash
slr evidence import-ai --db outputs/evidence.sqlite --file outputs/model-response-1/response.json
```

The built-in runner is tested with mocked responses. It was not exercised against a paid model during implementation; availability, model schema support and research quality require evaluation with your selected account/model.

### Other model providers

Run a prepared packet through your chosen system and construct an envelope with:

```json
{
  "request_id": 1,
  "request_sha256": "THE_SAVED_REQUEST_HASH",
  "provider": "your-provider",
  "model": "exact-model-or-snapshot",
  "generated_utc": "2026-10-22T12:00:00Z",
  "response_id": "optional-provider-response-id",
  "usage": null,
  "output": {"items": []}
}
```

Provider/model/timestamp are declared metadata for external imports, not independently verified facts. The import validates the saved request/hash, item schema, field/domain keys and source quotes. AI items cannot cite source IDs or supporting evidence IDs absent from their saved request. New sources require a new request. Duplicate response imports are rejected. A batch with a schema error is rolled back; valid but ungrounded items remain flagged and cannot be approved.

## Human review and corrections

```bash
slr evidence status --db outputs/evidence.sqlite
slr evidence review --db outputs/evidence.sqlite --proposal 1 --actor bob --decision approve --rationale "Checked quote, context and interpretation" --revision 0 --support-confirmed
```

All proposals start pending, including manual ones. Approval requires explicit support confirmation and no source/grounding flags. The actor and review rationale are saved. Rejections require a rationale too. `--revision` must equal the current number of review events for that proposal, so competing writes cannot silently overwrite a decision.

To correct a value, submit a new proposal. If an approved item already occupies that report/task/field, reject the old one with its current revision before approving the replacement. Reviews are appended, not edited. A rejected item may be reviewed again using the new revision. There is no automatic approval based on model uncertainty, quote matching, or model choice.

Screening is unchanged by every evidence command: model output never includes a callable path that finalizes inclusion/exclusion. The working digest includes only currently human-approved, unflagged items. Flags and rejected/pending proposals remain available in the full history.

## Gap hypotheses

```bash
slr evidence prepare --db outputs/evidence.sqlite --task gaps
```

This task requires approved, reported extraction items and supplies their IDs, report/study IDs, values and anchors. Responses use `key: "hypothesis"`, `status: "reported"`, a textual value, empty `anchors`, and a nonempty list of supporting `evidence_ids`. These IDs must have been in the saved request and remain approved. Hypotheses require human review and stay labeled hypotheses even after approval.

If a supporting approval is revoked later, the hypothesis becomes flagged and leaves the digest until support is restored or the hypothesis is rejected/replaced. Sparse evidence is not proof of an empty research area. The task does not search the literature independently, establish novelty, or verify global research gaps.

## Exports and completion

```bash
slr evidence export --db outputs/evidence.sqlite --output outputs/evidence-report
```

Exports contain:

- `evidence.json`: sources, requests, batches, proposals, review history and the saved screening scope.
- `evidence.csv`: currently approved/unflagged extraction, appraisal and hypothesis items, including anchors and producer/reviewer metadata.
- `coverage.json`: every configured field/domain for every included report, distinguishing not reviewed and approved not reported.
- `framework.json` and `source-N.txt`: reproducible configuration and decoded source pages.
- `records.json/csv/bib/ris`: bibliography metadata for the scoped included reports, whether or not all have approved evidence.
- `synthesis.md` and `report.html`: a citation-linked, human-editable working digest of approved items. No model-written connective claims are added automatically.
- `manifest.json`: artifact hashes, package version, export status, scope status, evidence completion and pending/flagged counts.

`status: complete` means export files were written successfully. `evidence_complete: true` additionally requires a current screening scope, an approved reported/not-reported entry for every extraction field and appraisal domain, and no pending or active flagged proposals. It does not certify study validity, adequate source coverage, independent dual extraction or publication readiness. A not-reported appraisal remains insufficient information, not a low-risk judgment. Any source-kind/page limitations remain in the evidence history.

The Markdown digest is a structured evidence list, not automatic narrative synthesis or meta-analysis. Every reported item identifies its evidence ID and source page/character range. Review citations and interpretations before writing publication prose.

## Complete offline example

```bash
python Scripts/evidence_demo.py --output outputs/evidence-example
```

This creates synthetic retrieval/screening data, attaches two supplied text pages, proposes and reviews nine extraction fields and three appraisal domains, prepares a model packet without sending it, and exports the digest. No real study, model output or paid request is involved.

## Official API references

The optional runner follows the [OpenAI structured-output guide](https://developers.openai.com/api/docs/guides/structured-outputs) and [Responses create reference](https://developers.openai.com/api/reference/python/resources/responses/methods/create). Schema adherence does not establish factual accuracy or semantic support.
