# AIOps 2.0 — Component Catalog and Reuse Matrix

**Author:** Abdelhalim Talbi  
**Last updated:** 2026-10-19  
**Status:** Initial inventory; candidates require source and contract review.

## Decision vocabulary

- **Reuse unchanged:** source, contract and tests match the canonical interface; no semantic/safety gap.
- **Adapt behind adapter:** capability is valuable but interface, schema, lifecycle or safety semantics differ.
- **Replace:** capability is duplicated or structurally unfit; replacement requires migration and rollback plan.
- **Retire:** demonstrably unused, no active dependency and rollback/retention obligations are satisfied.
- **Unknown:** evidence is insufficient; no implementation decision yet.

## Current runtime component catalog

| Component | Intended responsibility | Boundary / rule | Qualification needed |
|---|---|---|---|
| Portal / Command Center | Operator experience, incident/run timeline, evidence and decisions | Calls Core API; no direct DB writes | UI/API contract, auth, usability, error states |
| Core | Canonical API and state transitions | Sole authoritative lifecycle boundary | Schema validation, auth, idempotency, optimistic concurrency |
| Temporal | Durable workflow history and retry | Owns orchestration lifecycle | Worker restart, retry, timeout, replay, recovery |
| Worker | Execute workflow activities | No hidden untracked state | Activity idempotency, bounded retries, failure handling |
| Evidence | Evidence acquisition/storage/provenance | Append-only; unknown remains unknown | Integrity, freshness, source attribution, deduplication |
| Intelligence | Analyst and critic | Structured output is advisory until validated | Schema, grounded evidence, contradictions, missing info |
| Policy | Deterministic safety gate | Independent from LLM; fail-closed | P1/high-risk/invalid/stale evidence tests |
| Digital Twin | Model services, dependencies and impact | Must identify data freshness and simulation assumptions | Model accuracy, lineage, stale CMDB behavior |
| Simulator | Controlled scenario injection | Isolated execution network; explicit mode/token | Network isolation, repeatability, cleanup and audit |
| RAG | Retrieve runbooks, incidents and vendor knowledge | Citations and freshness; never bypass policy | Retrieval relevance, access control, source attribution |
| ITSM / GLPI | Ticketing and human approval integration | Explicit authority and reconciliation | Auth, duplicate suppression, HITL resume/close paths |
| Observability | Metrics/logs/traces/KPIs | Redaction and stable correlation IDs | Coverage, retention, alerting and stage timings |
| n8n / external adapters | Integration and notifications | Not source of Run state | Retry/idempotency, credential isolation, API contracts |

## Historical AIOps v1 / V145 reuse candidates

| Candidate path/name | Probable capability from name | Current assessment | Next action |
|---|---|---|---|
| `v145-d4.54-decision-intelligence` | Decision intelligence | Candidate; shallow inventory showed `app/dashboard.py`, `contract.json`, README and runner | Inspect contract and routes; determine whether duplicate of d4.61 |
| `v145-d4.55-evidence-fusion` | Combine evidence from multiple sources | Candidate | Inspect server, contract, source attribution and fusion semantics |
| `v145-d4.56-evidence-matrix` | Evidence-to-hypothesis matrix | Candidate | Verify evidence scoring, missing/conflicting evidence and deterministic tests |
| `v145-d4.57-evidence-acquisition` | Gather evidence from systems | Candidate | Inventory adapters, credentials, timeouts, freshness and provenance |
| `v145-d4.58-evidence-decision-adapter` | Translate evidence into decision contract | Candidate | Compare schema with canonical Run/Decision and policy API |
| `v145-d4.59-evidence-enrichment` | Add context to evidence | Candidate | Check CMDB/RAG duplication, source and timestamp preservation |
| `v145-d4.60-semantic-evidence-engine` | Semantic matching/reasoning over evidence | Candidate | Inspect implementation, dependencies, deterministic behavior and grounding |
| `v145-d4.61-decision-intelligence` | Decision intelligence | Candidate; potential overlap with d4.54 | Compare outputs and consumers before selecting one |
| `v145-functional-bridge` | Bridge APIs/contracts between functional components | Candidate; source and README listed | Inspect routes, auth, failure behavior and production ownership |
| `v145-functional-orchestrator` | Functional chain orchestration | Unknown; shallow inventory reported zero files | Recheck exact directory and archived kit/evidence; do not assume usable code |
| `v145-functional-read-model` | Aggregated functional status/dashboard | Candidate; dashboard/server and logs listed | Separate read model from authoritative state; inspect polling, API and stale-data behavior |
| `v145-decision-cockpit` | Decision UI and VM integration | Documentation/contract present | Read architecture, contract, demo and VM integration plan; compare with current portal before merging |

**Important:** “Probable capability” is inferred from the component name, not yet verified from implementation. Inventory output included logs, PIDs, caches and backups; these are not source deliverables and should not be treated as deployable modules.

## Required reuse assessment per component

Record the following before integration:
1. Source path and exact revision/hash.
2. Maintainer/runtime owner and whether it is active in production.
3. Entrypoints, API routes, schemas and contract version.
4. Dependencies, configuration names (never values/secrets), network access and persistence.
5. Tests and dated evidence; what was actually executed.
6. Data authority, state ownership, idempotency and retry semantics.
7. Security controls, authorization, audit and redaction.
8. Failure modes, timeouts, partial effects and rollback behavior.
9. Mapping to canonical Incident/Run/Evidence/Decision.
10. Decision: reuse unchanged / adapt / replace / retire / unknown, with rationale and acceptance criteria.

## Integration order

1. Read-only source and contract inventory.
2. Select low-risk pure/read-only capabilities first: evidence normalization, evidence matrix, read model.
3. Wrap with versioned adapters and schema validation.
4. Unit and contract tests, including stale/missing/conflicting evidence.
5. Isolated integration against a synthetic dataset.
6. End-to-end replay with audit trace and deterministic expected outcomes.
7. HITL/ITSM integration and recovery testing.
8. Live remediation only after independent policy, fencing, approval, rollback and reconciliation qualification.


## 2026-10-27 — PR #36 NOC synthetic RAG catalog targeted reuse (PR #54)

- **Source:** PR #36 `demo/rag_ops_fixture_catalog.json` (blob `56b8a58faf9c2140d212686ef14313576904f0b5`), six synthetic cases. **Disposition:** adapt behind a strictly synthetic read-only portal adapter, not a runtime RAG source.
- **Destination:** `app/portal/fixtures/noc_rag_synthetic.json`, `app/portal/noc_demo_rag.py`, portal NOC panel. Reuses PR #36's strict catalog-validation idea and exact-asset selection; adds operator token, bounded JSON, duplicate-key rejection and SHA-256 citations.
- **Limits:** no real Checkmk/Thruk, Grafana, Core correlation for this fixture, model inference, vendor-authenticated documentation or tenant ACL; all unqualified. Only synthetic fixture content is returned, and `live_remediation_authorized=false`.
- **Qualification:** offline unit/API tests under existing `quality.yml`; [PR #54 CI 40594299546](https://github.com/alimtalbi-ata/aiops/actions/runs/40594299546) completed/success for static/contract/Compose checks; merged at `b44b7f2ffcddecaf5229a4e5fd4c745e038a0c98`. Do not use this module as evidence of a live service incident.


## 2026-10-30 — Current convergence register

Use `docs/architecture/AIOPS2-REUSE-CONVERGENCE-REGISTER-2026-10-30.md` as the current PR/branch convergence record. The original V1/V145 inventory above remains a candidate list and must not be interpreted as qualification.

New decision vocabulary for active PRs:
- **Primary scenario candidate:** #185, subject to exact-head requalification and source-transport review.
- **Targeted correctness fix:** #190, subject to current-head CI.
- **Complementary integration slices:** #192 (Portal/GLPI read), #193 (guarded proposal), #194 (Core OIDC/outbox/Temporal); reconcile contracts before combining.
- **Schedule candidate:** #188; #189 is overlapping and must not run in parallel.
- **Deferred:** #187 observability expansion pending security/resource/retention review.
- **Not authorized for activation:** #146/#153 Debian auto-deployment; #177 broad UI promotion until transport and CI gaps are closed.

AI evaluation reuse:
- `tools/evaluate_ai_core.py`
- `eval/ai-core-cases.json`
- `tests/test_ai_eval_harness.py`
- `tests/test_model_evaluation_api.py`
These were source-reviewed on the HITL candidate branch. Quality metrics exist; per-call token/cost/latency telemetry is not yet qualified. Port selectively and preserve dataset/prompt/model hashes.


## 2026-10-30 12:15 UTC — exact-head component and overlap check

- **Portal/Core/Twin/Policy ACME:** #185 HEAD `5782d6f` has eight exact 1/5–4/5 source blobs. The V2.8 isolated gate failed on a stale gates-response fixture; treat the candidate as **not qualified** until the 2/5 contract test is repaired and all exact-head workflows pass.
- **GLPI/HITL:** #192 (read-only ticket context) and #193 (PROPOSED-only fastpath) overlap in `app/portal/glpi_run_context.py` and its test. #194 additionally overlaps #185/#190/#192 on `app/core/main.py`, `app/portal/main.py`, `compose.yml`; port contracts selectively and preserve Core authority. #193 Quality succeeded only after a transient pip-download retry; that does not validate a combined branch.
- **AI evaluator:** #196 reuses `tools/evaluate_ai_core.py` and `tests/test_ai_eval_harness.py` for provider-reported token/latency accounting. Its exact-head workflows succeeded; no live invocation, pricing source or actual cost has been qualified. Baseline local harness: 3/3 PASS, five synthetic cases, no inference.
- **Scheduling:** #188 daily full quality + 15-minute read-only runtime smoke is preferred, but both #188 and #189 remain unmerged. #189's actual YAML is `23 */2 * * *`, despite its stale PR description mentioning six hours. Never activate both.
- **Release/deployer:** stable SHA `e54c4e9a` is unchanged; stable deployer is portal-only and cannot transport the four-service candidate. #187 Loki/Tempo/OTel is deferred; #146/#153 auto-deploy is not authorized.


## 2026-10-30 12:30 UTC — 5/5 scoped-gates regression repair — main-based adapter boundaries

- [#198](https://github.com/alimtalbi-ata/aiops/pull/198) reuses the existing Core read-only Run locator; its bearer Evidence-refs endpoint is absent on `main`, so evidence attestation remains UNKNOWN. 14/14 local locator tests reported; exact-head Quality SUCCESS. No new Core engine.
- [#197](https://github.com/alimtalbi-ata/aiops/pull/197) is a fail-closed UTC Evidence preflight adapter (5/5 local tests, Quality SUCCESS); not a GLPI client or proof of authenticated reconciliation.
- [#199](https://github.com/alimtalbi-ata/aiops/pull/199) is a SIMULATE-only Policy fixture adapter (22/22 local Policy tests, Quality SUCCESS); it does not create approval authority or execution rights.
- The main Portal lacks the divergent Demo Studio run-detail routes; 2/5 must not import the old Portal tree. The integration owner must supply a reviewed main-based route before the foreign-run guard can be ported. Reuse Core, Temporal, Evidence, Twin, GLPI, Portal and evaluation harness; do not duplicate engines.

### 2026-10-30 13:12 UTC — source completeness boundary

#185 `2b2af9c` scenario/evaluator source and 395/395 archive checks do not include #194 migration `011_hitl_decision_outbox.sql` or OIDC modules, #196 AI telemetry implementation or #195 architecture/story docs. Main-based #197 Evidence UTC preflight is not GLPI authority; #198 Run locator is not tenant ACL; #199 Policy SIMULATE fixture is not approval/execution. #192/#193 share `glpi_run_context.py`; #185/#190/#192/#194 overlap Core/Portal main modules and #185/#192/#194/#196 overlap Compose. Reuse Core/Temporal/Evidence/Twin/Policy/GLPI/Portal/evaluator, do not duplicate engines. Prometheus/Grafana remain observability baseline; #187 deferred.

## 2026-10-30 14:00 UTC — clean-main exact-blob reuse boundary

Draft [#201](https://github.com/alimtalbi-ata/aiops/pull/201) reuses (not reimplements) #198 `tools/find_acme_demo_run.py` (synthetic locator), #197 `app/shared/acme_evidence_utc_preflight.py` (timestamp preflight, not GLPI client), #199 `app/policy/simulate_fixture.py` (Policy evaluate() adapter, `execution_allowed=false`) and #195 architecture/docs. It adds **no** new Incident/Run store, AI engine, executor, GLPI connector or Portal. #194 OIDC/outbox and #196 AI telemetry are not included; #185 scenario UI not included. Source-verified synthetic != authenticated tenant/Evidence/GLPI/production.
