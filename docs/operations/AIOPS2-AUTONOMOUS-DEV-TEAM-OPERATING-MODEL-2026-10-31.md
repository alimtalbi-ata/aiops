# AIOps2 — Autonomous development team operating model

**Date:** 2026-10-31  
**Repository:** `alimtalbi-ata/aiops`  
**Environment:** DEV ONLY. The default branch `main` is the shared development baseline, not a production release.  
**Team lead:** Schedule 5/5 — Architect / Integrator.

## 1. Mission

Build one enterprise AIOps platform that detects, understands, prioritizes, investigates, governs, simulates, verifies and learns from infrastructure incidents using AI and a governed Digital Twin. Align workflows and operator responsibilities with ITIL 4. The customer-facing proof is a reproducible synthetic enterprise journey, not a collection of disconnected demos.

Canonical journey:

`Monitoring/Event → correlation/deduplication → Incident (P1–P4) → service/CI impact from Twin → Analyst hypotheses with citations → Critic challenge → immutable Evidence → Policy decision → HITL approval where required → SIMULATE (no external effect) → post-action verification → resolve/reopen → Problem/Knowledge/Change feedback`.

The ACME SAN path degradation → Payments impact remains the reference scenario until the architect records a better candidate and updates the board.

## 2. Team and ownership

| Schedule | Role | Owned domain | Primary deliverable |
|---|---|---|---|
| 1/5 ACME & Digital Twin | Scenario / Twin engineer | Synthetic enterprise fixtures, Twin graph, scenario and incident generator, deterministic replay | Coherent incident generated from a versioned dependency graph, with source IDs, timestamps, tenant, severity and impact evidence |
| 2/5 Portal & GLPI UX | Operator experience engineer | Portal UI, NOC cockpit, GLPI read-only integration/presentation, role-aware workflows | One operator timeline showing Incident, ticket, CI/service context, Evidence, AI analysis, Policy/HITL and verification |
| 3/5 Core, NOC & CMDB | Platform integration engineer | Core read contracts, Incident/Run/Evidence/xref, GLPI CMDB→Twin normalization, correlation APIs | Authenticated tenant-scoped API and traceable identity joins; GLPI remains the ITSM/CMDB authority when qualified |
| 4/5 Policy & HITL | Governance / workflow engineer | Policy, Temporal/Worker, proposals, approvals, outbox and audit | Deterministic no-effect simulation, durable human decision workflow, idempotency and postcondition verification |
| 5/5 Architect / Integrator | Chief architect / team lead | Architecture, priorities, cross-team contracts, branch strategy, reviews, consolidation, merges, release/demo gates | One coherent integration candidate, one current board, verified evidence and explicit GO/NO-GO |

Ownership is a boundary, not a silo. Cross-team changes require an agreed interface contract and an explicit dependency on the board. Avoid simultaneous edits to the same files.

## 3. Schedules and cadence

Five existing ChatGPT automations are reused; no duplicate sixth schedule is created. All are enabled and configured hourly in `Europe/Paris`, staggered to reduce collisions:

| Sequence | Local start | Cadence |
|---|---:|---|
| 1/5 ACME & Twin | 23:00 | Hourly |
| 2/5 Portal & GLPI UX | 23:10 | Hourly |
| 3/5 Core, NOC & CMDB | 23:20 | Hourly |
| 4/5 Policy & HITL | 23:30 | Hourly |
| 5/5 Architect / Integrator | 23:45 | Hourly |

**Scheduler evidence caveat:** the automation API accepted the schedule updates and reports all five enabled, but `next_run_time` is still null at this snapshot. Therefore the hourly recurrence is configured, not yet independently proven to fire at the next scheduled time. The architect must recheck next-run/last-run and results each cycle. Do not call a configured schedule a successful heartbeat until an execution is observed.

## 4. Work intake and WIP

The architect maintains one ordered backlog and a maximum of three P0 work items in progress. Each task has:
- one accountable owner and one reviewer;
- a user-visible product outcome and acceptance criteria;
- one owning branch and a stated base SHA;
- a dependency list and explicit API/data contracts;
- tests and the exact CI workflow(s) required;
- a rollback/revert plan.

Priority order:
1. End-to-end identity and traceability: Tenant/Actor → Event → Incident → Run → GLPI Ticket/CI → Evidence.
2. Realistic enterprise Twin/CMDB and source-backed impact/blast-radius calculation.
3. Portal/NOC operator journey and ITIL 4 role/lifecycle handling.
4. Analyst/Critic quality, evidence grounding, Policy and HITL governance.
5. Deterministic incident generation, simulation, postcondition verification and learning loop.
6. Benchmark, developer kit, reproducibility and customer demonstration polish.

Do not optimize a disconnected AI benchmark or UI mock ahead of the working incident journey.

## 5. Branch and integration policy

- Developers create focused branches from the architect-designated integration candidate (or current `main` if no candidate is designated), commit their owned changes, run tests, and open/update a PR.
- Developers do not merge their own PRs or push directly to `main`. The architect is the sole integrator.
- The architect inspects actual diffs, file ownership, branch ancestry, migrations, contracts, exact-head CI, review feedback and runtime evidence. PR size or recency is not a quality signal.
- Prefer selective integration of compatible commits/files over wholesale merge of divergent branches.
- Keep one canonical integration candidate. Retarget/stack dependent PRs in dependency order; avoid duplicate parallel candidate branches.
- Merge a focused PR only when it is non-Draft, mergeable, based on the intended branch, has all required exact-head checks green, and has a documented revert. Use expected-head-SHA merge protection.
- Promote the integrated candidate to `main` through a tested PR. A replacement of `main` means a reviewed merge that changes the development baseline, never a force-push/reset or an unreviewed branch pointer replacement.
- After every merge, rerun qualification on the new target SHA. Tests from a previous SHA do not qualify the new integration.
- `main` is currently reported unprotected by GitHub API. Until an administrator enables branch protection/rulesets, enforce the above gates manually and do not mistake API mergeability for governance.

## 6. ITIL 4 and data semantics

The platform must distinguish:
- Event/Alert from Incident;
- Incident from Problem and Known Error;
- Change from an automated remediation proposal;
- Service Request from Incident;
- hypothesis from observed fact;
- estimated impact from confirmed impact;
- recommendation from Policy authorization;
- human approval from execution permission;
- command receipt from verified postcondition.

Use explicit roles: Service Desk/N1, resolver groups/N2-N3, Incident Manager, Major Incident Manager, Problem Manager, Change Authority and service owner. Priority P1-P4 must derive from documented impact/urgency policy and source-backed service criticality, not an LLM assertion. SLA/OLA clocks, maintenance windows, communications, escalation, resolution codes and knowledge feedback must be visible in the operator journey.

GLPI remains the system of record for tickets and configuration items where its connector and identity controls are qualified. The Twin consumes a normalized, versioned view with provenance/freshness; it is not a parallel CMDB.

## 7. Twin and incident-generator quality

The synthetic enterprise should include multiple sites, datacenters, network, compute, virtualization, storage/SAN, databases, middleware, applications and business services such as Payments, ERP and IAM. Every CI and relationship has stable synthetic IDs, type, lifecycle, owner, criticality, source, observed/known timestamps, freshness and graph version.

Incident generation must be deterministic by seed and graph version. Events must reference real fixture CI/service IDs and support deduplication, correlation, cascade impact, maintenance windows, recovery, reopen and false-positive scenarios. No synthetic data may be labelled live.

## 8. Quality gates

| Gate | Required evidence |
|---|---|
| G0 Source | Exact commit, clean diff, static/security/unit tests |
| G1 Integration | Disposable PostgreSQL/Temporal/GLPI-compatible adapters and migrations, tenant isolation, idempotency |
| G2 Vertical slice | Same-SHA API/UI E2E from event intake through verified no-effect simulation and resolution |
| G3 Twin/ITIL | Graph consistency, blast radius, P1–P4 policy, roles, SLA/OLA, Problem/Change/Knowledge semantics |
| G4 Developer kit | Manifest/checksum integrity, clean install, upgrade and rollback in disposable environment |
| G5 Demo | Repeatable seed, operator runbook, visible evidence, timing, known limitations and reset procedure |

A gate can be PASS, FAIL, BLOCKED or NOT_TESTED. No green-by-proxy. CI success is not runtime success; runtime success is not customer acceptance; demo readiness is not production readiness.

## 9. Durable handoff format

Every schedule writes a concise update to the relevant PR/issue and the architect updates #195 and #186. Record:
- Europe/Paris timestamp and owner;
- objective and user value;
- branch, base SHA, head SHA and PR;
- changed files and contract impact;
- exact commands, test counts and workflow URLs;
- artifacts and checksums when produced;
- observed result, limitations and unverified claims;
- decision, dependency, next action and revert plan.

Use evidence labels consistently: `SOURCE_REVIEWED`, `CI_PASS`, `INTEGRATION_PASS`, `RUNTIME_OBSERVED`, `DEMO_VERIFIED`, `NOT_VERIFIED`.

## 10. Immediate architect actions

1. Audit current open PRs #195, #201, #202, #198, #205, #204 and the Debian/reporting PRs using their current exact heads.
2. Select one integration spine based on product completeness, branch ancestry, test coverage, data contracts and migration safety.
3. Resolve whether #195 is the architecture/board baseline and whether #201 is still the best product integration candidate; do not merge either solely because its CI is green.
4. Assign the four teams non-overlapping next increments and update this document/board when priorities change.
5. Merge only small, fully qualified increments; requalify every resulting target SHA.
6. Keep the final customer journey as the decision criterion: does AIOps actually help an enterprise NOC understand, prioritize, resolve and learn from an incident?
