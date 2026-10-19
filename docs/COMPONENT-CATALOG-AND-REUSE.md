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

### Additional portal source evidence recorded 2026-10-19

| Source | Evidence available | Decision | Next action |
|---|---|---|---|
| R33 `03-SOURCES/V1/stack/live_console` | Main Python entrypoint, portal HTML/JS/CSS, campaign studio, demo studio, Dockerfile and requirements listed on host | **Candidate baseline**, not runtime-qualified | Use as a source comparison baseline; inspect dependencies and routes against current Portal/Core contracts |
| `aiops_v1_live_console` container export | Export archive exists; selected app files were listed in the export inventory | **Candidate** | Extract only whitelisted files using `tools/recovery/collect-historical-portal.sh`; compare hashes/diffs |
| `aiops_v1_live_console_v145_test` container export | Export archive exists; V145-specific files such as `fasttrack-v2-marker.html` were listed in its inventory | **Candidate for delta mining** | Identify unique behavior/fixes; port only after API, auth and safety review |
| `aiops_v1_ui_validation_20261018-000409` export | Export archive exists and largely resembles the v1 console inventory | **Secondary evidence** | Use only if it contains a useful change absent from both R33 and V145 comparison |
| `aiops_portal_consolidated_v92` | Export reported as 1,024 bytes; image metadata lookup reported a missing content blob | **Unavailable / untrusted** | Do not use unless independently recovered and integrity-checked |

The selective recovery archive is an interchange artifact only. Do not commit the archive or full container exports. Commit only reviewed source files, tests, contracts, and provenance notes that are needed by the current AIOps 2.0 target.

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
