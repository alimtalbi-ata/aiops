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

## 2026-10-27 target extension — NOC, human control and knowledge

These rows represent *target roles*, not installed, deployed or qualified services. Reuse current app/service code before adding new containers.

| Component / candidate | Intended role | Reuse/build decision | Qualification gate |
|---|---|---|---|
| Checkmk | Host/service monitoring, alert state, discovery | Candidate integration; avoid duplicate Prometheus collection | Edition/version, REST/Livestatus, auth, topology mapping, read-only spike |
| Thruk | Operator NOC view and multisite aggregation | Candidate UI with compatible monitoring backend | Backend compatibility, ack/downtime ownership, auth/RBAC |
| OpenTelemetry Collector | Telemetry ingest/routing | Optional addition if absent; reuse existing metrics first | Data contracts, cardinality, retention, secret redaction |
| ACME Enterprise Twin | CI/service dependency graph, business flows and incident ground truth | Extend existing twin/simulator | Deterministic seeds, isolation, CMDB reconciliation, impact assertions |
| AI Investigator + Critic | Evidence-backed competing hypotheses and recommendations | Extend existing Intelligence/Core/Worker; review V145 candidates | Citation validity, missing evidence, hallucination/contradiction tests |
| NOC Copilot | Read-only enterprise-grounded chat | Extend Portal + Core/RAG rather than parallel authority | Per-user ACL, citations, abstention, injection and exfiltration tests |
| Knowledge Hub / RAG | Vendor/internal docs, runbooks, postmortems, incident memory | Reuse RAG if present; PostgreSQL full-text + pgvector is candidate | Ingestion rights, source versions, retrieval quality, ACL, deletion |
| HITL Decision Center | Human approval, rejection, revision, expiry | Extend Portal/Core/Policy/Temporal/GLPI | Identity, role, immutable action approval, race/expiry, audit |
| Remediation Lab | Allowlisted Ansible, scripts, CLI, REST recipe catalog | Extend guarded Worker/Temporal, sandbox executors | No arbitrary commands, typed params, dry-run, idempotency, postchecks |
| Evidence Studio | Replayable incident timeline and proof package | Extend existing Portal/Evidence rather than separate writer | Exact source links, failed-run visibility, synthetic label, replay |

### Reuse-before-build investigation order
1. Inspect all relevant current and historical branches, existing RAG/Copilot/Intelligence/Simulator/Evidence/Portal contracts and V145 candidates.
2. Map authority for each object: incident, Run, CI, approval, document, recipe and evidence. No parallel writers.
3. Validate Checkmk↔Thruk adapter/compatibility in isolation before pinning versions or Compose dependencies.
4. Add small versioned contracts and deterministic fixtures for one ACME ERP incident, one document corpus and one sandbox recipe.
5. Test unauthorized chatbot queries, absent documentation, refused/expired HITL, duplicate approvals, stale CMDB, failed postcheck and rollback.
6. Qualify only with actual tests and exact artifacts; update this catalog with verified source paths, SHA, adapter owners and observed results.

## 2026-10-27 — PR #36 reuse assessment (source review, not runtime qualification)

Source: [draft PR #36](https://github.com/alimtalbi-ata/aiops/pull/36), *AIOps V2.13.10 — continuité du portail unique et STAR fictif*. This is a large divergent candidate branch, not a drop-in deployable upgrade. Its PR narrative describes synthetic/offline tests and expressly states that authenticated real-runtime NOC integration and Debian production qualification are outstanding. Do not merge or cherry-pick the entire branch blindly; compare exact files against current main and port narrow contracts with tests.

| PR #36 candidate source | Reuse potential | Required guard before promotion |
|---|---|---|
| `demo/noc_checkmk_export.py`, `demo/noc_livestatus_import.py`, `demo/noc_livestatus_loopback.py`, `demo/noc_checkmk_consolidation.py` | NOC Checkmk/Livestatus normalization and synthetic fixtures | Confirm actual Checkmk/Thruk versions, schema and backend compatibility; read-only adapter tests; no fabricated LIVE data |
| `demo/noc_wallboard.py`, `demo/noc_topology.py`, `demo/noc_drilldown.py`, `demo/noc_unified_offline.py` | NOC view, topology, drilldown and offline replay | Port to Portal/Core read-only APIs; authenticated CI/incident IDs and freshness; never infer runtime availability from fixture |
| `demo/rag_ops_fixture_catalog.json`, `demo/validate_rag_ops_fixtures.py` | Seed synthetic operations corpus and validate document provenance | Extend with real authorized docs, ACL, versions, licensing, citation granularity, retrieval benchmarks and deletion |
| `app/portal/acme-fixtures.json`, `app/portal/acme_fixture_contract.py`, `app/portal/acme_impact_read_model.py` | ACME business dependency and impact demonstration | Preserve `SIMULATED_TARGET` and null real ticket/time semantics; compare with canonical CMDB and twin contracts |
| `app/portal/platform_registry.py`, `app/portal/platform_registry_router.py`, `app/portal/noc_runtime.py` | Component inventory and possible NOC read-model seam | Exact GET route presence is not backend availability or authenticated runtime attestation; preserve false/unknown flags |
| `tests/test_portal_bootstrap_read_model.py`, `tests/test_preflight_secrets.sh` and portal bootstrap token changes | Read-only Portal auth and secret lifecycle test patterns | Assess compatibility with main's token and identity contracts; bootstrap token is not full SSO/RBAC |
| `demo/noc_evidence_center.py`, `demo/star_capture_evidence.py`, related STAR gates | Evidence replay and deterministic demo acceptance checks | Confirm cryptographic provenance, fixture separation, CI results on selected SHA; never treat synthetic captures as live proof |
| Candidate kit generator and `tests/test_single_portal_candidate_kit.py` | Reproducible source packaging and manifests | Verify pinned source hashes and dependencies; a ZIP passing offline tests is not a production release |

**Recommended extraction sequence:** (1) RAG fixture validation and ACME impact schema; (2) NOC Checkmk/Livestatus import contracts and offline wallboard; (3) Portal read-only authentication and registry; (4) evidence replay gates; (5) controlled HITL/remediation extensions built against canonical Core/Temporal/Policy, not inferred from the PR. Each extraction requires file-level source comparison, focused tests and a separate draft PR.

**Problems identified:** huge divergent PR, unqualified backend compatibility, static/fixture versus live evidence ambiguity, incomplete Portal authentication, and potential conflicts with current main and existing PRs. These are reasons for staged reuse, not for discarding the work.
