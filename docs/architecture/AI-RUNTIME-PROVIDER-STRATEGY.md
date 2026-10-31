# AIOps2 AI runtime provider strategy

**Status:** Architecture decision; implementation gate  
**Target runtime:** NVIDIA NIM / Nemotron 120B on the Debian host  
**CI runtime:** deterministic synthetic provider; optional Ollama lane  
**Internal lab:** controlled ChatGPT-assisted simulation  
**Safety:** advisory-only inference; no model-controlled execution

## 1. Decision

AIOps2 uses one Intelligence API contract and three explicitly separated provider environments. The provider is selected by deployment configuration, never by silent fallback.

| Environment | Provider | Purpose | What a PASS proves |
|---|---|---|---|
| Debian runtime / customer demo | NVIDIA NIM, Nemotron 120B | Real Analyst and Critic inference | The configured NIM endpoint actually answered and output passed the strict evidence/schema guards |
| GitHub Actions default CI | Deterministic synthetic OpenAI-compatible test provider | Fast, repeatable API, workflow, timeout, retry and safety tests | Contract and integration behavior only; no model quality claim |
| GitHub Actions optional experiment | Ollama with a pinned model | Local-model compatibility / diagnostic experiment | Only the exact Ollama model and run measured; not NIM qualification |
| Internal ChatGPT lab | Explicitly labelled simulated responses and synthetic datasets | UX, conversation design, scenario authoring and acceptance rehearsal | Product flow and contract review only; no AIOps runtime or Nemotron execution claim |

The test provider and ChatGPT lab are not model substitutes in the production runtime. Their output must never be labelled as NVIDIA, Nemotron, or a real provider response.

## 2. Common Intelligence contract

Analyst and Critic must use the same versioned request/response schemas in all environments.

Required request properties:
- incident/run identity and explicit execution mode;
- bounded evidence set with canonical evidence IDs and provenance;
- freshness metadata calculated by the service, not trusted from caller input;
- prompt and contract version;
- tenant/run scope and data-minimization rules.

Required response properties:
- strict schema validation; unknown properties rejected;
- claims grounded in supplied evidence IDs;
- hypotheses separated from facts, assumptions, unknowns and contradictions;
- Critic independently evaluates Analyst output and can reject it;
- actions remain advisory, require human approval and contain no executable shell or arbitrary tool instructions;
- execution_allowed=false for all model responses.

A provider error, timeout, invalid JSON, unsupported evidence reference, stale evidence, or schema failure must produce an explicit unavailable/failed state. Do not retry by silently switching provider.

## 3. Provider configuration contract

The Intelligence service should read provider configuration only from environment/secret injection:

- LLM_PROVIDER: explicit enum, for example nim, ollama, test.
- LLM_BASE_URL: provider API base URL; never hard-code the Debian host address.
- LLM_MODEL: exact model identifier reported by the provider.
- LLM_API_KEY: secret where the provider requires one; never print or log it.
- LLM_TIMEOUT_SECONDS: bounded request timeout.
- AIOPS_LLM_MAX_OUTPUT_TOKENS: output cap.
- AIOPS_LLM_MAX_REQUEST_BYTES: context byte cap.
- AIOPS_INTERNAL_TOKEN: service-to-service authentication secret.

For the Debian NIM lane, set LLM_PROVIDER=nim and configure the NIM OpenAI-compatible URL and exact Nemotron model ID from the deployed NIM service. The endpoint path, model identifier, authentication mode, context capacity and GPU allocation must be discovered from the actual SRV-DEB-05 deployment before declaring runtime qualification. Do not assume a port, model alias or GPU availability.

For CI, set LLM_PROVIDER=test and point only to the isolated deterministic test provider. The default workflow must not require an external NIM endpoint, GPU, model download, or SRV-DEB-05 network access.

For the optional Ollama lane, use an explicit workflow input/profile and pinned model tag. A timeout or unavailable runner resource is a failed experiment, not a reason to mark the job green or silently fall back to fixtures.

## 4. Provenance and telemetry

Every invocation must record, without logging prompts or secrets:

- invocation ID and run/tenant correlation IDs;
- provider name, exact model identifier and endpoint class (not credentials);
- Analyst/Critic role, prompt version and response-contract version;
- start/end time, latency, HTTP status, request count and retry count;
- provider-reported prompt/input, completion/output, total, cached and reasoning token counts when available;
- token usage source (provider_reported or unavailable);
- model result status and bounded error class;
- cost and pricing source only when a pinned price schedule or invoice source exists; otherwise both remain null/UNKNOWN.

Never estimate tokens from characters or response length. Never infer a cost from an unverified price. A response produced by the test provider must carry provider=test and a synthetic/test marker in all reports.

## 5. Workflow integration

The Temporal Worker must invoke the Intelligence service for the Analyst and Critic stages; a generic stage-completed evidence record is not proof of model execution.

Analyst stage:
1. Fetch the canonical incident and only the Evidence IDs allowed for the Run.
2. Call the Intelligence analyze endpoint with the bounded evidence set.
3. Persist the full validated analysis, invocation telemetry and evidence references in the run ledger.
4. Mark the stage failed/blocked when the provider or evidence guard fails.

Critic stage:
1. Read the persisted Analyst result, not a browser-supplied or transient replacement.
2. Call the independent critic endpoint with the same evidence set and exact Analyst record.
3. Persist the critique, invocation telemetry and disposition.
4. A rejected/unsupported analysis cannot pass Policy or create a remediation proposal.

Both stages must be idempotent under Temporal retries. Persist invocation attempts separately or use stable stage-attempt identifiers so retries do not overwrite the audit trail.

## 6. CI test matrix

Required deterministic tests:
- provider selection is explicit and unknown provider values fail closed;
- no configured provider returns an unavailable state, not a fabricated answer;
- no silent NIM → Ollama → test-provider fallback;
- provider timeout, connection refusal, 4xx/5xx, malformed JSON and schema-invalid output;
- missing provider usage stays null/UNKNOWN;
- invalid, duplicate, stale, future-dated and cross-Run evidence references;
- Critic rejects unsupported claims and cannot promote an adverse decision during schema repair;
- retry idempotency and invocation audit persistence;
- DEMO/REPLAY/STORY never create LIVE approval or effect receipts;
- no model response can set execution authority.

The synthetic provider is deterministic and must not inspect test answer keys or expected labels when constructing output. It is a protocol fixture, not a model evaluator.

## 7. NIM runtime acceptance on Debian

The NIM lane is not qualified until the following are captured from the actual Debian host:

- deployed NIM container/image version and digest;
- exact Nemotron 120B model name/revision and serving configuration;
- API readiness and authenticated health response;
- GPU model/count, available VRAM, utilization and serving placement;
- concurrency, context and output limits;
- Analyst and Critic invocation IDs, provider usage, latency and HTTP status;
- at least one end-to-end ACME SAN → Payments synthetic incident using real NIM responses;
- independent Critic challenge and persisted Policy/HITL disposition;
- sanitized run evidence bundle and reproducible test command.

A healthy NIM container alone is not an application-level PASS. A single successful completion is not a quality benchmark. Quality, latency and cost claims require a pinned dataset/prompt/model configuration and repeated measured runs.

## 8. Current implementation boundary

The repository contains a reusable Intelligence service and deterministic test provider in the stacked AI/HITL development line (PRs #194 and #196). Those changes are not yet proven integrated into the clean main-based PR #214 branch. They must be ported in bounded commits with shared evidence contracts, Compose wiring, Worker invocation and exact-head CI.

Until that integration is complete:
- portal and run views must not claim Analyst/Critic executed merely because a workflow stage exists;
- missing runtime model integration must be displayed as NOT_CONNECTED / NOT_QUALIFIED;
- synthetic storyboards must remain labelled synthetic;
- LIVE execution remains disabled.

## 9. Exit criteria for the first demonstrable vertical slice

- [ ] One canonical ACME incident and Run ID.
- [ ] Current-state synthetic observations persisted with provenance.
- [ ] Twin impact path resolves to the Payments business service.
- [ ] Real NIM Analyst invocation persisted with evidence citations and telemetry.
- [ ] Independent real NIM Critic invocation persisted with objections/disposition.
- [ ] Policy decision and HITL state visible in the Portal timeline.
- [ ] GLPI ticket is read back from the real GLPI API and correlated to the same incident/Run, or explicitly shown as not connected.
- [ ] Simulation has no real effect receipts.
- [ ] Run verifier emits a sanitized evidence bundle.
- [ ] CI contract tests pass independently of NIM; NIM runtime qualification is a separate gate.
