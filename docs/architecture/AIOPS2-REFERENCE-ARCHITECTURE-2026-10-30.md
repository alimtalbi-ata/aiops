# AIOps 2.0 — Reference architecture and enterprise operating model

**Status:** Target architecture / design baseline for the 48-hour convergence.  
**Date:** 2026-10-30. **Scope:** customer-demonstrable, ITIL 4-aligned synthetic enterprise journey; production integrations remain individually qualified.  
**Rule:** this document describes ownership and target contracts. It does not claim that every connector, process, or control is deployed.

## 1. Architecture decision

Converge on one AIOps 2.0 control plane. Do not create a parallel orchestrator, ticket store, evidence store, AI ledger, or operator portal. Reuse the existing Core, Temporal/Worker, Evidence, Twin, Policy, Portal, GLPI, Prometheus/Grafana, RAG and simulator implementations through explicit adapters and versioned contracts.

### Logical planes

| Plane | Primary components | Authority |
|---|---|---|
| Signal and observability | Checkmk (target monitoring authority), Prometheus, Grafana, selected log store/Elastic | Source observations and telemetry; never owns Incident/Run lifecycle |
| Integration and normalization | authenticated source adapters, GLPI adapter, n8n notifications | Validates, timestamps, deduplicates and maps external IDs; no canonical Run state |
| Service control | Core API + PostgreSQL | Sole authority for tenant, Incident, Run, stage, evidence references, decisions and lifecycle transitions |
| Orchestration | Temporal + Worker | Durable workflow execution, retries, timeouts, signals and recovery; no independent business ledger |
| Context and intelligence | Twin/CMDB, Evidence, RAG, Analyst, Critic | Advisory context and sourced evidence; no authorization |
| Governance | Policy, HITL, identity, audit | Deterministic authorization, human decision, fencing and audit; LLM cannot override |
| Execution | isolated simulator now; bounded Ansible/SSH executor only after qualification | Side effects only after independent gates; LIVE remains disabled until release gates pass |
| Experience | Portal / NOC Command Center / Demo Studio / Grafana | Authenticated read models and operator actions through APIs; no direct DB writes |

### Canonical flow

`Monitoring/ITSM → authenticated adapters → Core Incident/Run → Temporal → Evidence + Twin + RAG → Analyst → independent Critic → Policy → HITL → isolated SIMULATE → independent VERIFY → GLPI reconciliation → learning`

The customer journey is anchored to one `tenant_id`, `incident_id`, `run_id`, `service_id`, `ci_id`, `ticket_id`, and immutable evidence/decision references. If a link cannot be proved, expose `UNKNOWN`; never infer a relationship from a title or a synthetic identifier.

## 2. Source-of-truth and data ownership

| Entity | Authoritative owner | Mutability / contract |
|---|---|---|
| Tenant, user, role, service identity | Identity provider + Core authorization projection | Versioned claims; least privilege; tenant isolation |
| CI, service, dependency | GLPI CMDB / governed Twin source | External authority plus Core snapshot, freshness and source reference |
| Incident | Core | Optimistic versioning, idempotent creation, append-only lifecycle events |
| Run and stage | Core for canonical state; Temporal for workflow history | Correlated IDs; durable transitions; Temporal is not a replacement business ledger |
| Evidence | Evidence service | Append-only, hash, source, observed_at, known_at, provenance, freshness, tenant and run binding |
| Analysis / Critique | AI ledger in Core | Immutable input/evidence binding, provider/model/prompt/schema versions, validation state |
| Policy decision | Policy evaluation persisted by Core | Deterministic result, policy version, input hash, reasons and proof snapshot |
| Proposal / Approval | Core HITL ledger | Immutable proposal hash/revision; verified human identity; expiry, nonce and scope |
| Effect / Verification / Reconciliation | executor receipt + Core ledger | Separate effect from approval; independent postcondition evidence; no self-attestation |
| ITSM ticket / Change | GLPI | GLPI remains ticket/CMDB authority; Core stores verified cross-reference and reconciliation |
| Model invocation / evaluation | AI telemetry ledger (target) | Per-call usage, latency, model/prompt/dataset version, cost provenance and evaluation score |

Target canonical identifiers and fields (versioned schemas required): `schema_version`, `tenant_id`, `source`, `source_event_id`, `event_time`, `ingested_at`, `observed_at`, `known_at`, `severity`, `state`, `dedupe_key`, `incident_id`, `run_id`, `service_id`, `ci_id`, `ticket_id`, `evidence_ids`, `mode`, `provenance`, `freshness`, `correlation_status`, `policy_version`, `proposal_hash`, `actor_subject`, `trace_id`.

## 3. ITIL 4 operating model

This is an implementation alignment, not an ITIL certification claim.

| ITIL 4 practice | Platform behavior and customer-visible evidence |
|---|---|
| Monitoring and Event Management | Receive Checkmk/Prometheus events; normalize, dedupe, timestamp, classify; preserve source and acknowledgement separately |
| Incident Management | Create one canonical Incident; P1–P4 priority, impact/urgency, assignment, SLA/OLA timers, escalation and major-incident command |
| Service Desk | N1 intake, acknowledgement, communication, ownership and handover; N2/N3 technical escalation |
| Service Configuration Management | Link CI/service/dependency through GLPI CMDB and Twin; show source and freshness; stale/missing relations are UNKNOWN |
| Problem Management | Cluster recurring incidents, root-cause hypotheses, known error and workaround; link Problem to related Incidents |
| Knowledge Management | Curated runbooks/KB with owner, version, classification, ACL, expiry and citations; retrieval cannot grant authority |
| Change Enablement | Proposed change, risk/impact, implementation and rollback plan, approver roles, maintenance window and post-change review |
| Release Management / Deployment Management | Versioned package, exact commit, manifest/checksums, staged deployment, health checks and tested rollback |
| Service Validation and Testing | Contract/unit/integration/E2E/failure-injection tests with evidence and explicit environment/mode |
| Information Security Management | MFA/SSO, RBAC, tenant fence, secrets management, audit, redaction and security event trail |
| Service Level Management | Service SLO/SLI, SLA/OLA timers, breach/near-breach, availability and business impact |
| Continual Improvement | Post-incident review, verified lessons, action owner/due date, runbook changes and gold-set curation |

### Priority and escalation

Priority is computed from approved impact × urgency rules, not inferred from an LLM. P1 triggers major-incident handling, incident commander, N2/N3 escalation, customer communications and human approval. P2/P3/P4 follow service-specific OLAs and runbooks. The demo must show the calculation inputs and policy version.

### End-to-end enterprise scenario

1. A synthetic Checkmk event reports SAN fabric path degradation.
2. Core correlates the event with the Payments service and CMDB/Twin dependencies; the dependency path must be sourced.
3. A second observation reports payment latency/SLO breach. Core deduplicates and raises a P1 candidate with impact/urgency evidence.
4. N1 acknowledges; N2 investigates; incident commander is assigned for P1. GLPI ticket and Core Incident/Run links are verified, not guessed.
5. Evidence collects current path state, latency, service checks and selected logs. RAG returns only ACL-authorized, versioned runbooks and known errors with citations.
6. Analyst proposes ranked hypotheses and bounded corrective options; independent Critic checks evidence, contradictions, freshness, action safety and missing preconditions.
7. Policy records SIMULATE/ESCALATE/HUMAN_APPROVAL/BLOCK with explicit reasons. No LLM output can alter the policy result.
8. HITL displays proposal hash, CI, risk, evidence, preconditions, expected postconditions, rollback, expiry and verified human identity. Synthetic runs may demonstrate the UX but cannot create real approval authority.
9. The sandbox simulates an allowlisted remediation and records a simulation receipt. No real SSH, sudo, Ansible or GLPI write is implied.
10. Independent verification checks service health and business SLO; reconciliation updates the Core read model and the synthetic GLPI ticket if that connector is part of the test fixture.
11. A Problem/known-error candidate and post-incident review are generated only from verified evidence. A human accepts knowledge changes.

## 4. Safety and trust boundaries

- Core is the only canonical business-state writer; Portal is an API client.
- Temporal signals notify workflows of Core-persisted decisions; they do not authorize effects.
- Evidence and audit are append-only; corrections are superseding records.
- Policy is deterministic and independent of Analyst/Critic.
- Every effect requires proposal hash/revision, verified actor, scope, expiry, current ownership/fencing token, preconditions, idempotency, policy recheck and rollback.
- Execution must be a fixed allowlisted action catalogue; never translate free text into shell commands.
- DEMO/REPLAY/STORY never authorize LIVE. Mark synthetic provenance at every layer.
- Missing, stale, contradictory or untrusted information is `UNKNOWN`, not healthy.
- No cross-tenant retrieval, citation, ticket or evidence link without authorization before retrieval and before display.
- No secrets or raw sensitive prompts in logs, traces, benchmark reports or artifacts.

## 5. Runtime tiers and release gates

| Tier | Purpose | Allowed effects | Required proof |
|---|---|---|---|
| T0 unit/contract | deterministic logic | none | tests, static audit |
| T1 isolated integration | real service processes + ephemeral DB | disposable fixtures only | service integration reports |
| T2 synthetic E2E | customer story in isolated stack | simulator-only effects | exact Run/evidence/ledger receipts |
| T3 deployed read-only | actual deployed services | read-only | timestamped endpoint and redacted response |
| T4 controlled sandbox | isolated executor with approved fixtures | allowlisted sandbox mutations | approval, fencing, effect, verify, rollback |
| T5 LIVE | enterprise production | only explicitly authorized | independent security, identity, policy, executor, recovery and change approval gates |

Current 48-hour target: T2 customer story plus T3 only where actual access/evidence exists. T4/T5 are not implied by green CI. LIVE remediation stays blocked.

## 6. Standards and architecture governance

Use ITIL 4 practice alignment for process design; use versioned API/data contracts, threat modelling, least privilege, auditability, change enablement and rollback for engineering governance. Map controls to ISO/IEC 20000-1 service management, ISO/IEC 27001 information security, ISO/IEC 27017/27018 where cloud/privacy scope applies, and ISO 22301 continuity only after a control-by-control assessment. Do not claim compliance/certification without formal scope, evidence and independent audit.

Architecture changes require: ADR, source-of-truth owner, threat boundary, schema/API version, tests, operational owner, observability, migration/rollback, release manifest and exact qualification evidence.

## ADR-INT-2026-10-31B — current single integration candidate (23:48 Europe/Paris)

The sole clean main-based DEV integration candidate is [#234](https://github.com/alimtalbi-ata/aiops/pull/234) `integration/enterprise-slice-main-20261031-2230`, created from `main@ae7c3e5102b99a66bd7806d602146f1309a9749d`. Historical #201 remains source-only and stale documentary #227 is closed. The first scoped product port is the eight-path ACME synthetic graph/replay contract from #231, not a whole-branch merge. GLPI remains ITSM/CMDB authority when independently qualified; Core owns Incident/Run, Portal requires server-derived actor+tenant exact-Run ACL, and Policy/Temporal cannot authorize LIVE. New candidate exact-head D0 must be requalified; D1/D2 combined and D3/D4 are not qualified. See [integration ADR](../release/AIOPS2-INTEGRATION-CYCLE-2026-10-31-2345.md). RELEASE_STABLE=NO_GO.


## ADR-INT-2026-11-01A — Selective four-owner integration, fail-closed by construction (00:41 Europe/Paris)

The sole DEV candidate remains Draft [#234](https://github.com/alimtalbi-ata/aiops/pull/234), based on main `ae7c3e5102b99a66bd7806d602146f1309a9749d`. Architect selectively ported ACME Bearer origin pin #236, Portal OIDC callback/identity-only sessions #237, Core read-only xref #233 with installed SQL 009 AI→010 Evidence→011 HITL→012 xref #238, and Policy no-effect #239. Integration code checkpoint `f69b0f7e41ac3d199c8236b09dd8b301b2607176`; no whole historical PR merge.

**Trust ADR:** Portal RS256 identity is not authorization. Core signed synthetic ownership fixtures are not authenticated GLPI authority. The exact Run/Incident/ticket/entity actor+tenant positive ACL remains unqualified and MUST return UNKNOWN/fail-closed. ACME Core Bearer requires an explicitly pinned origin; Policy's public HTTP schema remains exactly state/decision/reason, while internal verdicts prohibit effects. Temporal signal never authorizes action. Only disposable PG16/Chromium tests are permitted; no host/real GLPI/LIVE. D0 integrated CI [#41253703233](https://github.com/alimtalbi-ata/aiops/actions/runs/41253703233) pending at checkpoint; D1/D2/D3/D4 not qualified. Revert focused integration commits in reverse order; discard ephemeral databases.
