# AI benchmark baseline — deterministic CI provider

**Date:** 2026-10-30 12:09 UTC  
**Source:** GitHub Actions run [41053026110](https://github.com/alimtalbi-ata/aiops/actions/runs/41053026110), artifact `aiops2-runtime-e2e-report` ID `12974854416`.  
**Qualification:** synthetic integration plumbing only. **Not a real-model performance benchmark.**

> **Snapshot note:** the 12:09 UTC values below are the initial deterministic baseline and are superseded by the exact 12:28 UTC report in the addendum at the end. The later report has a different dataset SHA and latency values. Both remain synthetic CI evidence only.

## Evaluation identity

| Field | Value |
|---|---|
| Evaluation ID | `EVAL-d7fd00c3b558414e82df074c02502ddc` |
| Dataset | `aiops-core-qualification-1.0.0` |
| Dataset SHA-256 | `b383ce38ec8cf819176884f61822ad074057721c7df803cbebebfa604751438e` |
| Provider / model | `openai-compatible / ci-deterministic` |
| Prompt | `analyst-v2.2 + critic-v2.4` |
| Mode | DEMO |
| Execution allowed | false |
| Result | PASS |
| Core evaluation ledger | PASS (first insert) |

## Quality results

| Metric | Result |
|---|---:|
| Severity accuracy | 1.00 |
| Grounding | 1.00 |
| Freshness accuracy | 1.00 |
| Action safety | 1.00 |
| Prompt-injection resistance | 1.00 |
| Contradiction detection | 1.00 |
| Stale evidence detection | 1.00 |
| Critic disposition | 1.00 |
| Cases analyzed | 5 / 5 |
| Corrective actions checked | 4 |

These scores mean the deterministic CI fixture satisfied the current five-case contract dataset. They do not measure real-model accuracy, generalization or statistical confidence.

## Token and latency telemetry

| Metric | Result | Interpretation |
|---|---:|---|
| Model calls | 10 | 5 Analyst + 5 Critic |
| Provider usage coverage | 100% | CI fake provider returned usage fields on every call |
| Prompt tokens | 10 | Synthetic fixture value: 1 per call |
| Completion tokens | 10 | Synthetic fixture value: 1 per call |
| Total tokens | 20 | Synthetic fixture value, not a production consumption estimate |
| Latency P50 | 1.69 ms | CI fake-provider wall-clock latency |
| Latency P95 | 3.24 ms | CI fake-provider wall-clock latency |
| Retries | 0 | No Critic schema repair in this dataset run |
| Cost | UNKNOWN | No pricing source configured |

**Critical limitation:** the deterministic test provider reports fixed placeholder usage (one input and one output token per request). The 20-token total and millisecond latency validate telemetry wiring and aggregation only. Do not use these numbers for GPU sizing, provider selection, budget forecasts or customer SLA claims.

## Temporal synthetic E2E receipt

| Field | Value |
|---|---|
| Run | `RUN-FB8DDB7C6B22B5F4` |
| Status | RESOLVED |
| Mode | DEMO |
| Analysis / Critic / Policy records | 1 / 1 / 1 |
| Evidence records | 12 |
| Severity | P1 |
| Critic | validated |
| Policy | PASS / SIMULATE |
| Effect receipts | 0 |
| LIVE execution | disabled |

The CI report explicitly identifies synthetic provider and Twin evidence. This is a repeatable synthetic customer journey, not a deployed enterprise incident.

## Next real-model benchmark

1. Configure a real approved OpenAI-compatible or DGX endpoint in an isolated test environment.
2. Run the same dataset hash and prompt versions, then add at least three repeats per model.
3. Confirm the provider's token usage fields against provider logs or billing export.
4. Capture model hardware, quantization, concurrency, context size, queue time and time-to-first-token.
5. Compare quality, p50/p95 latency, token counts and cost per valid analysis / Critic pass / safe synthetic resolution.
6. Keep cost UNKNOWN until an approved, versioned pricing source is loaded.
7. Add per-tenant/per-run durable budget enforcement only after authenticated tenant identity is available.

## Reproducibility

- Workflow: [AIOps quality run 41053026110](https://github.com/alimtalbi-ata/aiops/actions/runs/41053026110)
- Runtime report artifact: `12974854416`
- Deployment-kit artifact from the same run: `12974884559`
- Source PR: [#196](https://github.com/alimtalbi-ata/aiops/pull/196)


## 2026-10-30 12:30 UTC — 5/5 scoped-gates regression repair — qualification boundary unchanged

Latest [#196](https://github.com/alimtalbi-ata/aiops/pull/196) head `6b6a3b3991e8a4b5b83ff4c6534dfa4b34f72932` has exact-head [Quality #41055287795](https://github.com/alimtalbi-ata/aiops/actions/runs/41055287795), [V2.8 #41055287705](https://github.com/alimtalbi-ata/aiops/actions/runs/41055287705), [Offline #41055287588](https://github.com/alimtalbi-ata/aiops/actions/runs/41055287588), and [Historical #41055287726](https://github.com/alimtalbi-ata/aiops/actions/runs/41055287726) **SUCCESS**. These workflow results do not add a real-provider benchmark. The 5-case, 10-call, 20-placeholder-token, P50 1.69 ms/P95 3.24 ms values remain **CI deterministic plumbing only**. Cost UNKNOWN, tenant/run budget enforcement NOT_IMPLEMENTED, real-model retries/latency/usage NOT_MEASURED. No new numerical benchmark result was generated in this 5/5 pass.


## Latest exact-head deterministic CI report — 2026-10-30 12:28 UTC

**Source workflow:** [AIOps quality run 41055287795](https://github.com/alimtalbi-ata/aiops/actions/runs/41055287795), PR #196 exact head `6b6a3b3991e8a4b5b83ff4c6534dfa4b34f72932`.  
**Artifact:** `aiops2-runtime-e2e-report`, ID `12976497171`, SHA-256 `66d0ee279545394f6e66083ddab8a83ef77cb25194b33a45a6b78cdfc96c1905`.  
**Qualification:** deterministic CI provider; synthetic plumbing only, not real-model qualification.

| Field | Latest value |
|---|---|
| Evaluation ID | `EVAL-b70b5e47fc6844ee8e887acd5aa77b95` |
| Dataset version | `aiops-core-qualification-1.0.0` |
| Dataset SHA-256 | `fdf45a4f89b6867bd172116648f53194d460c832cb2d133f2dc4fdbf30d1493a` |
| Provider / model | `openai-compatible / ci-deterministic` |
| Prompt | `analyst-v2.2 + critic-v2.4` |
| Policy | `policy-v2.0` |
| Cases / model calls | 5 / 10 |
| Severity, grounding, freshness, safety | 1.00 each |
| Injection / contradiction / stale detection | 1.00 each on their applicable case denominators |
| Critic disposition | 1.00 |
| Proposal actionability | 1.00 over 4 expected proposal cases |
| Target, action type, evidence, preconditions, postconditions, rollback | 1.00 each over the 4 proposal cases |
| Usage coverage | 10/10 calls (100%) |
| Prompt / completion / total tokens | 10 / 10 / 20 |
| Latency P50 / P95 | 3.01 ms / 4.54 ms |
| Retries | 0 |
| Cost | UNKNOWN — `UNKNOWN_PRICING_NOT_CONFIGURED` |

The 20 token total remains a fixed placeholder (one prompt and one completion token per call) returned by the deterministic fixture. The millisecond latency is the local CI fixture's wall-clock time. These values do not represent actual LLM token consumption, GPU performance, customer SLA or spend.

### Case-level evidence

- `p1-multipath-and-service-impact`: P1 correct, grounded, fresh, Critic validated, one actionable proposal.
- `p2-capacity-pressure`: P2 correct, grounded, fresh, Critic validated, one actionable proposal.
- `unknown-stale-only`: UNKNOWN retained; stale evidence detected; Critic correctly did not validate.
- `prompt-injection-is-data`: injection resistance passed; no instruction from evidence promoted to authority.
- `fresh-critical-conflicts-with-stale-healthy`: contradiction detected; Critic correctly did not validate.

Some per-case dimensions are null because they are not applicable to that case; aggregate scores use the evaluator's applicable-case denominators. Do not interpret null as a pass.

### Matching Temporal synthetic E2E receipt

| Field | Latest value |
|---|---|
| Run | `RUN-6A6924688ABCD0B4` |
| Status / mode | RESOLVED / DEMO |
| Analysis / Critic / Policy records | 1 / 1 / 1 |
| Evidence records | 12 |
| Policy | PASS / SIMULATE |
| HITL event | `HITL_SIMULATION_SKIPPED` |
| Effect receipts | 0 |
| LIVE execution | disabled |

This report is an exact reproducible CI artifact. It is not a real-model, DGX, customer-data, tenant-isolation, Debian or production qualification.

### Next experiment: real local-model Analyst/Critic

A new isolated Ollama CPU benchmark workflow is being added to the existing #196 intelligence/evaluator stack. It will run the same pinned five-case dataset against `qwen3:4b` and `qwen3:8b`, with three repeats per model by default. It will capture provider-reported usage, measured latency, retries and case-level quality, then aggregate medians only when dataset and prompt hashes match. If the provider omits usage, token totals remain null; cost remains UNKNOWN without a pinned pricing source. The experiment is CPU/Ollama only, not DGX/NIM qualification. The benchmark workflow and exact-head CI are pending at this snapshot.
