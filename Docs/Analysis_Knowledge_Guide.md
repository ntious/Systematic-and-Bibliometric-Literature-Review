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
