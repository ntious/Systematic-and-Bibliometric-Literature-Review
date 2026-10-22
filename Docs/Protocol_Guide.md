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
