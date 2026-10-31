# AIOps 2.0 — AI benchmark, token economics and usage governance

**Status:** benchmark design and implementation backlog. Existing evaluation harness is reused; missing telemetry must be instrumented before claiming token/cost results.  
**Purpose:** measure whether AI makes diagnosis and corrective proposals more accurate, safer, faster and cheaper—not merely more fluent.

## 1. Existing baseline to reuse

The existing `tools/evaluate_ai_core.py` + `eval/ai-core-cases.json` + `tests/test_ai_eval_harness.py` and Core `model_evaluation_runs` ledger are the starting point. The current dataset includes severity classification, stale evidence, contradictory evidence, prompt injection and Critic disposition cases. The evaluator already scores severity accuracy, grounding, freshness, action safety, injection resistance, contradiction detection, stale detection, Critic disposition and coverage. Existing default gates require strict grounding/freshness/action-safety/injection/contradiction/stale/Critic outcomes; preserve these until a versioned ADR justifies changes.

**Gap found in source review:** the evaluator records provider/model/prompt version and quality outcomes, but does not yet capture per-request latency or reliable provider-reported token usage/cost. The AI decision ledger records provider/model/prompt/evidence-set identity but not per-invocation token economics. Therefore token/cost benchmarking is NOT YET QUALIFIED.

## 2. Telemetry contract

Add a versioned `ModelInvocation` event/table through the shared provider client, not scattered instrumentation in each prompt.

Required fields:

- Identity: `invocation_id`, `tenant_id`, `incident_id`, `run_id`, `stage`, `trace_id`, `attempt`.
- Model: `provider`, `model`, `deployment`, `region`, `api_version`, `prompt_version`, `schema_version`, `retrieval_version`.
- Input: `dataset_version`, `evidence_set_hash`, `input_bytes`, `context_items`, `retrieved_chunks`, `max_context_tokens`.
- Usage: `prompt_tokens`, `completion_tokens`, `total_tokens`, `cached_tokens`, `reasoning_tokens`, `usage_source` (provider_reported / tokenizer_estimated / unavailable).
- Performance: `queue_ms`, `time_to_first_token_ms`, `latency_ms`, `retry_count`, `timeout`, `http_status`.
- Economics: `input_cost_usd`, `output_cost_usd`, `total_cost_usd`, `pricing_source`, `pricing_version`, `currency`.
- Outcome: `schema_valid`, `critic_validated`, `groundedness_score`, `citation_validity`, `policy_disposition`, `proposal_created`, `proposal_quality_score`, `abstained`, `error_class`.

Do not persist raw prompts, secrets, customer payloads or full retrieved documents in telemetry. Store hashes, safe dimensions and references. Missing provider usage is null/UNKNOWN, never zero. Estimated tokens/cost must be labelled and kept separate from provider-reported values.

## 3. Benchmark scorecard

| Dimension | Metric | Interpretation |
|---|---|---|
| Diagnosis | severity accuracy, top-1/top-3 root-cause accuracy | correct operational classification and hypothesis |
| Grounding | valid evidence reference precision/recall, citation validity | every material claim supported by accessible evidence |
| Temporal quality | freshness accuracy, stale/contradiction detection | no stale data presented as current |
| Safety | action safety, injection resistance, policy override resistance | no unsafe command or unauthorized action |
| Critic | false-accept rate, false-reject rate, defect recall | independent challenge catches flawed Analyst outputs |
| Proposal quality | target CI correctness, precondition completeness, postcondition testability, rollback completeness, actionability | a human can evaluate and verify the proposed change |
| Operational performance | p50/p95 latency, time-to-first-token, queue time, timeout/retry rate | usable within NOC workflow |
| Token economics | input/output/total tokens per call, per stage and per resolved synthetic incident | transparent consumption and hotspots |
| Cost efficiency | cost per valid analysis, per Critic pass, per safely resolved synthetic case | quality-adjusted cost, not cheapest response |
| Reliability | provider availability, malformed schema rate, fallback rate | predictable operation under provider faults |

Report every metric with denominator, dataset version, model/prompt version, run date and missing-data count. Do not average away failed cases or remove provider outages from the denominator.

## 4. Benchmark protocol

1. Freeze a versioned synthetic dataset with a SHA-256 hash. Keep hidden adversarial cases separate from prompt-tuning data.
2. Run the exact same cases against each provider/model/prompt configuration; record concurrency, temperature, max output, retrieval settings and hardware/runtime.
3. Execute at least three repeats for nondeterministic models; report mean, median, p95 and variance. Keep deterministic fixture runs separate.
4. Blind model names during scoring where feasible; use rule-based validators and human review for corrective action quality.
5. Include outage, rate-limit, timeout, truncation, malformed JSON, prompt injection, stale evidence, contradictory sources, missing evidence, wrong tenant and tool-output injection.
6. Validate Analyst and Critic independently. A Critic that shares the same model/prompt failure mode is not independent assurance.
7. Compare the best-quality configuration with a cost/latency-constrained alternative; no model is promoted on cost alone.
8. Persist report and evaluation ledger with exact dataset/model/prompt/policy/retrieval versions and artifact URI/checksum.

## 5. Token and spend controls

- Per-tenant, per-incident and per-run budgets; separate budgets for Analyst, Critic, RAG query, summarization and evaluation.
- Hard cap on input/context/output tokens, max retrieved chunks, max tool calls, wall-clock timeout, retries and concurrency.
- Truncate by semantic priority with explicit omission metadata; never silently drop critical evidence.
- Cache only immutable, tenant-scoped inputs keyed by model + prompt version + evidence-set hash + policy/retrieval version. Invalidate on evidence, ACL, prompt or policy change.
- Use small/local model for low-risk extraction/classification only after quality qualification; route complex/high-impact incidents to the best validated model. Never downgrade safety/critic gates to save cost.
- Stop/reject additional inference when budget is exceeded; return an explicit budget-exhausted state and hand off to human review.
- Alert on token/cost anomalies, retry storms, unusually large context, model/prompt drift and quality regressions.
- Price calculations require a pinned provider pricing snapshot or invoice/export. Do not hardcode assumed prices or use public list price as actual bill.

## 6. Corrective-proposal evaluation rubric

Score each proposal independently across:
1. CI/asset/service target correctness.
2. Root-cause evidence coverage and counter-evidence handling.
3. Preconditions and ownership/fencing checks.
4. Risk classification and blast-radius estimate.
5. Exact allowlisted action type and bounded parameters.
6. Expected postconditions measurable by independent sources.
7. Rollback completeness and rollback verification.
8. Human approval requirements and separation of duties.
9. Policy consistency and no claims of execution.
10. Expected business impact and customer communication.

A high-quality proposal is not an executed action. Critic approval is not Policy approval. Human approval is not executor authorization.

## 7. 48-hour benchmark deliverable

- Baseline report from the existing evaluator with dataset hash, model/provider/prompt versions and quality metrics.
- Add latency measurement around each Analyst and Critic request.
- Extract provider `usage` fields only where response contract supplies them; add tests for present, absent and malformed usage.
- Add per-case/per-stage token and latency aggregates; preserve null when unavailable.
- Add pricing metadata input file with explicit version/source; cost remains UNKNOWN until matched to reliable usage and approved price data.
- Add a comparative table only when at least two configurations have been run on the same dataset and environment.
- Publish exact command, commit, artifact SHA, tests and known gaps.

## 8. Promotion gates

No model/provider/prompt promotion unless the candidate meets the current quality gates, has no critical safety regression, passes tenant/ACL and injection tests, and shows measured latency/token/cost trade-offs. Any threshold change requires an ADR and a new benchmark dataset version. Keep model evaluation synthetic until production data use is approved and privacy-reviewed.


## 9. Implementation update — 2026-10-30

Stacked PR [#196](https://github.com/alimtalbi-ata/aiops/pull/196) adds the first invocation telemetry slice on top of HITL PR #194:

- Analyst/Critic response metadata includes invocation ID, measured wall-clock latency, HTTP statuses, request/retry count and provider-reported token usage.
- The bounded Critic schema-repair call is included in usage totals.
- Request bytes and generated output tokens have configurable hard bounds.
- Evaluation reports include per-call details, usage coverage, complete token totals only when every call reports valid usage, partial reported sum, p50/p95 latency and retry count.
- Existing Core model-evaluation ledger receives aggregate metrics; detailed invocation rows remain in the report artifact.

**Exact-head CI:** PR #196 correction head `388b7c48a108f70315b9fae92de72d10ac399704` passed AIOps quality gates run `41053026110` (6/6 jobs), Offline Integrity `41053026078`, Historical Trace `41053026102`, and V2.8 Core `41053026140`.

**Still not qualified:** real DGX/provider benchmark (CI uses deterministic provider), dedicated durable per-invocation DB rows, tenant/run spend quotas, pricing source and actual USD cost. Missing usage/pricing remains UNKNOWN. The request-byte limit is not a token estimate. The PR is stacked on #194 and is not yet part of main.


## 9. Baseline evidence and existing telemetry work — 2026-10-30 12:15 UTC

The reproducible local dataset/harness audit is recorded in [AIOPS2-AI-BENCHMARK-BASELINE-2026-10-30.md](AIOPS2-AI-BENCHMARK-BASELINE-2026-10-30.md): five synthetic cases, dataset SHA256 `b383ce38ec8cf819176884f61822ad074057721c7df803cbebebfa604751438e`, harness 3/3 PASS, **zero model invocations**. This is a structural baseline, not a measured quality, latency or cost benchmark.

Reuse [PR #196](https://github.com/alimtalbi-ata/aiops/pull/196) on top of #194 for provider usage and latency instrumentation; its exact-head four workflows succeeded. Do not duplicate its provider client, assume provider usage is available, or publish estimated spend as billed cost. An isolated synthetic Analyst/Critic run on a pinned provider/model/prompt/dataset is still required before reporting p50/p95, token counts or cost.


## 10. Exact CI baseline — 2026-10-30

The exact deterministic CI report is published at `docs/benchmarks/2026-10-30-ci-deterministic-ai-baseline.md`.

- Dataset: `aiops-core-qualification-1.0.0`, SHA-256 `b383ce38ec8cf819176884f61822ad074057721c7df803cbebebfa604751438e`.
- Provider/model: `openai-compatible / ci-deterministic`.
- Quality: all eight current quality metrics 1.00 over five synthetic cases.
- Telemetry: 10 calls, usage coverage 100%, reported 20 total tokens, P50 1.69 ms, P95 3.24 ms, zero retries.
- Cost: UNKNOWN; pricing source absent.
- Runtime E2E: synthetic Run `RUN-FB8DDB7C6B22B5F4` RESOLVED, 12 evidence records, Policy PASS/SIMULATE, zero effect receipts.

The CI provider emits fixed placeholder token counts; token/latency numbers are proof of telemetry plumbing, not real-model consumption or performance. No customer SLA, GPU capacity or provider cost conclusion may be drawn from this baseline.
