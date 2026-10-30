# AIOps 2.0 — 48-hour convergence and customer demonstration plan

**Start:** 2026-10-30. **Target window:** 48 hours from execution start.  
**Outcome:** one coherent, repeatable, evidence-backed enterprise synthetic journey and an installable cumulative kit candidate.  
**Not a promise:** production cutover, LIVE remediation, real Checkmk/SSO/GLPI write access or full ITIL certification.

## 1. Delivery strategy

Use the existing ACME SAN → Payments scenario as the single customer narrative. Stop adding parallel demo paths. Converge the existing PRs and branches around one versioned reference architecture and one release candidate. Keep main protected; use small reviewed PRs. Every task reports commit SHA, exact test command, N/N, CI URL, artifact checksum and remaining caveat.

### Work in four phases

| Window | Objective | Work | Exit gate |
|---|---|---|---|
| H0–H4 | Freeze scope and inventory | Verify exact heads/CI for #185, #190, #192–194, #188/#189, #187; map duplicate PRs and source/runtime drift; select one scenario spine; freeze canonical IDs and acceptance criteria | Architecture baseline + reuse register + no conflicting deploy schedules |
| H4–H12 | Make the customer journey coherent | Reuse the verified ACME fixture/Twin edges, Core Run locator, Demo Studio timeline, AI ledger, Evidence refs, GLPI read-only adapter and Policy SIMULATE projection; wire one operator path; eliminate UNKNOWN/misleading states | One deterministic synthetic journey with exact Incident/Run/Ticket/Evidence links or explicit UNKNOWN |
| H12–H24 | Benchmark and govern AI | Run existing Analyst/Critic evaluation dataset; instrument per-call latency and provider-reported usage; report quality, token use, cost provenance, retries, abstentions and actionability; add budget controls only where usage data is reliable | Reproducible benchmark report with dataset/model/prompt hashes and no fabricated token/cost values |
| H24–H36 | Test failure and ITIL controls | Exercise duplicates, stale/conflicting evidence, prompt injection, Critic rejection, Policy block, HITL reject/approve notification, outbox lease expiry, Worker restart and sandbox-only postconditions; validate incident/problem/change lifecycle views | Negative-path evidence and explicit recovery/rollback results |
| H36–H48 | Customer rehearsal and release kit | Run from clean isolated environment; package source/config templates/migrations/scripts/docs; verify install/upgrade/rollback instructions and SHA-256; record demo storyboard, limitations and operator runbook | Rehearsal report, cumulative ZIP/checksum, exact GO/NO-GO by tier |

## 2. Five parallel schedules — keep ownership and interfaces separate

The existing five ChatGPT schedules are retained; Schedule 5/5 is the integration/architecture/release owner.

| Schedule | Exclusive scope | Must hand off |
|---|---|---|
| 1/5 ACME | Existing synthetic Incident/Run, SAN→Payments Twin path and reproducible locator | verified incident_id/run_id, source-backed edges, command, fixture hash |
| 2/5 Portal | Existing Portal/Demo Studio operator journey and source/status labels | route list, screenshots only if captured, tests, exact run deep links |
| 3/5 NOC/Evidence/GLPI | Read-only incident↔run↔ticket↔evidence reconciliation | IDs, evidence refs, source/freshness, GLPI read result or UNKNOWN |
| 4/5 Policy/HITL | Policy SIMULATE, proposal/decision display, HITL deny/approve notification contracts | policy version/reasons, proposal hash, role/scope, effect_allowed=false |
| 5/5 Architecture/release | Reference architecture, ADRs, interface convergence, AI benchmark, CI/release evidence, conflict resolution | single candidate, traceability matrix, manifest, SHA, GO/NO-GO |

No schedule may edit another schedule's exclusive module without an explicit handoff. Schedule 5/5 does not invent source facts or bypass gates; it integrates evidence and resolves duplicate branches/PRs.

## 3. Existing work to reuse first

| Existing work | Reuse decision | 48h action / limitation |
|---|---|---|
| PR #185 ACME integrated candidate | Scenario spine candidate | It reports 5/5 convergence, 8/8 exact Git blobs and prior 6/6 quality jobs plus package checks. Revalidate its current head; keep DEMO_LOCAL=GO / RELEASE_STABLE=NO_GO until transport/deployer/runtime proof is closed. Do not merge its 72-file diff blindly. |
| PR #190 INGEST stage/artefact visibility | Targeted correctness fix | Re-run current-head CI; merge only if tests pass and patch remains narrow. |
| PR #192 Portal HITL inbox + GLPI read-only Copilot | Reuse read-only ticket context and inbox | Reconcile with #194 identity/approval contract and #193 proposal fastpath; no browser-supplied approver identity. |
| PR #193 GLPI→Copilot→HITL proposal fastpath | Reuse guarded proposal mapping | Require same Run, validated Critic, evidence subset and no execution authority; test against current Core schema. |
| PR #194 Temporal HITL + OIDC + outbox | Reuse safety contracts | Prior head 1fade3e passed its observed CI; confirm latest branch head before port. Portal SSO and full approval/outbox runtime failure injection remain open. |
| PR #188 scheduled quality + 15-min read-only runtime smoke | Preferred schedule implementation | Merge only after review; runtime smoke remains inactive until repository-scoped Debian runner is installed and online. |
| PR #189 2-hour quality cron | Duplicate schedule candidate | Do not enable alongside #188. Consolidate to one nightly full suite + PR/push + optional read-only runtime smoke. |
| PR #187 Loki/Tempo/OTel | Deferred | Use existing Prometheus/Grafana first. Add log/trace stack only after resource, persistence, retention, security and integration review. |
| PR #146 / #153 Debian auto-deploy cron | Disabled / not a 48h objective | No auto-deploy or stable promotion until exact source transport, approved branch, backup, rollback and deployed SHA equivalence are proven. |
| PR #177 Portal UI P0 | Selective reuse only | Historical CI included Policy and Runtime failures and a deployer transport gap. Re-run current tests and port only proven patches. |
| PR #59 / issues #60–68 | Long-term backlog and practice map | Keep the 12-week plan as post-demo roadmap; 48h work is a vertical slice, not a substitute for full program delivery. |

## 4. Acceptance criteria for the 48-hour customer demo

### Business and ITIL
- One P1 synthetic Payments incident with impact/urgency and priority rationale.
- One canonical Core Incident and Run; no duplicate Run or guessed cross-system IDs.
- CI/service path shown with source and freshness.
- N1 acknowledgement, N2/N3 escalation, incident commander and customer update represented.
- GLPI ticket linked only after authenticated read confirms the relation.
- Evidence-backed Analyst hypothesis, independent Critic result and deterministic Policy decision.
- HITL proposal details include risk, scope, expiry, evidence, preconditions, postconditions and rollback.
- SIMULATE effect is visibly synthetic and cannot mutate real infrastructure.
- Verification, reconciliation and Problem/PIR/knowledge follow-up shown as separate outcomes.

### AI benchmark
- Fixed dataset version/hash and blinded adversarial cases.
- Analyst and Critic quality metrics include severity accuracy, grounding/citation validity, freshness, contradiction/stale detection, injection resistance, action safety and Critic disposition.
- Every call has model/provider/prompt version and measured latency.
- Token counts/cost are reported only when provider returns usage or a validated tokenizer/pricing source is pinned; otherwise null/UNKNOWN.
- Per-run token/cost budget, retry limit, timeout, concurrency and max context are visible.
- Compare at least the currently configured provider/model with one feasible alternative only if both can be run reproducibly in the same environment.

### Engineering/release
- Exact branch/commit and CI links.
- Unit, contract, real-service ephemeral integration, synthetic E2E and failure-injection results are separate.
- Clean install/upgrade/rollback scripts and configuration template; no secrets or live DBs in package.
- Manifest with file hashes, source commit, migrations, image references and test evidence.
- Runtime/deployed checks are labelled NOT RUN if no approved Debian runner/access exists.

## 5. Stop conditions

Stop the affected lane and mark BLOCKED if: tenant or actor identity is ambiguous; evidence freshness/provenance is absent; Core/Temporal state diverges; model output is malformed or ungrounded; Critic rejects; Policy returns BLOCK/UNKNOWN; proposal hash/scope changes; outbox lease is lost; executor ownership/fencing cannot be verified; package omits required files; rollback is untested. Do not convert BLOCKED/UNKNOWN into PASS for demo convenience.

## 6. Release decision

The 48-hour release target is a customer-demo kit at T2 synthetic E2E, plus T3 read-only checks where actually verified. It is not a production release. LIVE remains NO-GO until identity federation, real-source qualification, tenant RBAC, transactional outbox failure injection, post-approval Policy recheck, executor fencing, independent verification, GLPI lifecycle reconciliation, HA/PRA and change approval are complete.


## Current execution status — 2026-10-30 12:25 UTC

- H0–H4 architecture inventory, target architecture, ITIL 4 mapping, benchmark governance and reuse register are documented in PR #195.
- PR #195 latest docs head has a fresh quality workflow in progress after exact-head evidence updates.
- AI invocation telemetry PR #196 passed 6/6 AIOps quality jobs plus Offline Integrity, Historical Trace and V2.8 Core on its exact corrected head. Its synthetic benchmark artifact is documented separately.
- The RC1.4 package artifact has been downloaded and audited: 405/405 SHA-256 checksums pass; manifest says real-model and production qualification NOT_RUN; the package lacks the new PR #195 architecture documents.
- Schedules 1/5–4/5 have been reoriented to create clean main-based minimal PRs; immediate runs requested. Their previous branches are divergent and are not to be merged wholesale.
- Schedule 5/5 is the architecture/release integrator; its immediate run is asynchronous.
- The final cumulative kit is not yet complete. It must be rebuilt after main-based code integration and include the new architecture/ITIL/benchmark docs plus exact manifest/checksum and install/rollback evidence.

## 2026-10-30 14:00 UTC — actual H0–H12 integration progress and next gate

5/5 opened [draft #201](https://github.com/alimtalbi-ata/aiops/pull/201) at `2ceda14c8a21fe71e88b3228879799e6c37a5387`, base `main@27deb9b1`, 22 changed paths (6 exact 1/3/4 code/test files, 14 exact docs from #195, Quality offline test wiring, one provenance report), **0 behind main**. This is the first coherent main-based *staging* SHA, not the final release/kit. T0 combined Quality [41068355452](https://github.com/alimtalbi-ata/aiops/actions/runs/41068355452) PENDING at capture. Immediate sequence: inspect exact-head test steps/results; require 2/5 Portal main-based route and Core protected Evidence refs; reconcile #190/#192–#196 overlaps and migration 011/OIDC/AI telemetry; build/inspect cumulative ZIP; isolated install/upgrade/rollback/failure injection. No customer-facing real source/GLPI/model assertion yet.


## 2026-10-30 14:46 Europe/Paris — active 48-hour execution clock

**Target customer rehearsal deadline:** 2026-11-01 14:46 Europe/Paris.  
**Current release posture:** synthetic customer-demo target only; cumulative installation kit and Debian runtime remain NO-GO; LIVE remains NO-GO.

### Work completed / revalidated

- Target architecture, ITIL 4 operating model, ADRs, reuse register, 48-hour plan, customer story, benchmark governance, schedule/cron safety and RC1.4 kit audit exist in the main-based documentation PR #195.
- Exact prior #195 documentation head `f9617b09` passed Quality 41061315909 (3/3); subsequent evidence refreshes are awaiting their own exact-head CI.
- Main-based scoped PRs #197 (UTC Evidence preflight), #198 (synthetic Run locator) and #199 (Policy SIMULATE fixture) each have exact-head Quality SUCCESS. Their narrow limits remain explicit; they are not a combined integration proof.
- Existing #194 HITL/OIDC/outbox and #196 AI invocation telemetry stacks have all their previously observed exact-head workflows green, but their bases are stacked and require selective integration before a main-based release.
- The latest deterministic AI artifact #12976497171 records five cases, ten calls, provider usage 10/10, 20 fixed placeholder tokens, P50 3.01 ms/P95 4.54 ms, and cost UNKNOWN. It is not real-model performance.
- All five schedules were reoriented; 2/5 Portal was re-enabled; immediate runs were requested. The requests are not completion evidence.

### H0–H4 — architecture / integration control

- Freeze one canonical Incident/Run, service, CI, Evidence and ticket identity contract.
- Use #195 as the sole architecture/ADR baseline; refresh exact-head CI after doc updates.
- Review #197/#198/#199 and keep each scope honest.
- Inspect #185, #190, #192–#194 and #196 by changed-file intersection; port minimal changes to a clean main-based branch only when dependencies and tests are understood.
- Owner: 5/5; workstream inputs: 1/5–4/5.

### H4–H12 — operator journey and source integrity

- 1/5: verify SAN→Payments graph and canonical synthetic Run; never infer actual Payments impact from seed topology.
- 2/5: implement a minimal main-based read-only Run detail route from existing Portal routers and Core APIs; show Evidence as UNKNOWN while the protected refs API is absent.
- 3/5: preserve fail-closed UTC preflight; qualify authenticated, tenant-scoped GLPI/Evidence reads only when endpoints and test credentials exist.
- 4/5: show Policy decision/reasons and proposal state separately; no simulated human approval or effect authority.
- Exit: one coherent synthetic story with exact IDs and provenance or explicit UNKNOWN.

### H12–H24 — real-model benchmark and token control

- Run the existing evaluator through the actual Analyst/Critic Intelligence service against Ollama Qwen3 4B and 8B, three repeats each, using one dataset SHA and prompt version.
- Preserve raw per-call provider usage, latency, retries, case-level results and failure reports.
- Compare severity, grounding, freshness, injection, contradiction, stale detection, Critic disposition and proposal actionability.
- Do not infer token usage from request bytes or estimate price. Cost stays UNKNOWN without approved versioned pricing/invoice evidence.
- Add token/spend budget enforcement only after authenticated tenant identity and a reliable tokenizer/provider usage source are available.
- Exit: reproducible model comparison artifact or explicit BLOCKED/FAIL with the reason; no forced PASS.

### H24–H36 — resilience / ITIL control validation

- Test duplicate/out-of-order events, replay, stale/conflicting Evidence, prompt injection, Critic reject, Policy BLOCK/UNKNOWN, HITL reject/revoke, outbox lease expiry, lost acknowledgement and Temporal/Worker restart.
- Validate Major Incident, escalation N1/N2/N3, Incident Commander, Problem/PIR, Knowledge and Change Enablement projections against the canonical Run.
- Keep all remediation sandbox/no-effect; independently verify pre/postconditions in the simulation only.

### H36–H48 — cumulative kit and client rehearsal

- Create one main-based release-candidate SHA only after the code PRs are integrated/reviewed.
- Package the complete migration chain, config template, app services, scripts, test suite, runbooks, ITIL story, benchmark reports, manifest and checksums.
- Audit actual ZIP members and file hashes; compare package manifest to exact Git SHA and image references.
- Run clean extraction, offline repackage, disposable install/upgrade/rollback and synthetic E2E.
- Rehearse the ACME P1 SAN→Payments story; clearly label synthetic, UNKNOWN and NOT_TESTED fields.
- Exit: cumulative kit with exact checksum and a tiered GO/NO-GO. No Debian production deploy or LIVE remediation in this 48h target.

### Stop conditions

A missing endpoint, tenant ACL, provider usage field, price source, OIDC identity, outbox recovery test, package member or rollback proof is a BLOCKED/UNKNOWN result, not a reason to invent a fallback. If a model fails quality gates, retain the failure and select/adjust the model or prompt only through a new versioned benchmark.

## 2026-10-30 14:16 UTC — release-path incremental gate

The 5/5 staging [#201](https://github.com/alimtalbi-ata/aiops/pull/201) added a stdlib-only cumulative ZIP inventory/source correspondence guard at HEAD `03a5b0cce44e56d7ae315ee7df16e850a5e35b11`, with 10/10 offline negative-path tests PASS and a new Quality job step (new exact-head CI not yet confirmed). This is a **precondition**, not a substitute for the missing cumulative kit. Next: selectively reconcile #194 migration/OIDC/outbox and #196 telemetry on a clean main-based tree; generate one exact-SHA package; require `python3 tools/check_cumulative_release_kit.py --kit <zip> --expected-source-sha <40hex> --source-dir <exact-clean-checkout>` to PASS; then separately exercise clean install/upgrade/rollback, synthetic E2E and read-only smoke. Do not claim T1–T4 from archive integrity.

## 2026-10-30 14:23 UTC — 5/5 exact-source release preflight

Single staging [#201](https://github.com/alimtalbi-ata/aiops/pull/201) at `84f6cf1c3656c8c9b74acaf6036cc0c443827aad`: [Quality #41071155614](https://github.com/alimtalbi-ata/aiops/actions/runs/41071155614) SUCCESS 3/3, 12/12 release inventory tests PASS. This closes only the **offline source-provenance guard** (dirty checkout and non-root source directory now fail). Next: reconcile #194/#196 exact contracts and selectively port migration 011/OIDC/outbox and provider telemetry onto clean main-based source; build a real cumulative ZIP and verify its contents, exact HEAD, checksums, clean install/upgrade/rollback and synthetic ACME journey. T1/T2/T4 remain NOT_TESTED; T3 NOT_ATTESTED; T5 NO_GO. No Debian or LIVE approval.

## 2026-10-30 14:28 UTC — 5/5 handoff and next critical gate

- Selectively integrated the four changed #202 Portal/session/test blobs (ancestor verified **4/4**) into the one main-based #201 candidate at `178bbf71f5884c5a8b54f38ca815c6f76ea0ffb9`; no other module, workflow, Compose or config overwritten. #202 source exact-head Quality [41071596535](https://github.com/alimtalbi-ata/aiops/actions/runs/41071596535) SUCCESS 3/3 with Portal Python **21/21** and JS **6/6**; **combined #201 exact-head CI pending** at commit.
- Preserve `UNKNOWN` for tenant ACL, GLPI ticket binding, Evidence refs, Twin impact/freshness and runtime provenance. Canonical customer story uses the reported Core Incident/Run pair only as **operator-reported, not freshly authenticated**. The SAN→Payments dependency is inverse of current Twin API traversal; seed 92ms Payments VERIFY is not a real SLO breach. Do not invent impact or P1 priority evidence.
- Next tests: combined #201 Quality exact SHA; synthetic T2 journey with authenticated Core/Evidence refs; Core-owned tenant-scoped GLPI binding (#203); selective main-based port of #194 migration 011/OIDC/outbox and #196 telemetry with collision analysis; failure-injection #204 exact-head completion. Require one clean-source cumulative ZIP, source manifest SHA, member hashes, sandbox install/upgrade/rollback before release.
- T0 is GO **only for previously green #201 SHA**; the new head remains PENDING until CI completes. T1/T2 NOT_TESTED, T3 NOT_ATTESTED, T4 NO_GO, T5 NO_GO. #188/#189 still unmerged; #146/#153 disabled; no Debian/GLPI/LIVE action.
