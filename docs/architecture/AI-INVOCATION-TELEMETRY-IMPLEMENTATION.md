# AI invocation telemetry — implementation note

**Branch:** `feat/ai-benchmark-telemetry-20261030`, stacked on `feat/temporal-hitl-v1`.  
**Status:** implementation candidate; awaiting exact-head CI.

## Implemented in this tranche

- Intelligence service captures one invocation ID per Analyst/Critic request.
- Measures wall-clock latency for the full model operation, including the single bounded Critic schema-repair request.
- Captures request count, retry count and HTTP status codes.
- Extracts OpenAI-compatible provider usage fields: prompt/input, completion/output, total, cached and reasoning tokens.
- Usage is marked `provider_reported` only when prompt, completion and total counts are valid non-negative integers. Missing/malformed usage remains null and `unavailable`; no character-based token estimates are made.
- Cost and pricing source remain null until a pinned provider pricing schedule or invoice export is configured.
- Bounds request context by `AIOPS_LLM_MAX_REQUEST_BYTES` (default 262144 bytes) and generated output by `AIOPS_LLM_MAX_OUTPUT_TOKENS` (default 4096).
- The existing evaluation tool attaches per-call telemetry to each case and calculates usage coverage, complete token totals, partial reported token sum, p50/p95 latency and retry totals. Token totals remain null if any call in the evaluation lacks provider-reported usage.
- The evaluation now scores corrective-proposal actionability separately: target CI correctness, allowlisted action type, evidence references, preconditions, expected postconditions, verification steps, rollback completeness, risk tier and advisory/human-approval flags. Four dataset cases pin expected target CI and action type; the unknown-only case expects no proposal.
- The existing Core evaluation ledger receives aggregate metrics through the current model-evaluation endpoint; the per-invocation detail is retained in the JSON report artifact.

## Explicit gaps

- Per-invocation rows are not yet persisted to a dedicated Core table; current durable ledger stores evaluation aggregates and report artifact URI.
- Per-tenant/per-incident hard token quotas and spend circuit-breakers are not yet implemented.
- Pricing is not configured; cost must remain `UNKNOWN_PRICING_NOT_CONFIGURED`.
- Provider-specific response usage contracts must be verified for each model endpoint. The generic OpenAI-compatible parser is not proof that every provider reports complete usage.
- The request-size bound is a byte cap, not a tokenizer-accurate input-token budget. It is not to be presented as such.

## Tests added

- Provider-reported token extraction and malformed/missing usage.
- Critic repair accounting across both model calls.
- Output token limit and request byte-budget enforcement.
- Complete versus partial usage aggregation, latency percentiles and unknown cost.

The CI workflow already runs `tests/test_intelligence_contract.py` and `tests/test_ai_eval_harness.py`; this branch must pass the full current-head workflow before the implementation is qualified.


## Corrective proposal benchmark

The deterministic provider now emits a fully structured, read-only `COLLECT_DIAGNOSTICS` action with a case-derived SAN or storage-pool target, evidence IDs, preconditions, measurable postconditions, verification steps and a no-effect rollback statement. The evaluator gates proposal actionability separately from general action safety. This is a contract benchmark, not a proof that a real model will produce equally correct actions.


## 2026-10-30 — benchmark experiment correction

The first real CPU experiment on the previous workflow head produced six failed evaluator repeats (three each for qwen3:4b and qwen3:8b), all with `ReadTimeout`. The Actions workflow had incorrectly ended green because it captured non-zero evaluator exits but did not fail after preserving the report artifact. These runs are **failed experiments**, not model-quality results; no token, latency or cost measurements were available.

The follow-up experiment now:
- Uses qwen3:1.7b and qwen3:4b as the bounded CPU comparison set; qwen3:8b is deferred from CPU CI after the observed timeout failures.
- Defaults to one repeat per model for the first diagnostic pass; operators may request 3 or 5 only after a successful baseline.
- Increases the per-call inference timeout to 300 seconds and the job timeout to 120 minutes.
- Caps generated output at 2,048 tokens and request context at 65,536 bytes for this experiment only. These are experimental resource controls, not tokenizer-accurate input budgets.
- Preserves JSON reports and exit-code evidence before a final fail-closed job step. Any non-zero evaluator exit or missing repeat now fails the job after artifact upload.
- Keeps model evaluation result distinct from workflow execution result. A successful workflow with a failed model gate is no longer possible for this benchmark.

The updated experiment still needs a fresh Actions run. No real-model PASS, token coverage, latency or cost is claimed until its exact-head artifacts are inspected. A low-resource model may complete inference yet fail the strict quality thresholds; that is a valid benchmark result.
