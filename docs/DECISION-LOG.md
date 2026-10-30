# AIOps 2.0 — Decision Log

**Author:** Abdelhalim Talbi  
Use this file for durable architecture/product decisions. Add new entries; do not silently rewrite history. Status may be changed with a dated rationale.

## ADR-0001 — Keep one canonical runtime

- **Date:** 2026-10-19
- **Status:** Accepted
- **Decision:** Consolidate around the AIOps 2.0 runtime and its canonical Run/Incident state; do not build another parallel orchestration/control plane.
- **Reason:** Reduce duplicate state, integration drift and operational burden.
- **Consequences:** Historical platforms are reused through adapters and explicit contracts; production cutover requires qualification and rollback.

## ADR-0002 — Reuse AIOps v1/V145 before rebuilding

- **Date:** 2026-10-19
- **Status:** Accepted
- **Decision:** When a historical capability is faster to reuse and can meet current safety/quality standards, adapt it rather than rewrite it.
- **Candidates:** Decision intelligence; evidence fusion/matrix/acquisition/enrichment; semantic evidence engine; decision adapter; functional bridge/read model; decision cockpit.
- **Qualification condition:** Inspect source, dependencies, contract, tests, ownership, data stores and actual behavior. Directory presence or old demo status is insufficient.
- **Consequences:** Maintain a reuse matrix and record why each component is reused, adapted, replaced or retired.

## ADR-0003 — Keep the Portal out of direct database writes

- **Date:** Existing repository README; reaffirmed 2026-10-19
- **Status:** Accepted; implementation must be tested
- **Decision:** Portal calls Core APIs; Core owns state transitions and persistence boundaries.
- **Reason:** Consistent authorization, validation, audit and schema evolution.

## ADR-0004 — Durable orchestration owns Run progression

- **Date:** Existing repository README; reaffirmed 2026-10-19
- **Status:** Accepted; implementation must be tested
- **Decision:** Temporal/Worker own durable workflow progression; n8n is an integration boundary and must not own Run state.
- **Reason:** Retry, recovery and lifecycle consistency.

## ADR-0005 — Evidence and events are auditable records

- **Date:** Existing repository README; reaffirmed 2026-10-19
- **Status:** Accepted; implementation must be tested
- **Decision:** Events and Evidence are append-only; provenance/freshness and decision links are required. Unknown or missing proof stays `UNKNOWN`.
- **Reason:** Reproducibility, forensic traceability and safe decisions.

## ADR-0006 — Fail-closed live remediation

- **Date:** Existing repository README and prior project constraints; reaffirmed 2026-10-19
- **Status:** Accepted
- **Decision:** Live actions require deterministic policy authorization, explicit mode, validated identity/ownership/fencing, preconditions, approval when required, idempotency, verification and reconciliation. LLM confidence alone never authorizes a high-risk action.
- **Reason:** Prevent duplicate ownership, stale decisions, unsafe actions and unverified recovery.

## ADR-0007 — Preserve the PC11K5 fencing invariant

- **Date:** 2026-10-19
- **Status:** Accepted
- **Decision:** Preserve the invariant chain: claim → fencing/ownership → preconditions → effect → evidence → reconciliation. No integration may weaken stale-owner/duplicate-owner blocking.
- **Reason:** Correctness under concurrency and partial failure.
- **Qualification:** Existing fencing/concurrency/PostgreSQL tests must be included in regression runs.

## ADR-0008 — GitHub is the durable handover source

- **Date:** 2026-10-19
- **Status:** Accepted
- **Decision:** Keep continuity, architecture, component descriptions, decisions, test protocols, release notes and next actions in `alimtalbi-ata/aiops`. Work on branches, commit, and open PRs; preserve `main`.
- **Rule:** Every significant development session must update the relevant docs before closing. Verify commit/PR URLs before reporting completion.

## ADR-0009 — Separate test evidence by strength

- **Date:** 2026-10-19
- **Status:** Accepted
- **Decision:** Label evidence as source inspection, static test, unit/contract test, isolated integration, synthetic E2E, or live production verification.
- **Reason:** Avoid claiming runtime or production qualification from static evidence.

## ADR-0010 — Block LIVE execution until real adapters are qualified

- **Date:** 2026-10-19
- **Status:** Accepted as an interim safety control; merged in PR #5 at commit `493336fb51fcda41d1ece8fc1822bb13f1ef232c`
- **Decision:** The current worker must not progress LIVE runs by emitting generic stage-completion evidence or fixed confidence values. It records an explicit adapter-unavailable event and transitions the Run to BLOCKED.
- **Reason:** The repository does not yet provide qualified live evidence acquisition, CMDB/RAG/analyst/critic integrations, HITL approval evidence, or verified remediation/rollback adapters. Synthetic placeholder claims must not be marked non-synthetic merely because mode is LIVE.
- **Policy changes:** P1 always escalates; critic validation is required input rather than a trusted default; LIVE actions require explicit evidence freshness, preconditions, fencing/ownership, and human approval for effects.
- **Consequence:** LIVE execution remains intentionally unavailable until each adapter and end-to-end failure/recovery path is implemented and qualified. DEMO/REPLAY/STORY remain explicitly synthetic.
- **Qualification:** Deterministic unit cases are added, but they must be executed in the pinned runtime before merge. This ADR does not claim production qualification.

## ADR-0011 — Generate secrets on fresh install and reject insecure defaults

- **Date:** 2026-10-19
- **Status:** Accepted; merged via [PR #7](https://github.com/alimtalbi-ata/aiops/pull/7) at commit `1bdd7235687f8b2c7081278e4dd86b8a17939ff3`.
- **Decision:** New installs generate random credentials and set restrictive `.env` permissions. Existing `.env` files are not silently overwritten or rotated. Preflight rejects known defaults unless the operator explicitly opts into isolated demo mode. Internal admin/token values must match under the current service contract.
- **Reason:** Prevent accidental deployment with public, predictable demo credentials without breaking existing database credentials through automatic rotation.
- **Qualification:** CI tests generation, permission mode, non-rotation, default rejection, demo opt-in and token consistency. Full deployment/upgrade qualification remains required.

## ADR-0012 — No insecure application or Compose credential fallback

- **Date:** 2026-10-19
- **Status:** Accepted; merged via [PR #9](https://github.com/alimtalbi-ata/aiops/pull/9) at commit `e6251c1ce195937b1af6019e389c9f6b3f68e2dc`.
- **Decision:** Application services fail fast when internal credentials are absent. Compose requires secret variables rather than silently substituting known demo values. The secure environment template has blank secret fields; the known-value demo template is separate and opts into demo mode explicitly.
- **Reason:** A standard or direct Compose deployment must not silently start with a public development credential.
- **Consequence:** All services using the shared HTTP client must receive the same internal token through configuration. The installer generates it once and assigns it consistently to the current admin/internal aliases.
- **Qualification:** CI passes Python compileall, policy and secret-preflight tests, static audit, and Compose configuration validation. Full container build and synthetic E2E remain outstanding.

## ADR-0016 — Portage ACME synthetic impact sans autorité GLPI (2026-10-27)

- **Statut:** Proposition en PR #50 ; non qualifiée LIVE.
- **Décision:** Porter depuis PR #36 le validateur de graphe ACME et la vue de simulation en lecture seule, sans fusion massive et sans toucher au jumeau canonique en base.
- **Sécurité:** Les identifiants `SIM-ACME-*` et `SIM-GLPI-*` proviennent du SHA-256 du fixture, et ne sont jamais des identifiants Core/Temporal/GLPI. `ticket_id=null`, `runtime_attested=false`, `live_remediation_authorized=false`.
- **Qualification:** Tests unitaires du graphe, des modes interdits, des cycles, du montage portail et des erreurs ; CI GitHub Actions, sans services réels. Une vraie corrélation ITSM nécessitera un adaptateur authentifié et une attestation de ticket.


## ADR-0017 — Synthetic RAG references are never runtime evidence (2026-10-27)

- **Status:** Accepted for synthetic-only reference use; merged via PR #54 at `b44b7f2ffcddecaf5229a4e5fd4c745e038a0c98`, [CI 40594299546](https://github.com/alimtalbi-ata/aiops/actions/runs/40594299546) green. Not qualified for live RAG.
- **Decision:** Reuse PR #36's six synthetic NOC diagnostic fixtures through a strictly read-only portal drilldown, with exact asset matching, immutable file/doc SHA-256 citations and explicit `SYNTHETIC_SIMULATION_ONLY` provenance. Do not call an LLM or blend synthetic references with observed monitoring facts.
- **Safety:** The endpoint requires the existing operator read token, rejects malformed/missing catalogs and unsafe asset identifiers, and returns `UNKNOWN` when no matching fixture exists. Tenant ACL is not qualified; only public synthetic fixture content is eligible. No Core writes, no remediation and no LIVE evidence claims.
- **Promotion gate:** A future observed RAG path needs authenticated tenant/actor identity, ACL filtering before retrieval and before citation, source freshness and authority, exact canonical Run/Incident binding and independently tested NIM/Ollama grounding. CI fixture tests alone do not meet this gate.

## ADR-2026-10-28-P0 — Authenticate Core/Twin bootstrap before upstream reads

- **Date:** 2026-10-28 10:04 Europe/Paris
- **Status:** Accepted — merged PR #114 at cea1ed7b54ed34cf4b036b6d5f20bf968c9dac09
- **Decision:** Reuse the merged NOC viewer token guard for the Core/Twin bootstrap and serve an anonymous UNKNOWN-only portal shell. The browser may fetch read models only after explicit one-shot Bearer entry, without cookies or persistent storage.
- **Reason:** The existing public portal route contacted Core/Twin and exposed incident/run metadata without authorization. Shared auth avoids competing contracts.
- **Limits:** Shared token does not establish tenant ACL, SSO, real upstream integration or LIVE attestation. DEMO/Copilot writes remain separate unmerged security work.

## ADR-0018 — A caller-provided HITL boolean cannot authorize LIVE effects (2026-10-28)

- **Status:** Accepted for deny-only source behavior; [PR #118](https://github.com/alimtalbi-ata/aiops/pull/118) merged at `b33f655695949d6fef9e7d72b537d9810859c494` with [post-merge CI #40664759313](https://github.com/alimtalbi-ata/aiops/actions/runs/40664759313) green. No LIVE qualification.
- **Decision:** Policy must reject LIVE `EXECUTE`, `RESOLVE`, `REMEDIATE` and `CANCEL` even with `human_approved=true`. This field does not prove authenticated approver identity, distinct proposer, expiration, single-use consumption or immutable incident/Run/recipe/target/parameter binding.
- **Reuse:** Selectively port the deny-only fence from draft #76 onto current `main`. PR #36's simulation-only `execution_fence.py` demonstrates that reservation is not permission; its missing `autonomy_store` is not bulk-imported.
- **Preserve:** LIVE P1 escalation, missing-evidence UNKNOWN, DEMO/REPLAY/STORY SIMULATE, and non-mutating LIVE OBSERVE/ENRICH decisions. No command executor is enabled.
- **Qualification:** Existing `quality.yml` runs Policy unit tests and in-process FastAPI request tests. Core/RBAC/Temporal/Evidence, real container E2E and LIVE remain NOT_TESTED; HTTP in-process is not integration with a real service.
- **Rollback:** Never restore the unsafe boolean bypass; replace this fence only with a reviewed Core-owned, authenticated, expiring, one-use HITL proof validated atomically at the effect boundary.


## ADR-2026-10-28-P0 — Core synthetic NOC projection before tenant ACL

- **Status:** Candidate on dedicated branch; not production qualified.
- **Decision:** Add a dedicated internal-token authenticated, synthetic-only, allowlisted Core Run identity endpoint for the signed NOC join. Reuse the existing NOC tenant-scope refusal in a shared helper rather than silently accepting tenant claims. Require an actual synthetic Incident record in PostgreSQL. Keep the older Core endpoints unchanged in this small lot.
- **Qualification gate:** Existing GitHub quality workflow with real ephemeral Core HTTP and PostgreSQL 16, plus negative and non-regression tests. An internal token is service authentication, **not** tenant-bound actor identity. No A/B authorized reads or LIVE evidence until Core-owned tenant RBAC is implemented.
- **Rollback:** Revert the small Core/portal/shared/test/workflow patch together; do not restore anonymous NOC correlation or weaken the LIVE fence.


## ADR-0017 — One enterprise control plane and 48-hour vertical-slice convergence

- **Date:** 2026-10-30
- **Status:** Proposed on `architecture/48h-convergence-20261030`; architecture review required before implementation promotion.
- **Decision:** Converge all active AIOps work on one Core-owned Incident/Run lifecycle, Temporal-owned orchestration, append-only Evidence, sourced Twin/CMDB, advisory Analyst/Critic, deterministic Policy, Core-owned HITL ledger, separately fenced execution and Portal read models. Use the ACME SAN→Payments P1 synthetic journey as the single 48-hour customer demonstration.
- **Reason:** The repository contains many overlapping open PRs and feature branches. A single vertical slice with immutable identifiers and evidence is more demonstrable and maintainable than multiple disconnected feature demos or a parallel rewrite.
- **ITIL 4 alignment:** Map Monitoring/Event Management, Incident Management, Service Desk, Service Configuration, Problem, Knowledge, Change Enablement, Release/Deployment, Service Validation, Information Security, Service Level Management and Continual Improvement to observable states and evidence. This is not a certification claim.
- **AI governance:** Reuse the existing Analyst/Critic evaluation harness and dataset. Extend the shared invocation path to measure provider-reported tokens, latency, retries and cost only with a pinned pricing source. Missing usage remains UNKNOWN; no model is promoted on cost alone.
- **Schedule decision:** Retain the five existing ChatGPT schedules and assign 5/5 architecture/release integration. Prefer one daily full GitHub quality schedule plus a 15-minute read-only deployed smoke only after runner installation; do not activate duplicate #189 cadence. Debian auto-deploy #146/#153 remains disabled.
- **Qualification:** exact-head CI, real ephemeral integration, synthetic E2E, failure injection, package checksums and install/rollback are separate gates. Green CI does not qualify Debian or LIVE.
- **Safety:** no mass merge, direct main push, production change, cron installation, Docker restart, live migration or LIVE remediation. Any execution requires separate approval, policy recheck, identity, ownership/fencing, preconditions, idempotency, independent verification and rollback.
- **Rollback:** documentation branch can be reverted as one PR; no runtime or data migration is introduced by this ADR.


## ADR-0018 — Preserve scoped read-model contracts and exact-head release stop

- **Date:** 2026-10-30 12:15 UTC
- **Status:** Proposed; subject to review on PR #195.
- **Decision:** Never change a fail-closed Core Run/GLPI/Evidence/Policy response contract merely to satisfy an outdated test double. A failing exact-head CI gate stops the integrated release even when earlier heads passed. Repair mocks/fixtures to match the authoritative endpoint schema, add negative tests for foreign `run_id`, and rerun the exact SHA.
- **Evidence:** #185 candidate `5782d6f` V2.8 [41053319372](https://github.com/alimtalbi-ata/aiops/actions/runs/41053319372) failed one of 59 tests because a legacy mock returned `{"decision":"BLOCKED"}` rather than a scoped `{"items":[...]}` gates response. Quality [41053319020](https://github.com/alimtalbi-ata/aiops/actions/runs/41053319020) was pending when recorded. Do not infer a runtime regression or a green gate from this single test.
- **Ownership:** 2/5 owns Portal fixtures and UI contract; 5/5 integrates only verified fixes. #196 owns the existing Analyst/Critic telemetry implementation; 5/5 owns benchmark interpretation and release evidence, not a duplicate provider client.
- **Consequences:** One draft release candidate, no main/stable merge, no cron activation or Debian changes; explicit UNKNOWN for unverified business links, costs, approvals and rollback.


## 2026-10-30 12:30 UTC — 5/5 scoped-gates regression repair — release governance decision

**Decision:** repair the V2.8 contract fixture in the existing #185 candidate without weakening the Core run/gate identity guard; do not merge the diverged release branch. Favor clean-main selective integration of #197/#198/#199 and the architecture docs before rebuilding a cumulative kit. Keep #188 as the *single preferred* daily full-quality + 15-minute read-only runtime-smoke design; do not activate duplicate #189. #146/#153 Debian auto-deploy remain disabled and #187 Loki/Tempo/OTel remains deferred. CI PASS on an isolated PR is not an install/rollback/production approval; synthetic HITL cannot authorize LIVE.

**Evidence:** #185 `2b2af9c` V2.8 run 41055650146 SUCCESS, local V2.8 59/59 and selected 253/253; Quality 41055650123 pending at recording. #196 `6b6a3b3` four workflows SUCCESS. Two RC1.4 artifacts have mutually missing features and no full architecture docs. **Release verdict: NO-GO.**

### ADR-2026-10-30-48H-KIT — Cumulative release must be main-based (2026-10-30 13:12 UTC)

**Status:** proposed, no deployment authorization. **Decision:** #185 `2b2af9c` remains sole synthetic demo candidate, but direct merge is unsafe (741 ahead/43 behind main) and its 395/395-integrity ZIP is **not cumulative**: migration 011, OIDC identity modules, AI telemetry and architecture/story docs absent. Reuse #197/#198/#199 main-based adapters, selectively port #190/#185 story, #192/#193 GLPI/proposals, #194 HITL/OIDC/outbox, #196 provider telemetry and #195 docs; reconcile Core/Portal `main.py`, `compose.yml`, Quality YAML with tests and one exact SHA. #188 preferred nightly Quality/15-min read-only smoke after runner approval; #189 duplicate inactive; #146/#153 auto-deploy disabled and #187 deferred. No merge, stable push, host operation, GLPI write or LIVE approval implied.

## ADR 2026-10-30 14:00 UTC — one main-based staging candidate, no wholesale legacy merge

**Decision:** create draft [#201](https://github.com/alimtalbi-ata/aiops/pull/201) from exact `main@27deb9b1` and reuse only verified, disjoint Git blobs from #197/#198/#199 and docs #195. Extend PR CI with offline fail-closed tests; no new engine, Portal rewrite or scheduled workflow. **Rationale:** #185 and #194/#196 remain hundreds of commits divergent from main, with overlapping Core/Portal/Compose and incompatible cumulative ZIPs. **Consequence:** #201 is an integration staging source, not production/DEBIAN/LIVE approval. Keep #188 preferred, #189 duplicate inactive, #146/#153 disabled, #187 deferred. Next decision gate is exact combined-SHA CI plus 2/5 Portal and Core protected Evidence refs.

### ADR 2026-10-30 14:16 UTC — cumulative ZIP inventory must fail closed

**Decision:** a green CI or checksum-valid ZIP is not sufficient for release. Add a read-only exact-source inventory gate on main-based staging #201 (`03a5b0cce44e56d7ae315ee7df16e850a5e35b11`) checking mandatory architecture/HITL/AI/Portal/Policy files, all member hashes, manifest SHA, source-tree HEAD, and unsafe/duplicate members. The 10 offline guard tests pass locally; new-head CI remains unverified at this entry. **Consequence:** old #185/#196 partial packages remain NO-GO; a PASS still does not prove installation, rollback, runtime or LIVE. No engine, authorization boundary or deployment schedule changed.

### 2026-10-30 15:12 UTC — ADR delta: distinguish benchmark workflow success from evaluation qualification

**Decision:** GitHub Actions job conclusion is necessary but insufficient for AI model qualification. If any isolated Ollama evaluator repeat exits nonzero or produces a failed report, benchmark qualification is FAIL/UNAVAILABLE even when the wrapper job uploads artifacts and reports SUCCESS. Source [#196 Quality 41070920303](https://github.com/alimtalbi-ata/aiops/actions/runs/41070920303): qwen3:4b and qwen3:8b, three repeats each, `ReadTimeout`, `evaluator_exit=1`, 0/3 PASS per model, no p50/p95/provider tokens/cost. Require fail-closed post-upload workflow gate and independent resource/timeout diagnosis; never translate unavailable metrics into zeros or model quality scores. No model or LIVE promotion.

**Integration boundary:** #201 main-based `7474c74c` ports only the #198 six-test synthetic SAN→Payments seed contract and adds its exact-head CI step ([Quality 41077972849](https://github.com/alimtalbi-ata/aiops/actions/runs/41077972849) 3/3 SUCCESS, 6/6 tests). Reverse-edge path and synthetic P1 are not authenticated impact evidence. Do not merge divergent #185/#194/#196 wholesale, or activate both #188/#189 crons.

<!-- convergence-5of5-477da60-20261030 -->
### 2026-10-30 — ADR delta: one main-based candidate, fail-closed source transport

**Decision:** retain #201 as the only release integration candidate; port six exact source blobs from #198/#202 without merging stacked/divergent PRs or replacing Portal main/Compose/Core. Canonical Evidence UTC must be bounded and Portal must refuse unqualified authority claims, expose 401/403/503 without navigation, and never persist bearer credentials. **Rationale:** preserve Core authority and operator-visible UNKNOWN, prevent false customer evidence. **Qualification:** [new exact-head Quality 41088096834](https://github.com/alimtalbi-ata/aiops/actions/runs/41088096834) queued; T0 not yet passed, T4/T5 NO-GO. No merge, Debian or LIVE.
