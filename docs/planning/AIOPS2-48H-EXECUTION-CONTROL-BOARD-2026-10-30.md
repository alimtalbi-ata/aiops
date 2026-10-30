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

## 5/5 control update — 2026-10-30 17:08 UTC

- **One main-based candidate:** [#201](https://github.com/alimtalbi-ata/aiops/pull/201), base `main@27deb9b1a66faf27df8d69b137a63451f7649d80`, new head `1d3a902877d556549425a95cd4cef792c5c000c8` (29 ahead/0 behind). Exact-head [Quality 41096370024](https://github.com/alimtalbi-ata/aiops/actions/runs/41096370024) **IN_PROGRESS** at this checkpoint, not PASS.
- Previous head `477da60d92dc777e1e635eea4c5510c350a5d90c` [Quality 41088096834](https://github.com/alimtalbi-ata/aiops/actions/runs/41088096834) **FAILED 2/3 jobs**. Portal suite 25/26 PASS, one ERROR: anonymous home missing `Cache-Control`/anti-framing headers. 5/5 ported only #202's verified `Response` import and `home(response: Response = None)` response-header block into existing #201 Portal; new `app/portal/main.py` Git blob `0dac60be551f58e8a2bf578178a4ff298aef5118` **exactly equals #202 source blob**. No security guard weakened, no other file modified. Targeted Portal Python 26/26 and JS 7/7 were previously observed on #202 exact head, **NOT YET observed on new combined #201**.
- #198 fixture contract on its latest head `0091cc56dceec4729312d08feb1359f107cf1c04`: [Quality 41093598267](https://github.com/alimtalbi-ata/aiops/actions/runs/41093598267) 3/3 SUCCESS, locator 16/16 and fixture 6/6, offline synthetic only. No authenticated Twin/tenant/Evidence/GLPI proof.
- **Real-model benchmark #196** head `747f0df4b8bae0fa0265b6dc568558a6a9057ad1`: [Quality 41083049858](https://github.com/alimtalbi-ata/aiops/actions/runs/41083049858) **6/8 jobs SUCCESS, 2 Ollama FAILED**. Actual logs show qwen3:1.7b ValidationError and qwen3:4b ReadTimeout, each 3/3 repeats `evaluator_exit=1`; no qualified model results/tokens/cost. Artifact-first failure propagation now works. Do not promote deterministic fixture metrics as real usage.
- **T0 PENDING** new exact-head CI; **T1 NOT_TESTED**, **T2 NOT_TESTED** (14 ITIL checkpoints synthetic/MISSING), **T3 NOT_ATTESTED**, **T4 NO_GO**, **T5 NO_GO**. No cumulative kit, migration 011/OIDC/outbox/telemetry integration, Debian smoke, sandbox install/rollback or LIVE. #188 preferred unmerged; #189 duplicate; #146/#153 unauthorized; #187 deferred.

### Exact-head CI qualification — 2026-10-30 17:11 UTC

[#201 Quality 41096370024](https://github.com/alimtalbi-ata/aiops/actions/runs/41096370024) on **`1d3a902877d556549425a95cd4cef792c5c000c8` completed SUCCESS 3/3**. Inspected policy-and-static logs: Portal Python **26/26**, Portal JS **7/7**, ACME locator **16/16**, SAN→Payments fixture **6/6**, Chromium synthetic **6/6**, kit inventory guard **12/12**; all PASS. This supersedes the PENDING T0 snapshot above. **T0=GO limited to exact-source CI; T1/T2 NOT_TESTED, T3 NOT_ATTESTED, T4/T5 NO_GO.** Chromium is an ephemeral Portal/fixture test, not the full Core→Temporal→Evidence→GLPI synthetic E2E.

### Artifact provenance exception — 2026-10-30 17:12 UTC

Downloaded #201 [artifact 12995044690](https://github.com/alimtalbi-ata/aiops/actions/runs/41096370024): ZIP CRC PASS, 2 entries, ZIP SHA256 `c1a5fcb6ed4819d67c1a06e252541674bfbcdf4db8332d2b88e529cd30fa6cbf`; screenshot SHA256 matches manifest `8a1720c3851833525d0e817a157d24826ff431fc84ce1d9d9742fd5595ebcaca`. **Metadata `git_sha=55b02788...` differs from PR head `1d3a9028...`**, because the capture uses GitHub `GITHUB_SHA` on a PR workflow (merge checkout). Require explicit `pr_head_sha`, `pr_base_sha`, `checkout_sha` and source-fixture digest in the next receipt contract. No runtime authentication or production qualification; this is only a synthetic browser capture, not a cumulative kit.

### Ollama artifact diagnostic refinement — 2026-10-30 17:14 UTC

Real #196 artifacts audited at member level: 1.7b **14/15 provider usage reports** across three failed repeats, token diagnostic sums 11875 (partial), 15195, 15241; all 0/5 cases analyzed per repeat because ValidationError/ReadTimeout. 4b **0/15 provider usage reports**, 15/15 ReadTimeout, token totals UNKNOWN. Both artifacts ZIP CRC PASS. Do not conflate provider-reported usage in failed calls with successful-model token economics or quality; no cost provenance. Exact details and ZIP hashes in AI benchmark baseline. #201 remains T0 GO only, not T2.

## 5/5 security convergence — 2026-10-30 18:xx UTC

- Fresh audit: #195 HEAD `2c824c1fdc034a76d17020aacfae1396684be341`, main-based, [Quality 41096853102](https://github.com/alimtalbi-ata/aiops/actions/runs/41096853102) SUCCESS. #201 previous HEAD `1d3a902877d556549425a95cd4cef792c5c000c8`, base `main@27deb9b1a66faf27df8d69b137a63451f7649d80`, [Quality 41096370024](https://github.com/alimtalbi-ata/aiops/actions/runs/41096370024) SUCCESS 3/3; Portal 26/26 Python, 7/7 JS, Chromium synthetic 6/6.
- #202 newer exact HEAD `9c462f0c6ff0e665220a3bc30247e2847b94900a`, [Quality 41101417585](https://github.com/alimtalbi-ata/aiops/actions/runs/41101417585) SUCCESS. Its strict four-key Core Run projection and negative authority-claim test have been ported **only** as two exact blobs into #201: `app/portal/acme_run_detail.py` blob `2500b19deff5fba79001c639c335d05c5acd7152`, `tests/test_portal_run_detail.py` blob `d0cc63acf753de0b4ad511006eab9383d9da68c7`. Commits `3356aac5` then `7bc825b3`. New #201 HEAD `7bc825b30e13c9a685192fde7486cad5632061fe`, [Quality 41104533241](https://github.com/alimtalbi-ata/aiops/actions/runs/41104533241) QUEUED at audit; **no exact-head PASS claimed yet**. Core rejects any unqualified extra identity/approval/ticket field with HTTP 503 UNKNOWN; no guard weakened.
- #204 failure-injection HEAD `1d03072417d09c124d09a6301ec517d7007b6ef0`, stacked on #194, Quality 41101379570, V2.8 41101379391, Offline 41101379498, Historical 41101379551 SUCCESS. Not integrated; runtime restart/lost ACK still NOT_TESTED. #205 mock ITSM xref HEAD `2964fdbb95484e654c07eb0d24e92b3eb3b9d3b7`, Quality 41082003327 SUCCESS, no live connector.
- #196 HEAD `747f0df4b8bae0fa0265b6dc568558a6a9057ad1`, stacked on #194, [Quality 41083049858](https://github.com/alimtalbi-ata/aiops/actions/runs/41083049858) FAILURE; Offline/Historical/V2.8 SUCCESS separately. Ollama evaluation 0 valid cases; provider usage in failed 1.7B calls is diagnostic only, not model qualification. Cost UNKNOWN.
- #201 Chromium artifact 12995044690 was a synthetic browser capture, not a kit; `git_sha` is PR merge checkout rather than PR head. Explicit head/base/checkout provenance remains required. No new cumulative ZIP or sandbox rollback.
- Gates: **T0 PENDING for new #201 head** (prior head GO limited), T1 NOT_TESTED, T2 NOT_TESTED, T3 NOT_ATTESTED, T4 NO_GO, T5 NO_GO. #188 preferred unmerged; #189 duplicate; #146/#153 auto-deploy unauthorized; #187 deferred. No Debian, GLPI write, LIVE or merge.


## 2026-10-30 19:10 UTC — 5/5 integration checkpoint (source-verified)

- **#201** base `main@27deb9b1a66faf27df8d69b137a63451f7649d80`: prior HEAD `7bc825b30e13c9a685192fde7486cad5632061fe`, [Quality 41104533241](https://github.com/alimtalbi-ata/aiops/actions/runs/41104533241) **SUCCESS 3/3** (grafana-real-integration, core-postgres-noc-real-integration, policy-and-static); 31 ahead / 0 behind. Artifact `12999887492` (`acme-explore-story-ci-simulated`, 237616 bytes, Actions digest `sha256:54aa3dbd4a1564805b281c6647c2fd64e0f2edce5f22d49ef39b873fbfaf2ca2`) is **synthetic story evidence**, not a cumulative installation kit. Archive member extraction and provenance audit for this artifact **NOT_RUN** in this checkpoint.
- **New #201 HEAD `7e4cbe9d75aedccf2078ca50d052e6d0796c284e`**: two narrowly scoped commits `70203a0f` and `7e4cbe9d`, 33 ahead / 0 behind main. Exact Git blobs from #202 HEAD `2e8e90371e89d8760fdfc98736dad7531acf9a3c`: `app/portal/acme_run_detail.py` `fe55bd199398eb92593d43deabea3d2cce6ae2b2`, `tests/test_portal_run_detail.py` `587578bf99dfc42bec10500f193cc16f0b59ef64`. Change permanently labels the ACME SAN→Payments story as **SYNTHETIC context, not linked to the requested Run or runtime-attested**, on 200/401/403/503; preserves UNKNOWN and no-store. **No exact-head Actions run observed yet**, so T0 on this new SHA **PENDING**; do not transfer previous success. Source #202 [Quality 41109683748](https://github.com/alimtalbi-ata/aiops/actions/runs/41109683748) SUCCESS 3/3, Portal Python 28/28 and JS 7/7, mock-only.
- **#204** stacked on #194, HEAD `f19473ac51c8ebbbba6bbd448e96118894f1a205`: [Quality 41110282633](https://github.com/alimtalbi-ata/aiops/actions/runs/41110282633) SUCCESS; V2.8/Offline/Historical SUCCESS. OIDC role/scope/expiry/nonce negative tests are offline; runtime lost-ACK/restart NOT_TESTED. **#196** HEAD `747f0df4b8bae0fa0265b6dc568558a6a9057ad1` still stacked on old #194 base `1fade3e5`; [Quality 41083049858](https://github.com/alimtalbi-ata/aiops/actions/runs/41083049858) FAILURE, real Ollama benchmark **NOT_QUALIFIED**; no model quality/cost promotion.
- Release gates: **T0 PENDING new exact head; T1 NOT_TESTED; T2 full Core→Temporal→Evidence synthetic E2E NOT_TESTED; T3 Debian NOT_ATTESTED; T4 cumulative kit/rollback NO_GO; T5 LIVE NO_GO**. Next exact test: #201 Quality at `7e4cbe9d`, then authenticated ephemeral single-Run ACME contract E2E, and independent ZIP extraction/member audit + disposable install/rollback. No merge, main/stable push, Debian operation, GLPI write, or LIVE.


### 2026-10-30 19:13 UTC — exact-head CI closeout (supersedes pending T0 above)

#201 HEAD `7e4cbe9d75aedccf2078ca50d052e6d0796c284e`: [Quality 41113172965](https://github.com/alimtalbi-ata/aiops/actions/runs/41113172965) **COMPLETED SUCCESS 3/3**. Inspected policy/static logs: Portal Python **28/28**, Portal JS **7/7**, Chromium synthetic **6/6**, cumulative kit guard **12/12** PASS. Artifact `13005150615` (`acme-explore-story-ci-simulated`, 237618 bytes, GitHub digest `sha256:6fdaab4220604c401c531999907df55e0a54d713920537ca22f5dfac2886bf69`) was listed but **not downloaded/member-audited**. T0 **GO_LIMITED exact head**; T1/T2 NOT_TESTED, T3 NOT_ATTESTED, T4/T5 NO_GO. These are mocked/ephemeral synthetic checks, not a complete authenticated Core→Temporal→Evidence run.


### 2026-10-30 19:16 UTC — audited Chromium artifact and source/checkout provenance fix

Downloaded #201 Quality 41113172965 artifact `13005150615` to isolated workspace: outer ZIP **237618 bytes**, SHA256 `6fdaab4220604c401c531999907df55e0a54d713920537ca22f5dfac2886bf69` matches Actions digest, **2/2 members CRC PASS** (`capture-metadata.json`, `explore-story-ci-simulated.png`). Screenshot SHA256 `8a1720c3851833525d0e817a157d24826ff431fc84ce1d9d9742fd5595ebcaca` matches metadata. Metadata `git_sha=43f3b5bdda21f40e0c4f63ac21740c42416d4daa` differs from source HEAD `7e4cbe9d...` because it denotes the PR merge checkout. `runtime_authenticated=false`, `production_qualified=false`, `live_remediation_authorized=false`, `glpi_ticket_id=null`; the archive is **not** an install kit or T2 E2E.

#201 commits `5bed2bf9945e1f107bffe36daa0849bea00164b8` (workflow passes source/base SHAs) and `cee6a834befbee47275e83651e7c0955528c51a0` (receipt separates `source_head_sha`, `base_sha`, `checkout_sha`; legacy `git_sha` remains checkout alias, and CI validates SHA formats). **New HEAD `cee6a834befbee47275e83651e7c0955528c51a0`**, main-based, 35 ahead/0 behind; exact-head CI **NOT_OBSERVED** at posting, so T0 PENDING for this new commit. Prior `7e4cbe9d` Quality 41113172965 SUCCESS 3/3 (Portal 28/28, JS 7/7, Chromium 6/6, kit 12/12). No runtime or release promotion.


### 2026-10-30 19:20 UTC — exact-head provenance contract qualified

#201 HEAD **`cee6a834befbee47275e83651e7c0955528c51a0`**, [Quality 41113479815](https://github.com/alimtalbi-ata/aiops/actions/runs/41113479815) **COMPLETED SUCCESS 3/3**. Inspected policy/static job: Portal Python **28/28**, JS **7/7**, Chromium E2E synthetic **6/6**, kit inventory gate **12/12** PASS. Downloaded artifact `13004397285`: ZIP size **237689 bytes**, SHA256 **`7f1821aefdbc687601bc2ae62163a7e777df03e8d6d939031880cead20b6ab93`** matches Actions digest; **2/2 CRC PASS**, screenshot SHA256 matches metadata. Receipt now proves **`source_head_sha=cee6a834befbee47275e83651e7c0955528c51a0`**, **`base_sha=27deb9b1a66faf27df8d69b137a63451f7649d80`**, **`checkout_sha=73a71c76fbe7660aa55e1c136591b3e3dbfd54a8`**, with legacy `git_sha` equal to checkout and distinct from source. `runtime_authenticated=false`, `production_qualified=false`, `live_remediation_authorized=false`, `glpi_ticket_id=null`. This fixes **capture provenance**, not tenant identity or T2 runtime.

**T0 GO_LIMITED on exact HEAD; T1 NOT_TESTED; T2 NOT_TESTED; T3 NOT_ATTESTED; T4 NO_GO; T5 NO_GO.** No new kit, install/rollback, Debian or LIVE proof.


### 2026-10-30 ~20:08 UTC — 5/5 canonical Core Run status port (exact-head pending)

#201 remains the **single main-based integration candidate**, base `main@27deb9b1a66faf27df8d69b137a63451f7649d80`, now HEAD **`8236c93460a160914247aaca8141253ebddf3aac`** (37 ahead/0 behind; open/unmerged). Ported exactly two source blobs from main-based #202 HEAD `d623c173b1414649298a31bc87e1948dde775395`: `app/portal/acme_run_detail.py` blob `28a7604ede814664c101e7748878060aed4ce7e6` via commit `81f9645d646e3c838450402ef84031391cff8c5d`, and `tests/test_portal_run_detail.py` blob `b1f51b1d0b613da88a7e5e980ca3c17465f7cf7b` via commit `8236c93460a160914247aaca8141253ebddf3aac`. The existing `shared.domain.STATUSES` on main and #201 was verified to match; reject forged/malformed Core Run status as HTTP 503 UNKNOWN. #202 [Quality 41117705285](https://github.com/alimtalbi-ata/aiops/actions/runs/41117705285) SUCCESS 3/3, 29/29 Portal Python and 7/7 JS in its own branch. #201 [new exact-head Quality 41120972224](https://github.com/alimtalbi-ata/aiops/actions/runs/41120972224) QUEUED at posting; its N/N NOT_OBSERVED. Previous #201 `cee6a834` [Quality 41113479815](https://github.com/alimtalbi-ata/aiops/actions/runs/41113479815) SUCCESS 3/3 does not transfer to this SHA.

#204 latest `b17f8a5c2bb573c2e207294207d7d096413548f3` remains stacked on #194; its [Quality 41118324370](https://github.com/alimtalbi-ata/aiops/actions/runs/41118324370) SUCCESS with 36/36 targeted HITL/outbox/contract tests, but OIDC, Postgres concurrency, lost ACK and Temporal restart are not runtime-attested. #196 `747f0df4` remains stacked on an older #194 base; [Quality 41083049858](https://github.com/alimtalbi-ata/aiops/actions/runs/41083049858) FAILURE (0 valid Ollama repeats). T0 PENDING new #201 SHA; T1/T2 NOT_TESTED, T3 NOT_ATTESTED, T4/T5 NO_GO. No cumulative kit or deployment proof.

## 5/5 exact-head checkpoint — 2026-10-30 21:10 UTC (22:10 Europe/Paris)

- [#201](https://github.com/alimtalbi-ata/aiops/pull/201) remains the sole **draft, unmerged, main-based** integration candidate: base `main@27deb9b1a66faf27df8d69b137a63451f7649d80`, HEAD `8236c93460a160914247aaca8141253ebddf3aac`, **37 ahead / 0 behind**, 41 changed paths. [Exact-head Quality 41120972224](https://github.com/alimtalbi-ata/aiops/actions/runs/41120972224) **COMPLETED SUCCESS 3/3**: `policy-and-static`, `core-postgres-noc-real-integration`, `grafana-real-integration`. Logs confirm Portal Chromium 6/6, kit inventory negative tests 12/12, Core/PostgreSQL NOC HTTP 5/5, Core DEMO Policy integration 14/14, real Policy HTTP 8/8, Grafana HTTP readiness 1/1. These are **separate CI scopes**, not a connected Core→Temporal→Evidence→GLPI T2 receipt.
- Downloaded and inspected the exact-run artifact [13007279749](https://github.com/alimtalbi-ata/aiops/actions/runs/41120972224/artifacts/13007279749): ZIP SHA256 `083ec62ececcbb11e2c47ef777619e86c7c5d9bfa11d9ff67713e4502d5718dc`, **2/2 CRC PASS**; screenshot SHA256 `8a1720c3851833525d0e817a157d24826ff431fc84ce1d9d9742fd5595ebcaca` matches metadata. `source_head_sha=8236c93460a160914247aaca8141253ebddf3aac`, `base_sha=27deb9b1a66faf27df8d69b137a63451f7649d80`, `checkout_sha=959a34e131309d0b83c8f1e4e81a81490ab036db`. `runtime_authenticated=false`, `glpi_ticket_id=null`, `production_qualified=false`. This **is not a deployment kit**.
- [#195](https://github.com/alimtalbi-ata/aiops/pull/195) previous HEAD `3785d85495580f9c9f41fa59211eeb6d805c2c66` [Quality 41121057494](https://github.com/alimtalbi-ata/aiops/actions/runs/41121057494) **SUCCESS 3/3**; any new documentation commit requires a fresh exact-head run.
- [#204](https://github.com/alimtalbi-ata/aiops/pull/204) advanced to `7372be2098ef955db9a4e14f2b94340ac447d509`, still stacked on #194; Quality 41126426770, Offline 41126426804, Historical 41126426764, V2.8 41126426754 **SUCCESS**. Source review: `app/core/main.py` differs from #201; `app/worker/workflow.py`, `db/migrations/011_hitl_decision_outbox.sql`, `app/core/hitl_identity.py`, `app/shared/hitl_identity.py` are absent from #201. Do **not** cherry-pick the full stack without migration and ownership review.
- [#196](https://github.com/alimtalbi-ata/aiops/pull/196) HEAD `747f0df4b8bae0fa0265b6dc568558a6a9057ad1`, still stacked on stale #194 base `1fade3e5`; Quality 41083049858 **FAILURE** (two Ollama CPU jobs), three other workflows SUCCESS. Real-model scored repeats **0**, costs and qualified p50/p95 **UNKNOWN**; deterministic CI placeholders are not real-model economics. `app/intelligence/main.py` and `tools/evaluate_ai_core.py` are absent from #201; `compose.yml` and `.github/workflows/quality.yml` differ across candidate/HITL/AI branches.
- **Release gate:** T0=GO_LIMITED on exact #201 CI; T1=NOT_TESTED for complete ephemeral integration; T2=NOT_TESTED for single Incident/Run Core→Temporal→Evidence→GLPI; T3=NOT_ATTESTED Debian; T4=NO_GO (no cumulative install/upgrade/rollback); T5=NO_GO LIVE. `RELEASE_STABLE=NO_GO`.

**Next precise gate:** establish one isolated canonical tenant/incident/run fixture with Core+Temporal+Evidence source IDs, append-only evidence hashes, Policy SIMULATE and independent no-effect verification; fail closed on missing ticket/tenant/identity links. Only then call it T2. 5/5 owns dependency ordering/CI/release; no second scheduler or UI.
