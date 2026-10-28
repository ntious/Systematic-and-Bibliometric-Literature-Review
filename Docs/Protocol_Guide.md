# Review protocol guide (PRISMA-P)

`slr protocol` keeps a structured review protocol and checks it against the 26 PRISMA-P 2015 checklist items (Moher et al., *Systematic Reviews* 2015;4:1). It drafts copy-and-paste fields for PROSPERO and the OSF Generalized Systematic Review Registration template. Once saved to a review ledger, every later change is an append-only amendment linked to the criteria version in force.

## Write and check a draft

Start from [configs/example_protocol.json](../configs/example_protocol.json). It is a complete, clearly synthetic example that matches `configs/example_criteria.md`.

```bash
slr protocol check --file my_protocol.json
slr protocol export --file my_protocol.json --output outputs/protocol-draft
```

Drafts may be incomplete. `check` validates field names, types, dates (`YYYY-MM-DD`), the question framework (`PICO`, `PECO`, `PCC`, `SPIDER`, `other`) and the stage (`planned`, `searching`, `screening`, `extraction`, `synthesis`, `completed`). Unknown fields are rejected, so a typo never silently drops content. The checklist reports each item as `reported`, `missing` or `not_applicable`:

- 1b (update) applies only when `is_update` is true.
- 5c (sponsor role) applies only when a sponsor is named (not "None").
- 15b/15c (quantitative methods, additional analyses) do not apply when `synthesis.quantitative` is false. 15d (non-quantitative summary) does not apply when it is true. If it is unset, all three stay applicable.
- 3a needs every author's name and affiliation, plus at least one `contact: true` author with an email.

"Reported" means the item has content. It does not judge methodological adequacy.

## Registry drafts

`export` writes `prospero-fields.md/json` and `osf-fields.md/json`. Each row gives the registry field, the drafted value, `filled` or `needs_entry`, and the protocol field it came from. Question elements are matched case-insensitively. For example, `Population`/`Participants`/`P` fill PROSPERO's population field, and `Intervention`/`Exposure`/`Concept` fill its intervention field.

Registry forms change. The labels are a best-effort mapping: verify each one against the current form before you submit. Nothing is submitted automatically. PROSPERO accepts reviews only within its stated scope (generally reviews with a health-related outcome), so many education or computing reviews belong on OSF or another registry.

## Save to a review ledger and amend

```bash
slr protocol save --db outputs/demo.sqlite --file my_protocol.json --actor carol --expected-version 0
# Later, after editing the file:
slr protocol save --db outputs/demo.sqlite --file my_protocol.json --actor carol --expected-version 1 \
  --amendment "Widened publication years to 2018-2025" --rationale "Pilot screening found key 2018-2019 studies"
slr protocol status --db outputs/demo.sqlite
slr protocol export --db outputs/demo.sqlite --output outputs/protocol-v2
```

- Any assigned reviewer or the adjudicator can save. `--expected-version` must equal the current protocol version (0 before the first save), so concurrent edits are rejected rather than lost.
- The first save is the initial protocol. Every later save needs `--amendment` and `--rationale`. The changed top-level sections are computed automatically, and saving unchanged content is rejected.
- Each version stores the canonical JSON, its SHA-256 hash, the actor, the UTC time and the current **criteria version**. Database triggers block updates and deletes. As with the other ledgers, this is tamper-evident record keeping, not protection against someone with file access.
- `status` lists `criteria_links` (which protocol versions were saved under each criteria version) and `undocumented_criteria_revisions`. Those are the criteria versions after version 1 that have no protocol version or amendment saved under them. Run `slr review criteria` and then save an amendment that explains the change, so the deviation is documented.
- Older ledgers work unchanged. The protocol table is created on the first save, and reading status never modifies the database.

A ledger export (`slr protocol export --db`) adds `protocol-history.json` and `amendments.md`. `slr review export` also includes `protocol.json` (current protocol, history and criteria links) whenever a protocol has been saved.

## Guided protocol and pilot workflow in the dashboard

After approving the current topic and research questions, open **Review protocol**. Seven sections guide eligibility and publication period, information sources, source-specific queries, screening, extraction, appraisal and synthesis. Publication dates start blank; the researcher enters the intended range and its rationale. Automated adapters are OpenAlex, Crossref and PubMed, which retrieve metadata. Other sources can be documented as manual searches without implying that the application searches them or supplies their full text.

Save the draft, then approve each section. Extraction, appraisal and synthesis may instead be marked not applicable with a substantive rationale. A separate final action approves the exact protocol version. New questions, criteria or relevant protocol changes invalidate affected approvals. Each action checks the question approval and criteria shown in that browser tab; stale tabs must reload. Saving eligibility with changed wording creates a new screening-criteria version and screening pass, retaining old decisions.

Final protocol approval enables a bounded pilot, not a main search. Pilot results remain separate from the study library. Inspect their exact source-specific queries, period, caps, source diagnostics and sample records; then record notes and approve the strategy or request revisions. Only a current protocol and researcher-approved pilot strategy permit the dashboard main-search action. Source/queries that fail make the governed run fail visibly; partial results remain in session artifacts instead of becoming an approved corpus. Existing nonempty main corpora are preserved; combining and rerunning them is a later workflow increment.

The backend checks authorization before retrieval, between queries and before corpus registration. Changes during a run can make its results historical and prevent registration. Protocol, plan, question and criteria histories are retained when an import or approved main search replaces the active corpus ledger. Earlier/imported corpora remain screenable and are labelled as unbound or externally assembled, without retrospective approval.

Optional **Ask local AI for suggestions** uses the selected local model. Cloud configurations remain supported but require explicit per-request disclosure and consent. Only approved topic/questions, the chosen section, its field rules and relevant adapter capabilities are sent; PDFs and other protocol sections are omitted. The application supplies a versioned prompt. Proposals need individual accept/edit/reject decisions and cannot approve sections. Dates are excluded from AI replacements. Unchanged suggestions record a decision without a fake amendment. All errors and model requests/responses remain inspectable in session/history records.

Review ZIP exports include `protocol-approval-history.json` and the existing protocol/checklist/registry drafts. Screening exports include `protocol-approvals.json`. Presence of text, approval or a successful model response does not establish methodological adequacy.

**Scope:** these gates govern dashboard searches and `slr plan` searches through the shared authorization service. Standalone live commands require explicit `--unregistered` and do not grant protocol approval; `slr review init` refuses unbound live or separately approved runs that would lose their approval history. Existing review databases and imported external libraries remain accessible with their provenance labels. Low-level Python retrieval adapters remain unbound utilities. The PRISMA-P reporting checklist and seven workflow-section approvals are different checks.


## Review-bound CLI workflow

Create an empty review before searching. Use private workspace paths and replace synthetic examples with your own reviewed content:

```bash
slr review create --db workspaces/review.sqlite --name "My review" \
  --topic "My topic" --question "My research question?" \
  --reviewers Alice Bob --adjudicator Carol --criteria configs/example_criteria.md
slr questions status --db workspaces/review.sqlite
slr questions approve --db workspaces/review.sqlite --actor Alice --expected-revision 1
slr plan status --db workspaces/review.sqlite --output workspaces/context-1.json
slr plan save --db workspaces/review.sqlite --actor Alice --context workspaces/context-1.json \
  --file configs/example_governed_protocol.json
```

The new example is synthetic and workflow-complete; it is not a methodologically adequate protocol or a complete PRISMA-P report. Its query, dates, criteria and methods must be replaced or deliberately reviewed. Saving eligibility changes executable criteria and starts a new screening version. To revise questions, use `slr questions save --file DRAFT.json --actor LABEL --expected-revision N`; the file contains `topic` and a `questions` array. A topic-only starting point is supported.

Before **each** approval, read the current plan and save a new context file. Review that section's actual contents, then act against that exact inspected state:

```bash
slr plan status --db workspaces/review.sqlite --output workspaces/context-2.json
slr plan approve-section --db workspaces/review.sqlite --actor Alice \
  --context workspaces/context-2.json --section eligibility
```

Do the same for `sources`, `search`, `screening`, `extraction`, `appraisal` and `synthesis`; do not bulk-approve sections without reviewing them. `not-applicable --section ... --rationale ...` is available only for the last three sections. A later protocol save needs `--description` and `--rationale`. `revoke --target SEQUENCE --rationale ...` preserves the withdrawn decision in history. Status output includes private research context and is never overwritten by `--output`.

After all sections are current, inspect a fresh context and use `slr plan approve-final`. Inspect another fresh context before executing a bounded pilot:

```bash
slr plan run --db workspaces/review.sqlite --actor Alice --context workspaces/context-for-pilot.json \
  --kind pilot --pilot-limit 5 --output runs/pilot-1
slr plan inspect-pilot --db workspaces/review.sqlite --run-id RUN_ID_FROM_PILOT_OUTPUT
```

Inspection verifies the recorded pilot manifest and artifacts and displays source-specific queries, caps, diagnostics and sample records. Read these and the session log. If the strategy fits, inspect a fresh context and record `slr plan review-pilot --db ... --actor ... --context ... --run-id ... --decision approve-strategy --notes ...`; otherwise choose `revise` and amend the protocol.

Only then use `slr plan run --kind main` with another inspected context and new output directory. It registers results **in the same empty ledger**, preserving question, criteria, protocol and approval history. No provider request is made when approval prerequisites are missing. A changed protocol or revoked pilot review blocks registration. Existing nonempty corpora and decisions are preserved. Do not modify a review concurrently from CLI and a running dashboard; a stale workspace retrieval pointer is rejected before import rather than dropping records.

Direct `slr --config ... --unregistered` and `slr pipeline --plan ... --unregistered` remain available for exploration. They are labelled unbound, and `slr review init` will not use them to create an approved workflow. Imports do not prove that an external systematic search was executed. Existing databases can still be opened and screened without fabricating approval.

Empty-review publication uses a same-filesystem hard link to avoid overwriting another creator's database. This path was exercised on Linux/WSL; native Windows/macOS and filesystems without hard-link support remain acceptance work. If publication fails, the newly created staging directory is cleaned up and an existing destination is preserved.
