# AIOps 2.0 — Synthetic Analyst/Critic benchmark baseline

**Recorded:** 2026-10-30 12:15 UTC. **Evidence tier:** local offline structural audit only; no model calls, no production access. **Verdict:** BENCHMARK_NOT_QUALIFIED.

## Source and reproducibility

- Existing evaluator: `tools/evaluate_ai_core.py` (SHA256 `affeb783274ffc3ff37238ea124eb915a5e4257d8ddaa78d81919a0c40f997da`).
- Synthetic dataset: `eval/ai-core-cases.json`, version `aiops-core-qualification-1.0.0`, SHA256 `b383ce38ec8cf819176884f61822ad074057721c7df803cbebebfa604751438e`.
- Source used: locally available operator archive labelled `aiops2-acme-portal-02dd3aa-operator.zip` from the earlier #185 candidate. Its claimed correspondence to CI artifact was not independently re-downloaded in this audit; it is **not** the newer #185 head `5782d6f`.
- Command actually run after extraction: `python3 -m unittest discover -s tests -p 'test_ai_eval_harness.py' -v` → **3/3 PASS** (reference extraction for Analyst and Critic; dataset uniqueness/adversarial case presence).
- Additional baseline archive tests: `PYTHONPATH=app:tests python3 -m unittest tests.test_initial_stage_state tests.test_demo_v2 tests.test_acme_core_evidence_refs_read tests.test_acme_policy_demo_result tests.test_acme_glpi_ticket_read tests.test_deploy_acme_p0 tests.test_find_acme_demo_run tests.test_portal_preview_readonly -q` → **193/193 PASS**, on the *older archive only*.
- `sha256sum eval/ai-core-cases.json tools/evaluate_ai_core.py` used for the two hashes above.

## Fixed synthetic cases

| Case | Expected focus |
|---|---|
| `p1-multipath-and-service-impact` | P1 SAN/Payments severity and evidence grounding |
| `p2-capacity-pressure` | P2 classification and bounded advisory action |
| `unknown-stale-only` | stale-only abstention / Critic rejection |
| `prompt-injection-is-data` | injected log text remains untrusted data |
| `fresh-critical-conflicts-with-stale-healthy` | contradiction and stale source handling |

## Measurement scorecard — do not fabricate

| Metric | Measured value | Denominator / source |
|---|---|---|
| Dataset structural checks | 3/3 PASS | local unit harness; not model inference |
| Analyst severity accuracy, grounding, freshness, injection resistance | UNKNOWN | 0 model invocations |
| Critic disposition, false accept/reject, contradiction/stale detection | UNKNOWN | 0 model invocations |
| Corrective proposal actionability / rollback completeness | UNKNOWN | no human-scored proposals |
| p50/p95 latency, time-to-first-token, retries | UNKNOWN | no provider request timing |
| Provider-reported input/output/cached/reasoning tokens | UNKNOWN | no provider usage response |
| USD cost and pricing provenance | UNKNOWN | no approved pricing snapshot or invoice |
| Tenant/run budget enforcement | NOT_TESTED | no authenticated runtime / budget probe |

## Existing implementation to reuse

[PR #196](https://github.com/alimtalbi-ata/aiops/pull/196), HEAD `388b7c48a108f70315b9fae92de72d10ac399704`, is stacked on #194. It adds invocation latency, provider-reported usage, retries, bounded request/output controls and evaluator aggregates. Its four exact-head workflows returned SUCCESS, but the changes are not yet part of the single #185 scenario candidate or any attested Debian deployment. Keep missing usage and cost as null/UNKNOWN.

## Next isolated qualification

1. Freeze this dataset and the provider/model/prompt/policy/retrieval versions, plus environment and concurrency.
2. Run `tools/evaluate_ai_core.py --dataset eval/ai-core-cases.json --report reports/ai-core-evaluation.json` against a **separately approved isolated synthetic Intelligence endpoint** with an ephemeral token. Do not run it against a production or LIVE endpoint.
3. Save the JSON report hash and every case outcome; measure p50/p95, retries, usage coverage and missing counts. Use a pinned pricing source before calculating any cost. Repeat nondeterministic runs at least three times and score proposals independently.

No approval, GLPI write, remediation, Docker restart, or LIVE effect is implied by this baseline.


## 2026-10-30 12:20 UTC — exact candidate artifact cross-check

The same dataset SHA256 `b383ce38ec8cf819176884f61822ad074057721c7df803cbebebfa604751438e` and evaluator SHA256 `affeb783274ffc3ff37238ea124eb915a5e4257d8ddaa78d81919a0c40f997da` were independently verified inside the **new #185 head `5782d6f`** deployment kit, artifact `12975971501` (inner ZIP SHA256 `af627c8af804eec25e643e7b3a7169bb6e513ee6cae8687c18bc4c47c2c0aa5d`). `python3 -m unittest discover -s tests -p 'test_ai_eval_harness.py' -q` → **3/3 PASS** on that exact package as well. **No Intelligence endpoint was called**; all model-quality, p50/p95, provider-token, pricing and budget figures remain UNKNOWN. This confirms source/dataset identity, not benchmark performance.

### 2026-10-30 13:12 UTC — benchmark qualification remains synthetic

Fresh-extraction `#185@2b2af9c` AI harness `python3 -m unittest discover -s tests -p 'test_ai_eval_harness.py' -q` **3/3 PASS**, structural only. #196 `6b6a3b3` Quality/V2.8/Offline/Historical exact-head SUCCESS, but stacked on #194 and absent from #185 cumulative source. Deterministic CI five-case quality 1.0, 10 fake calls, 20 placeholder tokens, p50 1.69ms/p95 3.24ms validate telemetry wiring **only**. No real-model calls or new numerical benchmark: real-model accuracy, latency, tokens, retries and cost UNKNOWN; tenant/run budgets NOT_IMPLEMENTED. No model-selection or spend claim.

## 2026-10-30 14:00 UTC — benchmark boundary after main-based staging

Draft #201 `2ceda14c` **does not** integrate #196 per-call telemetry or invoke a model. The existing CI deterministic five-case/ten-placeholder-call/twenty-placeholder-token exercise is a wiring test only; its latency numbers are not model p50/p95 and its quality 1.0 is not model accuracy. Provider-reported input/output/cached/reasoning tokens, real-model retries/latency, pricing provenance, USD cost and enforced tenant/run budgets remain **UNKNOWN / NOT_IMPLEMENTED / NOT_TESTED**. The separate #196 exact-head four workflows are green but on a divergent stacked base; selectively port only with #194 OIDC/outbox contract reconciliation and new exact combined-SHA tests. No token estimates or costs may be promoted as provider facts.

## 2026-10-30 14:16 UTC — no model performance promotion

#196 has advanced to `cba1c696a797bb8f3b946cb75bd9a399ec54727f`; V2.8/Offline/Historical exact-head workflows are SUCCESS, but its Quality workflow 41069509546 was IN_PROGRESS at this audit. The new #201 release inventory gate requires the telemetry implementation document and benchmark summarizer in a cumulative ZIP; it **does not** measure models or prove provider usage. The prior 5-case deterministic CI scores and 20 placeholder tokens remain synthetic wiring data, not provider-reported consumption. Real-model p50/p95, costs, pricing provenance and tenant/run enforcement remain UNKNOWN/NOT_IMPLEMENTED.

## 2026-10-30 14:23 UTC — #196 exact-head pending real-model evidence

[#196](https://github.com/alimtalbi-ata/aiops/pull/196) HEAD `48b353b1f674f4e952d34d92d072fe4202f1989e`, base SHA `1fade3e5b3f07bdbd6b4fa8222bbb585012894ca` (stale relative to #194 current `40d38705`). V2.8/Offline/Historical exact-head SUCCESS. [Quality #41070920303](https://github.com/alimtalbi-ata/aiops/actions/runs/41070920303) still had Ollama CPU and runtime jobs IN_PROGRESS at inspection: no completed model score, latency, token usage, retry or cost claim. The five-case deterministic CI baseline and 20 placeholder tokens remain wiring evidence only. USD cost and tenant/run budget enforcement UNKNOWN/NOT_IMPLEMENTED. #201 contains neither #194 nor #196 implementation; no cumulative model qualification.

## 2026-10-30 14:28 UTC — exact-head benchmark status, no model score promotion

[#196](https://github.com/alimtalbi-ata/aiops/pull/196) remains on stacked base `feat/temporal-hitl-v1@1fade3e5` (older than current #194 `40d38705`), head `48b353b1f674f4e952d34d92d072fe4202f1989e`. Exact-head V2.8/Offline/Historical are SUCCESS. [Quality 41070920303](https://github.com/alimtalbi-ata/aiops/actions/runs/41070920303): migration, build/package, runtime E2E, MariaDB DR and release-kit jobs SUCCESS; Ollama CPU qwen3:4b and qwen3:8b **IN_PROGRESS** at inspection. Do not claim benchmark accuracy, p50/p95, retries, usage coverage, real-model token totals or artifacts before completed jobs and checked reports. Deterministic five-case/ten-call/twenty-placeholder-token CI is not model inference. USD cost remains UNKNOWN; request/run/tenant budget enforcement NOT_IMPLEMENTED/NOT_TESTED. No #196 telemetry is in #201 main-based candidate `178bbf71`.
