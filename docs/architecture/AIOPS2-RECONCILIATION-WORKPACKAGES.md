# AIOps2 — programme de réconciliation et kits de remodelage

**Status:** PLAN / READ-ONLY FIRST. No changes on SRV-DEB-05 are authorized by this document.

## Baseline known from host observations
- Docker: 78 containers; 59 running, 18 exited, 1 created; five Compose projects; existing cron and auto-deploy.
- Active components: Core 810, Twin 811, Evidence 812, Policy 813, Worker 815, Intelligence 817; GLPI 80 (host 8080), Temporal 7233, PostgreSQL 5432.
- Core: 133 incidents, 137 runs (at observation); GLPI xref 44 confirmed FS1130 out of 50; FS1250 1 without xref; other 82 without xref.
- GLPI UI shows ticket #201 for RUN-8CA56A39E58944F1 and #200 for RUN-C3BD568B15367B66; UI pagination and ticket IDs do not establish total incident count.
- FS1250 Critic denial outbox RECONCILED, policy decision POL-0CB0E84ECD6E01B0; remediations blocked.
- FS1250 has no row in glpi_ticket_links or itsm_xref_events; existence of GLPI #201 proves a linkage gap, not failed ticket creation.
- Per-run gate core_api UNKNOWN may be a parsing/contract mismatch; don't label Core unhealthy.
- GitHub draft PR #452 is audit-only; PRs #431 #438 #443 #446 #448 #449 #450 #451 are candidate work, not proof of Debian deployment.

## Kit 0 — Freeze and provenance (no downtime)
Inputs: existing read-only Debian inventory JSON, Docker inspect (image IDs/digests, compose labels, network graph), running service OpenAPI, migration versions, cron list, GitHub branch/PR inventory, scheduled ChatGPT outputs.
Outputs: signed as-built manifest, component ownership matrix, active/experimental/orphan classifications, unresolved facts.
Gate: all critical running components have identified image, runtime dependency, state owner, GitHub relationship (or explicitly UNKNOWN).
Do not dump secrets, env values, volume data, logs with credentials.

## Kit 1 — Contract and identity convergence
Map source_event_id, incident_id, run_id, policy_decision_id, action_id, ticket_id and evidence IDs across APIs, DB, outboxes and UI. Record DB write owner and event emission path. Identify multiple ticket writers and lookup paths without changing them.
Outputs: lineage graph, contract-diff report, minimal migration proposal with rollback.
Gate: no unowned write path; no duplicated ownership.

## Kit 2 — ITSM reconciliation
Read-only enumerate existing GLPI tickets via authorized API or read-only DB; correlate by structured IDs, then exact run markers, then reviewed weaker matches. Never assume GLPI ticket #201 is count of incidents. Preserve confirmed FS1130 links and detect duplicate candidates.
Outputs: MATCHED, EXISTING_UNLINKED, AMBIGUOUS, MISSING, NOT_ELIGIBLE, UNKNOWN per incident; evidence refs; repair plan requiring approval.
Gate: FS1250 #201 and FS1233 #200 verified independently, no new tickets created; readback and idempotence tests pass.

## Kit 3 — Workflow/HITL/Evidence
Read-only trace Temporal workflow IDs and Worker executions, link to run events; validate action-bound HITL, Critic denial outbox, Policy state and Evidence. A 401 is AUTH_REQUIRED, not a failed service.
Outputs: per-run trace receipts with PASS/FAIL/UNKNOWN/NOT_APPLICABLE, no fabricated success.
Gate: one safe blocked run and one authorized simulated run traced end-to-end.

## Kit 4 — Digital Twin qualification
Digital Twin provides the same adapter contracts as a client, with deterministic expected results. Scenarios: SAN degradation, FS lab, network fault, application saturation, ITSM existing ticket, approval-required action, insufficient evidence, connector outage.
Outputs: E2E tests, safety regression, business KPIs (MTTD, MTTA, diagnostic precision, unsafe action prevention, ITSM duplication rate).
Gate: repeatable demo with preserved production controls.

## Kit 5 — Client installability
Packaging, secrets, IAM, tenant separation, TLS, config schema, capability discovery, adapter conformance tests, backup/restore, migration/rollback, offline/online installation guides.
Gate: clean-room installation and second adapter profile without rewriting Core.

## Delivery ownership
- Integration: canonical architecture, Debian/GitHub provenance, change gates, release candidate.
- Core: identity/event contracts, correlation, outbox/ITSM xref.
- Portal: truthful E2E lineage UI, NOC, audit and KPI.
- Twin: contract-compatible test harness, isolation and expected outcomes.
- Worker: Temporal/Worker execution evidence, idempotency, action guard.
Cross-cutting Policy/ITSM/Evidence reviews owned by Integration with Core and Worker.

## Git and cron discipline
Do not change deploy/aiops2-stable, main, or existing cron jobs. Work in component branches or audit branch; no auto-merge. Audit branch must never be auto-deployed. Before using any existing cron path, inspect its branch, command, credentials handling, and side effects, and obtain explicit authorization for changing production automation. CI can validate candidate code; Debian runtime evidence is separate.

## Acceptance matrix
Each deliverable includes owner, commit SHA, tests, evidence origin, Debian installed? (yes/no/unknown), risk, rollback, approval required, unresolved blockers. HOLD by default if provenance or E2E proof missing.
