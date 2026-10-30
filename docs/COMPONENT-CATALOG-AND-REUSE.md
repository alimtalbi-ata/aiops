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
