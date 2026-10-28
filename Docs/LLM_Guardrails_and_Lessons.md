# LLM guardrails and lessons

This is a living engineering record for local and cloud AI in LitAtlas. Its purpose is to turn practical observations into explicit controls, actionable recovery and regression tests. It is not evidence that every model is compatible or that recommendations are scientifically correct.

## Evidence and terminology

Keep two layers:

- **Public lessons (this guide):** sanitized failure patterns, implemented controls, remaining work and user-facing remedies. No research questions, papers, credentials or raw private model responses.
- **Private evidence:** `Docs/Practical_Test_Log.md`, `Docs/LLM_Observation_Register.md` and the ignored `outputs/llm-validation/` register. Request/response files, model digests, prompt versions, validation errors and session Markdown stay in the originating workspace/output directory. Do not publish them automatically or include them in application release archives.

Use these evidence labels consistently:

| Label | Meaning |
|---|---|
| Observed | Encountered during actual local setup or inference |
| Source review + regression | Found by inspecting code and reproduced with a controlled test |
| Regression only | Exercised with synthetic/mocked inputs; not observed as a real-user incident |
| Anticipated | A plausible risk that still needs a test or observation |
| Validation limit | What the available checks do not establish |

**Format-valid, human-approved and methodologically suitable are different states.** A model health check cannot certify a research task. Never report a successful JSON response as an accuracy percentage or use a failed response as a valid abstention.

## Lessons from actual local use

The observed model was Llama 3.2 3B on Linux/WSL through a portable Ollama runtime. Results do not establish native Windows/macOS compatibility or the behaviour of other model families.

| ID | Observed issue | Current control | Researcher remedy / remaining work |
|---|---|---|---|
| LLM-001 | Local runtime unavailable before setup | Guided local setup, visible status and explicit model selection | Start/retry local setup or continue manually. Never silently send the request to a cloud provider. |
| LLM-002 | Portable runtime could not resolve required shared-library links | Archive digest checking, safe internal-link extraction and managed library-link repair | Inspect the setup log; retry the supported installer. Native-platform acceptance remains pending. |
| LLM-003 | A response contained blank required explanations | Strict task validation rejects it and preserves the original response | Inspect the error and explicitly retry or continue manually. Failed output is not an empty valid prediction. |
| LLM-004 | Recommendations analysed question wording rather than synthesizing review evidence | Task instructions and mandatory human review; no automatic knowledge-base learning | Review the unit of analysis. A reliable semantic suitability check remains to be developed and evaluated. |
| LLM-005 | Primary surveys/experiments were proposed as review synthesis | Human approval and proposal isolation | Reject inappropriate methods. Method-role and evidence-prerequisite checks remain planned. |
| LLM-006 | A structurally valid method was named “None” | Human review; no automatic execution or ontology update | Structural validation alone is insufficient. A versioned sentinel-method rule is pending; historical experiment outputs must not be silently rewritten. |
| LLM-007 | Generic network methods lacked the specificity needed to select an analysis | Evidence requirements and suitability require review | Identify network type, nodes/edges and available data before selecting an analysis. Automatic equivalence to a bibliometric method is not established. |
| LLM-008 | Question refinement introduced unrequested industry restrictions | Candidate-only suggestions, add/replace/edit/reject and separate final approval | Review scope changes explicitly. Automatic detection of all unsupported assumptions remains unvalidated. |
| LLM-009 | Protocol prompt v1 returned repeated replacements for one field | Reject duplicate fields; cap response items by the number of available fields | Do not merge conflicting replacements automatically. Record the failed attempt and use a revised versioned prompt. |
| LLM-010 | Protocol prompt v2 expected JSON encoded inside a JSON string; the local model returned ordinary text | Prompt v3 uses native typed values and task-specific validation | Keep contracts simple. Never silently guess or repair a malformed value into an approved decision. |
| LLM-025 | An early appraisal response suggested a clinical risk-of-bias tool without evidence about the technical studies’ designs | Prompt now asks for design-appropriate tools; researcher review remains required | Treat suitability as unverified until study designs and tool scope are checked. This is an observed unsupported recommendation, not a validated judgment that a tool is always wrong. |
| LLM-011 | A format-valid protocol suggestion merely repeated the current text | Display unchanged suggestions; a human decision can be recorded without a fake amendment | Reject, retain or edit it. Successful inference does not demonstrate improved advice. |

Protocol v1/v2 failures and the successful v3 request remain separate records. The model weights were not fine-tuned. The frozen question-only experiment was not rewritten to apply later prompt changes.

## Controls tested with synthetic cases or source review

| ID | Failure pattern / limit | Implemented control | Status and limit |
|---|---|---|---|
| LLM-012 | Insufficient or unknown available RAM/storage | Conservative resource recommendations and server-side recheck before setup | Regression tested. GPU capacity and peak runtime memory are not measured; an out-of-memory incident was not observed in the practical run. |
| LLM-013 | Oversized source packet may be truncated or exceed context | Bounded local context, conservative UTF-8-byte input check and reserved output budget | Regression tested. This is not exact tokenizer accounting; automatic full-paper chunking is not implemented. |
| LLM-014 | Truncated, refused, invalid-JSON or wrong-shape output | Adapter completion checks, saved raw output and downstream task validators | Regression tested. Never import a partial object or assume parser success implies scholarly quality. |
| LLM-015 | Response belongs to another provider, model or saved request | Match request ID/hash and requested provider/model; record local model digest | Regression tested. A digest identifies weights, not capability or reproducibility of every generated token. |
| LLM-016 | Local endpoint points remotely or a model proxies to cloud | Loopback-only endpoint rules, redirects/proxies disabled, known cloud-backed tags/metadata rejected | Regression tested. No silent local-to-cloud fallback; explicit cloud consent remains separate. |
| LLM-017 | Researcher changes questions/criteria in another tab | Expected question-approval identity, criteria hash and protocol/history versions on actions | Source review + regression. Reload and review changed context; never silently rebind an old approval click. |
| LLM-018 | A delayed proposal or running search refers to superseded inputs | Stale-response checks, approval invalidation and authorization checks during retrieval/registration | Regression tested. Preserve historical artifacts; retry explicitly against current inputs. |
| LLM-019 | AI output attempts an out-of-section edit, unsupported adapter or date replacement | Field allowlist, ordinary protocol validators, capability registry and manual-only date entry | Regression tested in the protocol workflow. Not a general proof against prompt injection. |
| LLM-020 | Archive tampering, traversal or escaping links | Official asset digest verification and bounded safe extraction | Regression tested; no real tampering event observed. Do not disable verification to make installation succeed. |
| LLM-021 | Cancellation, restart or provider failure | Visible failure/interruption, cached downloads where supported and durable session artifacts | Recovery has tests; cached local restart was observed. There is no silent paid retry or automatic model substitution. |
| LLM-022 | API-key or private-content leakage | Session-only keys by default, optional OS credential storage, ignored workspaces and release/export boundaries | Tested with synthetic credentials. Native credential-store and live cloud-account acceptance remain incomplete. User-requested research exports intentionally contain research history. |
| LLM-023 | User input tries to instruct the model outside its task | Treat input as data; disable browsing/tools where unavailable; validate proposals; require human decisions | Partial controls. Adversarial evaluation is still required; do not label the application injection-proof. |
| LLM-024 | A local route is treated as blocked because no cloud key exists | Explicit local/cloud selection; local inference does not require a cloud key | Local path tested. Keep provider-specific setup and error messages distinct. |
| LLM-026 | CPU-only generation took tens of seconds on the test machine | Background jobs and visible status | Validation limit. Timings and model-allocation figures are observations, not throughput, peak-memory or concurrent-user guarantees. |


The browser test environment also required a missing Linux browser library. That was QA infrastructure, not a demonstrated dependency required by researchers to run Llama. Avoid turning test-host problems into misleading installer instructions.

## Required record for every future AI practical test

Record one stable observation ID per failure pattern, and link each attempt separately:

1. Session and UTC timestamp; application revision/working-tree identity where available.
2. Stage/task, prompt/schema version and saved request hash.
3. Provider, exact model identifier, weight digest where available, runtime version and relevant hardware/context/output budget.
4. Expected behaviour and actual outcome. Separate transport, formatting, scope, methodological suitability and user-interface issues.
5. Error class/message and local evidence references/hashes. Preserve the original request/response; never overwrite a failed attempt with a successful retry.
6. Cause, with confidence: established, suspected or unknown. Do not present a guess as a diagnosis.
7. User-facing recovery, developer remedy, guardrail status and regression-test reference.
8. Re-test result and remaining limitation, including whether the manual path and prior approvals remained intact.

Use `observed`, `source-review-and-regression`, `regression-only`, `anticipated` or `validation-limit` for the evidence class, and `implemented`, `partial`, `planned` or `unresolved` for the guardrail status. Keep retries, invalid output, valid abstention and no-change suggestions distinct. A changed prompt or validator creates a new version/new run, not an edit of an earlier benchmark.

Current per-request manifests and session Markdown provide operational evidence. The consolidated private observation register is curated; a unified automatic classifier/export of every observation is **not yet implemented**. Future sessions must append to the register and practical log. Do not imply that documenting a lesson has implemented its guardrail.

## Priority follow-up

- **P1: semantic checks and curation.** Versioned sentinel-method rejection, review-level versus primary-study role checks, evidence/data prerequisites, and researcher-confirmed scope changes. Evaluate false positives across disciplines before enforcing broad rules.
- **P1: task compatibility checks.** A new local model should pass the actual topic, protocol and extraction contracts, not just a generic connection test. Keep compatibility separate from quality certification. The guided installer currently offers a curated catalogue; arbitrary model installation is not claimed.
- **P1: structured observation collection.** Produce a private, structured per-attempt summary linked to existing session artifacts; provide a researcher-reviewed redacted support export. No automatic telemetry or upload of papers/prompts.
- **P2: context and platform coverage.** Tokenizer-aware budgeting, explicit chunking with source anchors, cancellation/timeout/OOM recovery, and native Windows/macOS and varied-hardware acceptance.
- **P2: independent evaluation.** Compare models/prompts on development examples, then untouched discipline-balanced cases. Measure suitability, coverage, unsupported assumptions and failure rates separately. Never train and evaluate on the same examples and call that general accuracy.


### Background request visibility and duplicate protection

Task-specific question, protocol and evidence generation jobs now expose actual running/complete/failed state in a persistent accessible UI region. Generation requests for the same review are serialized by a backend guard as well as disabled controls. Completion polling does not overwrite unsaved question/protocol drafts; suggestions remain pending human review. Retries require explicit action and existing consent. Controlled in-process provider tests cover background navigation, completion, provider failure and preservation of unsaved edits; this is workflow validation, not additional evidence of a real model's accuracy or reliability.
