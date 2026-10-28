# Analysis knowledge base — initial curated prototype

LitAtlas now has a dedicated local SQLite knowledge graph and a provisional recommendation service. This is a cross-disciplinary foundation, not a validated universal ontology, an OWL reasoner, or 32 executable analysis modules. It does not modify screening/evidence databases or call an AI provider. Dashboard integration, verified evidence-ledger field binding, approval persistence and execution adapters remain future work.

## Research foundations

The initial source register contains 13 resources, inspected on 2026-10-23 through available pages, abstracts and identified sections. This was a targeted methodological search, not an exhaustive systematic review of recommendation systems. Some publisher pages were inaccessible; the relevant abstracts or institutional records were used instead. Source access is not equivalent to expert validation.

- [STATO](https://stato-ontology.org/) describes statistical concepts, application conditions, inputs and outputs. The [maintainer repository](https://github.com/ISA-tools/stato) identifies its CC BY 3.0 licence. We link to the resource; no OWL classes have been imported and no exact class equivalences are asserted.
- [OBCS](https://doi.org/10.1186/s13326-016-0100-2) models statistical workflows, including transformation and visualisation. Its examples support the architecture, not a claim that our recommendations are validated across disciplines.
- [Munn et al. (2018)](https://doi.org/10.1186/s12874-017-0468-4) relates question structures to review types; health-specific applicability is recorded.
- [Right Review (2022)](https://doi.org/10.1016/j.jclinepi.2022.03.004) provides structured synthesis-method selection; it does not validate automatic statistical-method assignment from keywords.
- [RETREAT](https://doi.org/10.1016/j.jclinepi.2018.03.003) highlights qualitative method-selection considerations beyond question wording.
- Cochrane Chapters [10](https://www.cochrane.org/authors/handbooks-and-manuals/handbook/current/chapter-10), [12](https://www.cochrane.org/authors/handbooks-and-manuals/handbook/current/chapter-12), [13](https://www.cochrane.org/authors/handbooks-and-manuals/handbook/current/chapter-13) and [14](https://www.cochrane.org/authors/handbooks-and-manuals/handbook/current/chapter-14) inform quantitative methods, displays, missing-evidence considerations and certainty assessment.
- [JBI](https://jbi-global.atlassian.net/wiki/spaces/MANUAL/pages/355860547) informs qualitative meta-aggregation.
- [Campbell evidence-map guidance](https://doi.org/10.1002/cl2.1125) informs evidence availability mapping.
- [VOSviewer documentation](https://www.vosviewer.com/documentation/Manual_VOSviewer_1.6.20.pdf) documents bibliometric relationships.
- [W3C PROV-O](https://www.w3.org/TR/prov-o/) is a provenance design reference; the prototype does not claim formal conformance.

Original brief annotations are included, not full articles. Literature support, local question mappings, eligibility checklists and execution availability are distinct. Source links and section locators require methodologist curation. No knowledge is taken from other users' private conversations or represented as empirical experience from those conversations.

## Graph structure

Stable local identifiers distinguish question intents, methods, required fields, human checks, outputs and sources. Relations include:

```text
Question intent -> candidate_method -> Method
Method -> documented_in -> Source with section locator
Method -> requires_field -> Field
Method -> requires_human_check -> Judgment
Method -> produces -> Output type
```

All intent mappings are `local_unvalidated_hypothesis`; all method records are draft and require methodologist review. Source evidence is not automatically evidence for the local mapping rule. Required fields are a preliminary checklist, not a complete statistical schema or formal proof of suitability. The seed version and canonical content hash bind the catalogue and each recommendation. Hashes detect accidental change, not malicious replacement with a recomputed hash.

## Use

Create a new knowledge database in an ignored local folder:

```sh
slr knowledge init --db outputs/analysis-knowledge/knowledge.sqlite
slr knowledge catalogue --db outputs/analysis-knowledge/knowledge.sqlite
slr knowledge recommend --db outputs/analysis-knowledge/knowledge.sqlite --question "How effective is tutoring compared with usual teaching?"
```

The last command proposes tentative intents and methods. It never records approval. To specify the researcher's interpretation:

```sh
slr knowledge recommend --db outputs/analysis-knowledge/knowledge.sqlite --question "Experiences of an effective programme" --intent experience
```

Repeated `--intent` values allow multiple aims. Explicit intents override phrase hints; they are declarations in this request, not authenticated or stored approval events.

Use `--method METHOD_ID` to ask about a specific catalogue entry. An unknown method is identified explicitly. A known method may lack intent fit. All execution states remain `not_integrated` in this service, including methods related to existing bibliometric commands: no automatic execution link is being claimed.

The catalogue lists accepted field/check identifiers. Repeated `--field` and `--check` arguments declare available data and completed checks. They do not inspect study-level values, verify independence or approve method suitability. Even with all declarations, the result is only a candidate requiring methodologist review.

Recommendations include catalogue hash/version, question, matched English phrases, confirmed declared intents, source links, missing fields, unresolved checks and limitations. Save private outputs under an ignored local directory. The service reads knowledge databases in read-only mode and refuses to initialise over an existing file.

## Limits and next development gates

Phrase matching is English-only, cannot reliably interpret negation or distinguish every ambiguity, and is not assigned a fabricated confidence percentage. Unknown wording yields no automatic recommendation; it does not establish that no suitable method exists. For example, prevalence and predictive-accuracy intents exist but have no dedicated statistical pooling implementation or complete method-selection route yet.

A robust next version needs:

1. Independent methodologist review of each source annotation, relation, prerequisite and formula before executable adapters are added.
2. A richer structured question profile: purpose, entities, comparator, outcome, context, study design, scale, dependence and intended inference.
3. Cross-disciplinary benchmark questions independently annotated by experts, including multilingual, negated, ambiguous and unsuitable cases. Evaluate inappropriate suggestions and abstention as well as coverage; keep evaluation questions separate from rule development.
4. Binding to approved extraction snapshots, actual data validation and persisted researcher approvals; never infer eligibility from field names alone.
5. Individually validated execution modules, formula/parameter provenance, reference datasets and reproducible outputs.
6. Dashboard cards, manual overrides and explicit unsupported-method explanations.
7. Versioned amendments and impact review. New articles, AI suggestions or user feedback enter a draft curation queue; they cannot silently update accepted methodological knowledge.

Future terminology mappings to STATO/OBI and RDF/OWL export should use verified term identifiers and record mapping scope, source version and licence attribution. A custom node label is not an authoritative ontology term.

## Evaluate question-only recommendations

Use a frozen catalogue and source-anchored questions to evaluate the current rules before revising them:

```sh
slr knowledge-evaluate predict --catalogue catalogue.json --cases cases.json --output predictions
slr knowledge-evaluate score --predictions predictions/predictions.json --annotations annotations.json --output scores
```

Each case requires `case_id`, `question`, `cohort`, `discipline` and nonempty `anchors` (for example PDF page and original quotation). Only `question` enters the recommender. Each annotation requires the same case ID, distinct `observed_method_ids`, `annotator` and source `anchors`. Optional `outside_catalogue` records unsupported methods. Set `status` to `unresolved` with an empty observed-method list when classification is uncertain; that case stays in coverage counts but leaves the agreement denominator. Retain all inclusion/exclusion decisions separately.

Outputs use fresh directories and SHA-256 manifests; existing bundles cannot be overwritten. These hashes detect accidental edits, not deliberate tampering. Preserve original predictions when correcting the cohort. Keep PDFs, extracted text, questions and annotations in private local storage such as ignored `outputs/`.

Coverage measures whether a question receives any candidates. Observed-method overlap compares candidates with the annotated published methods; it does not establish accuracy or methodological suitability. The unranked catalogue has no top-k score. Use independent annotation and adjudication before claiming validation, and reserve fresh papers for later holdout evaluation. No evaluation command grants approval or executes the suggested analyses.

## Compare AI with the knowledge base and published methods

`slr knowledge-ai prepare --cases questions.json --output prepared` freezes one request per study's question set. Use explicit questions; keep objectives as a separately labelled experiment. Complete question subparts and verify quotations against source pages before freezing. Only question text enters provider input; source filenames, annotations and catalogue entries stay local. Tools and retrieval are disabled. Prior model exposure to a published question cannot be ruled out.

Configure `OPENAI_API_KEY` in the process environment without sharing it in chat, and choose an available model explicitly:

```sh
slr knowledge-ai run --provider openai --plan prepared/plan.json --model YOUR_MODEL --output ai-run
slr knowledge-ai compare --plan prepared/plan.json --run ai-run --baseline baseline/predictions.json --annotations annotations.json --output comparison
```

Generate `baseline/predictions.json` with `knowledge-evaluate predict` using exactly the prepared cases and a frozen catalogue. The AI proposes up to six methods per question set with rationale, required data, uncertainty and contraindications. Its output is unconstrained by catalogue method names. The comparison presents AI suggestions, catalogue candidates and provisionally observed published methods side by side, plus a review worksheet. Free-text method mapping and suitability require review; the command does not silently treat name differences as disagreement or report AI accuracy. The six-suggestion cap differs from the unbounded rule-based candidate list, so counts are not equivalent rankings.

A completed run can resume without repeating completed calls. An existing failed/incomplete request stops the run; inspect provider usage before explicitly starting another experiment. Requests, raw responses, requested/returned model, usage and hashes are saved locally. API calls may incur charges. Never promote suggestions into the ontology automatically: verify methodological sources, record prerequisites and exclusions, obtain researcher approval, version the change, and evaluate it on fresh holdout papers. These exposed examples are development material after curation.

The adapter uses the [official structured-output interface](https://developers.openai.com/api/docs/guides/structured-outputs). Structured output constrains format; it does not establish scientific correctness.

### Local and cloud model routes

The design supports two routes: locally run open models, and explicitly selected cloud providers. The experiment currently implements Ollama for installed local models and OpenAI for cloud calls. The Settings wizard also implements Anthropic, Google, Mistral and DeepSeek connections with provider-specific requests and model discovery; live access depends on account credentials. AI assistance remains optional.

For a locally installed model, run:

```sh
slr knowledge-ai run --provider ollama --plan prepared/plan.json --model YOUR_EXACT_INSTALLED_TAG --output local-run
```

The default Ollama endpoint is `http://127.0.0.1:11434`; `--base-url` accepts loopback origins only. No API key is required, no models are downloaded automatically, and the app never falls back to cloud generation. The model tag and installed digest are captured, with a separate output directory per provider/model. Cloud-backed Ollama tags/remote metadata are rejected; configure the Ollama server with cloud features disabled for offline use. Local runtime/hardware and model licensing remain the user's deployment choices. The dashboard Settings wizard provides resource-aware model selection and managed installation.

Both routes use the same question-only prompt/schema and comparison procedure. Record provider/model-specific differences in support, truncation and defaults. See the [Ollama chat API](https://docs.ollama.com/api/chat) and [installed-model listing](https://docs.ollama.com/api/tags).

For a frozen batch experiment, optional `--continue-on-error` records failed cases and moves on without retrying them. Previously failed requests stay failed. The run summary distinguishes accepted outputs from generation/validation failures. Comparison tables retain those failures explicitly; they are not abstentions or usable method predictions. Keep failed raw responses for auditing, and do not repair their contents or change the prompt mid-experiment.
