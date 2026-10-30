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
