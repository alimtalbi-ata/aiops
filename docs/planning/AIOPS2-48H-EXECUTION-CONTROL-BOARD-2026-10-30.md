# AIOps 2.0 — 48-hour execution control board

**Execution start:** 2026-10-30 16:11 Europe/Paris (UTC+01:00)  
**48-hour target:** 2026-11-01 16:11 Europe/Paris  
**Architecture owner:** Schedule 5/5 — architecture, benchmark, integration and release  
**Primary repository:** `alimtalbi-ata/aiops`  
**Primary demo:** ACME synthetic enterprise — SAN path degradation → Payments service impact investigation

> This board is the live steering record for the 48-hour window. It distinguishes source/CI qualification from integrated runtime, Debian attestation and production readiness. A green PR is not a green platform.

## 1. Delivery objective

Deliver one coherent, repeatable customer demonstration and a cumulative, auditable installation-kit candidate. The client must recognize a realistic IT operating model: service impact, incident command, evidence, investigation, risk decisions, human governance, controlled simulation, verification and continual improvement.

The target is **DEMO T2/T3 evidence**, not production cutover, not real SAN remediation, not an ITIL certification claim and not an assertion that every enterprise connector is live.

### Customer journey

1. Monitoring event: synthetic SAN fabric path degradation, with source, timestamp and deduplication key.
2. Service impact: Payments service and CI dependency path from the governed ACME Twin fixture; show edge provenance and freshness.
3. Incident: one Core-owned Incident and Run, P1 only if impact/urgency evidence and deterministic priority policy support it.
4. Service Desk: N1 acknowledgement/ownership, N2 investigation, N3 specialist escalation, incident commander and customer update as explicit lifecycle events.
5. Evidence: immutable evidence IDs, source, hash, observed_at, known_at, freshness, tenant/run binding; absent proof is UNKNOWN.
6. Intelligence: Analyst hypotheses, alternatives and bounded corrective proposals; independent Critic challenge and disposition.
7. Governance: deterministic Policy decision, proposal hash/revision, verified approver identity, expiry, scope, preconditions, postconditions and rollback.
8. Action: isolated SIMULATE only, with a no-effect receipt; no real SSH, sudo, Ansible or GLPI mutation.
9. Verification: independent postcondition checks, before/after evidence and explicit result.
10. ITSM closure: read-only GLPI relation only when the authoritative connector verifies the same tenant/ticket/incident/run; otherwise UNKNOWN.
11. Continual improvement: Problem/known-error candidate, post-incident review and knowledge suggestion with owner/review status.

Every screen and export must preserve `SYNTHETIC` / `SOURCE_VERIFIED_SYNTHETIC_ONLY` labels where applicable. Never narrate a synthetic measurement as a customer production event.

## 2. Target architecture and authority boundaries

| Plane | Existing implementation to reuse | Authority / invariant |
|---|---|---|
| Signal & observability | Prometheus, Grafana, Alertmanager; Checkmk only when installed and verified | Source telemetry; never owns Incident/Run |
| Integration | Existing Core/NOC adapters, GLPI read-only adapters, n8n notifications | Authenticate, normalize, timestamp and dedupe; no parallel lifecycle |
| Service control | Core API + PostgreSQL migrations | Sole business authority for tenant, Incident, Run, stage, event, evidence refs, Policy/HITL decisions |
| Orchestration | Temporal + Worker | Durable orchestration/retries/signals; no second business ledger |
| Context | Twin/CMDB, Evidence, RAG/knowledge | Sourced, versioned, fresh, ACL-qualified context; missing facts remain UNKNOWN |
| Intelligence | Existing Analyst/Critic evaluator and Intelligence service branch | Advisory only; model cannot authorize, alter Policy or execute |
| Governance | Deterministic Policy, Core HITL ledger, OIDC verifier, audit | Least privilege, SoD, immutable proposal/decision, expiry, nonce, tenant fence |
| Execution | Existing isolated simulator/remediation lab | No effects outside the isolated simulator until separately qualified |
| Experience | Existing Portal/NOC/Demo Studio/Grafana | API-backed read models; no direct database writes |
| Release | Existing deploy/package/backup/restore/checksum tooling | Exact source SHA, manifest, migrations, image references, tested upgrade and rollback |

**Canonical flow:**  
`Monitoring/ITSM → authenticated adapters → Core Incident/Run → Temporal → Evidence + Twin + RAG → Analyst → independent Critic → deterministic Policy → HITL → isolated SIMULATE → independent VERIFY → ITSM reconciliation → Problem/PIR/Continual Improvement`

### Canonical data contract

All event and decision envelopes must carry, where relevant: `schema_version`, `tenant_id`, `source`, `source_event_id`, `event_time`, `ingested_at`, `observed_at`, `known_at`, `dedupe_key`, `incident_id`, `run_id`, `service_id`, `ci_id`, `ticket_id`, `evidence_ids`, `mode`, `provenance`, `freshness`, `correlation_status`, `policy_version`, `proposal_hash`, `proposal_revision`, `actor_subject` and `trace_id`.

Do not infer cross-system identity from titles, copied IDs or text in a ticket. The authority that owns the relation must verify it.

## 3. ITIL 4 operating model — demonstrable behaviors

| Practice | Demo behavior | Evidence required |
|---|---|---|
| Monitoring & Event Management | normalize, correlate, dedupe, acknowledge | source event, timestamp, dedupe record |
| Incident Management | impact/urgency, P1-P4, SLA timer, escalation, major incident | Core incident history and priority-policy version |
| Service Desk | N1 acknowledge, ownership, communication, handover | actor, queue, timestamps, OLA |
| Service Configuration Management | CI/service/dependency graph | source, version, freshness per edge |
| Problem Management | recurring pattern, root-cause hypothesis, known error/workaround | linked incidents and verified evidence |
| Knowledge Management | cited runbook/KB retrieval with ACL/version/owner/expiry | document ID/version/citation/access decision |
| Change Enablement | risk, implementation, maintenance window, approver, rollback | change proposal and approval evidence |
| Release/Deployment Management | exact package, manifest, staged install, rollback | SHA-256, applied SHA, health and rollback receipt |
| Service Validation & Testing | unit, contract, integration, E2E, failure injection | exact SHA, command, N/N and artifact |
| Information Security Management | SSO/MFA, RBAC, tenant fence, audit, redaction | verified claims, policy decision and audit |
| Service Level Management | SLO/SLI, SLA/OLA, breach/near breach | source metric and threshold/version |
| Continual Improvement | PIR, action owner/due date, knowledge update | verified cause, decision, accepted action |

This is alignment with ITIL 4 practices, not certification.

## 4. AI benchmark and usage governance

### Score four independent dimensions

**A. Diagnostic quality**
- Severity/priority agreement against deterministic gold labels.
- Top-1 / top-3 root-cause accuracy where the gold set supports it.
- Evidence grounding and citation validity.
- Evidence freshness and stale-data detection.
- Contradiction detection and correct abstention.
- Prompt-injection resistance and unsupported-claim rate.
- Analyst/Critic disposition agreement and Critic false-accept rate.

**B. Corrective proposal quality**
- Correct CI/target and allowlisted action type.
- Evidence IDs are a subset of the input evidence.
- Explicit preconditions and measurable postconditions.
- Independent verification steps.
- Rollback completeness and risk classification.
- Human approval requirement and advisory-only flag.
- Proposal actionability rate; unsafe or unsupported proposal rate.

**C. Efficiency**
- Provider-reported prompt, completion, total, cached and reasoning tokens per call.
- Tokens per case, per Incident and per successful actionable proposal.
- P50/P95 latency, timeouts, retry count and schema-repair overhead.
- Usage coverage: provider-reported calls / total model calls.
- Input/output token ratio and context-size distribution.
- Cost per case/incident only when a versioned provider price sheet or invoice is available.

**D. Operational control**
- Request/context byte cap, output-token cap, timeout, retry budget and concurrency.
- Per-tenant and per-run budgets only after durable usage accounting is available.
- Circuit-breaker and graceful fallback/abstention behavior.
- Model/prompt/dataset/schema/retrieval version and SHA for every report.

### Benchmark rules

1. Reuse `tools/evaluate_ai_core.py`, `eval/ai-core-cases.json`, `tests/test_ai_eval_harness.py` and the existing Core model-evaluation ledger.
2. Keep deterministic provider contract tests separate from real model results.
3. Compare models only on identical dataset SHA, prompt version, schema, retrieval corpus, context limits and environment.
4. Run at least one bounded real local-model comparison, then repeat only after the first run completes within resource limits.
5. Do not estimate tokens from bytes/characters. Missing provider usage is UNKNOWN.
6. Do not estimate cost. Cost is UNKNOWN without a pinned pricing source.
7. A green workflow is not a quality PASS. Any failed evaluator repeat must fail the benchmark job after preserving its report artifact.
8. Do not promote a model on quality alone: include latency, usage coverage, reliability, cost provenance, safety and actionability.
9. Ollama CPU results do not qualify DGX/NIM/GPU production throughput or SLA.

### Current benchmark facts

- Deterministic CI baseline: five synthetic cases, ten Analyst/Critic calls, placeholder usage and very low fake-provider latency. It validates the telemetry contract only.
- Previous Ollama CPU run on #196 HEAD `48b353b1`: qwen3:4b and qwen3:8b each had three evaluator failures caused by `ReadTimeout`; zero model calls were scored, token/latency/cost were unavailable. The 8/8 Quality workflow was green but the experiment itself failed.
- Follow-up correction is being implemented on #196: qwen3:1.7b + qwen3:4b, one repeat by default, 300-second per-call timeout, 2,048 output-token cap, 65,536-byte request cap, artifact-first reporting and a fail-closed evaluator-exit gate. New exact-head run is required before claiming results.
- No real-model PASS, actual token consumption or cost is currently claimed.

## 5. Exact-head reuse and integration register

| Work | Current source / CI evidence | Decision |
|---|---|---|
| #195 architecture | main-based docs branch; Quality 41078216626 SUCCESS | Architecture and release steering source |
| #201 clean-main staging | HEAD 7474c74; Quality 41077972849 SUCCESS | Primary integration candidate for selective main-based demo slices; T0 only |
| #185 integrated ACME candidate | HEAD 2b2af9c; four observed workflows SUCCESS; base diverges 741 ahead / 43 behind main | Scenario/story source only; no wholesale merge |
| #197 Evidence UTC preflight | main-based; Quality SUCCESS | Reuse timestamp gate only; not authenticated Evidence |
| #198 Core Run locator + ACME fixture | main-based; Quality SUCCESS | Reuse locator/fixture contracts; not tenant ACL or runtime attestation |
| #199 Policy SIMULATE fixture | main-based; Quality SUCCESS | Reuse deterministic synthetic Policy projection; no approval/effect |
| #200 INGEST initial state | main-based; targeted tests/CI reported in PR | Reuse only after exact current-head CI confirmation |
| #202 Portal Run detail | main-based; Quality 41074573704 SUCCESS | Reuse read-only detail; session capability is not OIDC or tenant authorization |
| #205 ITSM↔Run xref | main-based; Quality 41075269257 SUCCESS | Contract/mock only; no real Core GET or GLPI connector |
| #194 HITL/OIDC/outbox | stacked on #193; HEAD 40d3870; Quality, V2.8, Offline, Historical all SUCCESS | Reuse after selective main-based dependency review; Portal SSO and full live-path qualification remain open |
| #204 HITL failure injection | stacked on #194; HEAD dabfeb6; all four observed workflows SUCCESS | Reuse strict positive revision fence and negative tests; not a complete runtime Temporal failure test |
| #196 AI telemetry | stacked on #194; previous HEAD 48b353; Quality 8/8 but real Ollama evaluation failed all six repeats | Reuse instrumentation/evaluator; new bounded fail-closed benchmark rerun pending |
| #188 schedule | main-based; daily full Quality + 15-minute read-only smoke | Preferred schedule PR; runtime smoke blocked until approved self-hosted runner is installed and attested |
| #189 schedule | main-based; two-hour full Quality cadence | Duplicate; do not activate alongside #188 |
| #187 Loki/Tempo/OTel | separate draft branch | Defer; instrument existing Prometheus/Grafana first |
| #146/#153 auto-deploy | old unqualified proposals | Keep disabled; no auto-deploy in this 48-hour window |

**Integration policy:** do not mass-merge branches. For each port, identify exact source blob, dependency graph, target base SHA, changed paths, owner, tests, CI and rollback. Core, Portal, Worker, Compose and migrations are conflict hotspots and must be integrated in small, reviewed slices.

## 6. Five-schedule operating model

The five existing schedules remain the only parallel work lanes. No sixth schedule is created.

| Schedule | Exclusive ownership | Current priority | Handoff contract |
|---|---|---|---|
| 1/5 ACME/Twin | scenario, CI graph, source-backed SAN→Payments | one deterministic incident/run and fixture hash | exact IDs, edge source/freshness, command, tests |
| 2/5 Portal | operator journey, NOC, Demo Studio, Run detail | one authenticated, coherent read-only customer journey | route list, screenshot only if captured, run deep links, tests |
| 3/5 NOC/Evidence/GLPI | source adapters and cross-system reconciliation | Evidence provenance and verified ticket/run relation | exact IDs, auth/scope, freshness, UNKNOWN where absent |
| 4/5 Policy/HITL | Policy, proposal, identity, approval and simulation | fail-closed decisions and failure-injection evidence | policy version/reasons, proposal hash/revision, roles, no-effect receipt |
| 5/5 Architecture/release | integration order, ADRs, AI benchmark, CI, package and release decision | coordinate exact SHAs, fix benchmark reporting, one cumulative kit | decision log, dependency map, manifest, hashes, GO/NO-GO |

No schedule edits another lane's exclusive module without a documented handoff. Schedule 5/5 resolves conflicts; it does not bypass source authority or acceptance gates.

## 7. 48-hour execution sequence

| Window | Deliverable | Exit criteria |
|---|---|---|
| H0–H4 (16:11–20:11, Oct 30) | Freeze exact baseline, verify branch/PR/CI inventory, reconcile duplicate schedules, freeze scenario and IDs | no conflicting PR/cron; single owner and candidate |
| H4–H12 (20:11 Oct 30–04:11 Oct 31) | Coherent Portal journey over the main-based Run/Twin/Policy/Evidence contracts | one canonical Incident/Run; verified source links or explicit UNKNOWN |
| H12–H24 (04:11–16:11 Oct 31) | AI benchmark and efficiency report | bounded real-model run or explicit timeout diagnosis; deterministic and real model results separated |
| H24–H36 (16:11 Oct 31–04:11 Nov 1) | ITIL lifecycle and negative-path rehearsal | N1/N2/N3/P1/SLA, Critic reject, Policy BLOCK, HITL reject/revoke, outbox restart/lease tests, no-effect verification |
| H36–H48 (04:11–16:11 Nov 1) | Clean install-kit rehearsal, storyboard and client demo | cumulative source manifest/checksums, clean install/upgrade/rollback evidence or explicit NO-GO |

If a lane misses its exit gate, reduce scope and expose UNKNOWN; do not weaken acceptance criteria.

## 8. Qualification and release gates

| Tier | Meaning | Current state |
|---|---|---|
| T0 | source, static, unit and contract CI | PASS on several component heads; integrated #201 current head requires its own exact evidence |
| T1 | ephemeral real-service integration | NOT_TESTED for the complete converged candidate |
| T2 | deterministic synthetic end-to-end journey | NOT_TESTED for the current clean-main candidate |
| T3 | Debian runtime/source/image attestation | NOT_ATTESTED; no host/runner access in this session |
| T4 | isolated sandbox effect + independent verification + exercised rollback | NO_GO pending exact effect/verify/rollback evidence |
| T5 | LIVE production authority/remediation | NO_GO; explicitly outside 48-hour target |

### Hard stop conditions

Stop and mark BLOCKED if tenant/actor identity is ambiguous; evidence provenance/freshness is missing; Core/Temporal disagree; AI output is malformed/ungrounded; Critic rejects; Policy returns BLOCK/UNKNOWN; proposal hash/revision/scope changes; an outbox lease is lost; executor ownership/fencing is absent; or package/rollback proof is incomplete.

## 9. Tooling and operational limits

- GitHub and GitHub Actions are available for source review, PR changes, tests and workflow evidence.
- No Debian SSH/Docker/host session is available through this session. No crontab, systemd runner, volume, deployed image, applied SHA or production service will be changed or claimed.
- No ChatGPT Lab control surface is exposed to this session. Keep the five existing ChatGPT schedules; Schedule 5/5 is the integration owner. Do not create a sixth schedule.
- GitHub schedule #188 remains the preferred future daily-quality / read-only-smoke candidate; #189 is redundant. Neither is treated as active until merged, and the 15-minute runner job requires separate runner installation/attestation.
- Auto-deploy schedules #146/#153 remain disabled.
- The new observability stack #187 is deferred until resource, persistence, retention and security review; use existing Prometheus/Grafana first.

## 10. Required evidence for every work item

Each handoff or completion record must include:
- PR / branch / base SHA / exact head SHA.
- Exact changed paths and source blob/commit provenance.
- Exact test command, observed N/N, environment and mode.
- GitHub Actions run URL and per-job conclusion.
- Runtime/artifact evidence and SHA-256 where applicable.
- Known limitations, UNKNOWN fields, failure modes and rollback.
- Status vocabulary: `PLANNED`, `IN_PROGRESS`, `PASS_SOURCE`, `PASS_INTEGRATION`, `PASS_SYNTHETIC_E2E`, `PASS_RUNTIME_ATTESTED`, `BLOCKED`, `NO_GO`.

Never use one generic PASS for all tiers.


## 2026-10-30 16:25 Europe/Paris — customer-story implementation delta

The clean-main integration candidate #201 has a new 14-checkpoint ACME Explore/Story vertical slice at source HEAD `890977be741269a864f991a37ecf3208e82ecd34`; Quality run `41081252003` was queued at the time of this update.

The Portal now presents synthetic owner roles, ITIL practice, handoff and evidence requirements for:
1. Monitoring/Event → NOC L1 detection.
2. CMDB/Twin → NOC L2 dependency correlation.
3. Service Desk N1 acknowledgement and SLA start.
4. N2 impact/urgency/P1 assessment.
5. Incident commander and customer communications.
6. N3/SRE evidence collection.
7. ACL/versioned Knowledge retrieval.
8. Problem Manager N3 analysis and Critic challenge.
9. Change proposal, risk and rollback.
10. Authorized approver (simulation-only).
11. Temporal/automation no-effect simulation.
12. Independent service/SLO verification.
13. Service Desk incident closure.
14. Problem review and Continual Improvement.

All checkpoints deliberately remain `MISSING`; they specify required evidence, not captured events. No actual ticket, runtime timestamp, approver, SLA breach, recovery or live impact is inferred. This is the 48-hour customer story spine, not a connector qualification.

## 2026-10-30 15:36 UTC — exact-head gate correction and Ollama artifact audit

- #201 clean-main candidate: the 14-step synthetic ITIL read-model introduced at `890977be` invalidated nine-step Chromium and read-only qualification fixtures. [Quality 41081496981](https://github.com/alimtalbi-ata/aiops/actions/runs/41081496981) on `c00ceb111fc5538b31987146267f8b7d0bbb82dd` **FAILED** (policy-and-static: Chromium six tests, 2 PASS / 2 FAIL / 2 ERROR; Core/PostgreSQL and Grafana jobs SUCCESS). A pinned 14-target validator and Chromium assertions were corrected on the same draft PR; 5/5 added [`2dafb00717b572023153e2b5dd974eada8a759c5`](https://github.com/alimtalbi-ata/aiops/commit/2dafb00717b572023153e2b5dd974eada8a759c5) to finish the second 14-step assertion and add negative tests for forged ITIL provenance/metadata. [Exact-head Quality 41082175476](https://github.com/alimtalbi-ata/aiops/actions/runs/41082175476) **IN_PROGRESS at this checkpoint**; no PASS claim. No source or auth guard weakened.
- #196 stacked benchmark HEAD `135328f51c64c29648df42e9ec6846b783fb3604`: [Ollama push 41080394263](https://github.com/alimtalbi-ata/aiops/actions/runs/41080394263) now has **2/2 model jobs FAILURE**, with artifact-first reports retained: [1.7B artifact 12989398184](https://github.com/alimtalbi-ata/aiops/actions/runs/41080394263/artifacts/12989398184), [4B artifact 12989592150](https://github.com/alimtalbi-ata/aiops/actions/runs/41080394263/artifacts/12989592150). Each: evaluator_exit=1, 0/5 cases analyzed, ReadTimeout, provider/model unavailable, no latency/usage/cost. The fail-closed job gate now exposes failure instead of falsely green. [Quality PR 41080407493](https://github.com/alimtalbi-ata/aiops/actions/runs/41080407493) has non-model jobs green but two Ollama jobs **IN_PROGRESS**; not a model qualification.
- All 14 customer checkpoints still `MISSING`, no source-backed GLPI/Evidence/tenant/runtime capture. T0 new head PENDING, T1 complete/T2 NOT_TESTED, T3 NOT_ATTESTED, T4/T5 NO_GO. Next: finish exact-head Chromium CI; diagnose isolated Ollama CPU timeouts without relaxing quality thresholds; keep single cumulative kit BLOCKED pending #194/#196 selective port, migration 011 and exercised rollback.

### 2026-10-30 15:40 UTC — Chromium gate restored; Portal rejection-header port

- [#201 Quality 41082437029](https://github.com/alimtalbi-ata/aiops/actions/runs/41082437029) **SUCCESS 3/3** at exact `5f2feb088694f4eaa4472a4ab7ca6611a58371c1`; real ephemeral Chromium Explore/Story **6/6 PASS**, including 14-step ITIL projection, forged source/metadata negatives, and fail-closed read-only qualification. Kit gate **12/12 PASS** is inventory logic only, not a kit. [Synthetic Chromium artifact 12989149422](https://github.com/alimtalbi-ata/aiops/actions/runs/41082437029/artifacts/12989149422) ZIP CRC PASS, screenshot SHA256 `8a1720c3851833525d0e817a157d24826ff431fc84ce1d9d9742fd5595ebcaca`, source fixture SHA256 `254b1e4df518e38febc3bd25347462b67b24a39228b744a0235ef33f1578faed`. Its metadata explicitly says `CI_SIMULATED_PORTAL`, `runtime_authenticated=false`, `production_qualified=false`, `live_remediation_authorized=false`, GLPI ticket null.
- The 2/5 [#202 `5fe17abd`](https://github.com/alimtalbi-ata/aiops/commit/5fe17abd3b4f8c0e8dc043f9b5da030f19a26c67) failure-response hardening was selectively integrated into the *same* #201 draft in [`59ba22f1761c35ed46b92ffe5a3c4d050ed4f7c6`](https://github.com/alimtalbi-ata/aiops/commit/59ba22f1761c35ed46b92ffe5a3c4d050ed4f7c6): exact source blob `app/portal/acme_run_detail.py@14729a4a8c3b54757e5e78e12a8043202adb7caa` plus the new denial-header regression test inserted into #201's existing test file, preserving its independent coverage. Source-parent code blob equalled #201 before port; no main.py/Compose/DB change. [New exact-head Quality 41082715412](https://github.com/alimtalbi-ata/aiops/actions/runs/41082715412) **QUEUED** at this checkpoint, not a PASS. No LIVE/session/OIDC tenant attestation.

<!-- convergence-5of5-477da60-20261030 -->
## 5/5 checkpoint — exact-source contract convergence

**Audit UTC:** 2026-10-30T16:15:33.055Z. **Release candidate:** [#201](https://github.com/alimtalbi-ata/aiops/pull/201), base `main@27deb9b1a66faf27df8d69b137a63451f7649d80`, exact HEAD [`477da60d92dc777e1e635eea4c5510c350a5d90c`](https://github.com/alimtalbi-ata/aiops/commit/477da60d92dc777e1e635eea4c5510c350a5d90c), **28 ahead / 0 behind**, draft and unmerged. [Exact-head Quality 41088096834](https://github.com/alimtalbi-ata/aiops/actions/runs/41088096834) **QUEUED** at audit; previous #201 [Quality 41082715412](https://github.com/alimtalbi-ata/aiops/actions/runs/41082715412) **3/3 SUCCESS** on old `59ba22f1`, not on this new SHA.

Six exact source Git blobs selectively transported in **one commit**, no `main.py`, Compose, DB, Policy, executor or new engine overwritten: from 1/5 [#198](https://github.com/alimtalbi-ata/aiops/pull/198) `0504b1c4`, `tools/find_acme_demo_run.py` `0b2cad84` and `tests/test_find_acme_demo_run.py` `a41b6d97` (canonical UTC / pre-epoch Evidence metadata fail-closed); from 2/5 [#202](https://github.com/alimtalbi-ata/aiops/pull/202) `6a0403b7`, `app/portal/acme_run_detail.py` `b77645bc`, `tests/test_portal_run_detail.py` `3a88d1b3`, `app/portal/portal_run_link_client.js` `fb1f133d`, `tests/test_portal_run_link_client.cjs` `3eda6543` (reject unqualified authority claims, preserve 401/403/503, no credential persistence). Targeted suites are wired in `.github/workflows/quality.yml`; **new SHA test N/N NOT_YET_OBSERVED**. Source #198 Quality 41084152439 and #202 Quality 41084329363 were QUEUED at audit; no source exact-head PASS claim.

**Customer demo:** 14 ITIL checkpoints remain SYNTHETIC/MISSING unless independently captured. Canonical Incident/Run IDs are operator-reported, not runtime re-attested; ticket, Evidence, SLA and Payments impact remain UNKNOWN. **Benchmark:** #196 `747f0df4` Quality 41083049858 QUEUED; prior Ollama ReadTimeout/evaluator nonzero is a failed real-model qualification, not green quality. **Next:** exact-head CI then isolated T2 one Incident/Run with read-only Core/Evidence/Twin and explicit UNKNOWN links; separate cumulative kit/rollback exercise. **T0=PENDING, T1=NOT_TESTED, T2=NOT_TESTED, T3=NOT_ATTESTED, T4=NO_GO, T5=NO_GO.**
