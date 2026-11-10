# AIOps2 — durable supervisor handoff and eight-hour execution mandate

**Recorded:** 2026-11-01 Europe/Paris. **Owner:** Architecte intégrateur (existing schedule 5/5). **Canonical repository:** `alimtalbi-ata/aiops`. **Existing-host only:** `SRV-DEB-05` (Debian 13). This document is the recovery point when conversational context is lost. Do not reconstruct priorities from stale prompts without re-reading current GitHub SHA, PR, CI and runtime report.

## Existing scheduled team — DO NOT create duplicate agents

Five existing hourly automations, verified by private automation lookup. They are enabled. Architect schedule prompt was updated with the eight-hour mandate and an immediate run was requested successfully; **request acceptance is not proof that work finished**.

| Slot | Role | Automation ID | Exclusive scope |
|---|---|---|---|
| 1/5 | ACME & Digital Twin | `6ae0f116e1f88191a38cecbc15d683d4` | Deterministic ACME incidents, Twin fixtures, ITIL impact |
| 2/5 | Portal & GLPI UX | `6ae0f10e37fc8191a2ba89d5f61ef114` | Portal operator experience, GLPI display |
| 3/5 | Core, NOC & CMDB | `6ae0f111268c81919131dc4ca347da15` | Core xref, Evidence, canonical CMDB/provenance |
| 4/5 | Policy & HITL | `6ae0f113bebc8191ba0621e774133dfa` | Worker, Policy, outbox, Temporal tests |
| 5/5 | Architecte intégrateur | `6ae0f1197a8c81919e5f296137346bba` | Supervise schedules, assign tasks, review PRs, integrate only after gates |

**No sixth schedule.** All schedules currently hourly. Architect is sole integrator; owners do not merge. Preserve team-specific prompts and guardrails. The architect must adjust the four owners' prompts as work advances, cap simultaneous P0 to three, and publish handoffs with actual exact-head evidence.

## Eight-hour acceptance contract

Deliver by eight hours from the user's 2026-11-01 instruction, with timestamp and timezone in final report:

1. **Runtime telemetry:** verify published report freshness, actual active vs historical containers, service health, source timestamps, missing probes and failed cron publication; distinguish `RUNTIME_OBSERVED` from `NOT_TESTED`.
2. **Executable tests:** machine-readable, service-scoped smoke results for Core, Worker, Twin, Policy, Temporal, Portal in disposable environments; actual Debian execution only if supported by observed evidence, not inferred from CI.
3. **Fixes:** targeted PRs with tests N/N, exact SHA, CI workflow URLs, security review, rollback. No duplicated stacks or broad rewrites.
4. **Enterprise demo:** deterministic ACME SAN -> Twin -> Payments, Event -> Incident -> Run -> Evidence -> Policy/HITL -> SIMULATE -> verification -> resolve/reopen, with honest GLPI native approval status.
5. **Integration:** one candidate branch, dependency-aware review, no merges without green exact-head checks and rollback. Publish explicit GO/NO_GO and blockers.

Each owner handoff: objective; source branch/base/head SHA; changed files; exact commands and N/N; CI run URL/status; artifacts/checksums if present; source vs runtime provenance; dependencies; risk; rollback/revert; next action. Report **zero** where no verified results exist. Avoid repeated audits without code/test/doc delta.

## Observed baseline (not a promise of deployment)

- [Existing-host automation runbook](../operations/SRV-DEB-05-AUTOMATION-RUNBOOK.md) and [versioned SSH publisher](../../scripts/aiops-publish-report.sh) added in commit `a06059b459543d15d83b7ee521223b004aec3cea`, PR [#286](https://github.com/alimtalbi-ata/aiops/pull/286).
- Debian user successfully ran `REPORT_PUBLISH=PUBLISHED` on 2026-11-01, report branch commit `013eb64`. Cron lists reporter every minute, publisher every five minutes, stable portal poller every five minutes.
- Independently fetched `ops/debian-runtime-reports:ops/debian-reports/SRV-DEB-05/latest.json`: `collected_at=2026-11-01T11:29:01.709559+00:00`, **61 containers**. Historical `aiops2-portal-rollback-v2-20261028` was exited/unhealthy; do not label active portal broken from this alone. Confirm subsequent freshness before claiming ongoing cron publication.
- GitHub SSH key works; old reporter still emits `COLLECTED_LOCAL_TOKEN_NOT_CONFIGURED` for unused legacy API publishing path. Separate SSH publisher is authoritative.
- Existing poller tracks `deploy/aiops2-stable` and invokes `deploy/deploy-demo-studio-v2.sh` on new SHA. **Do not push this branch to trigger tests.** Docker/volumes preserved; no `down -v`, global prune, or LIVE remediation.
- Sole integration candidate at last observation: Draft [#234](https://github.com/alimtalbi-ata/aiops/pull/234), branch `integration/enterprise-slice-main-20261031-2230`, SHA `6755405ffb8538470925163f1466b45686d9b4af` (historical snapshot, re-fetch before edits).
- Draft #286 is source work for existing-host autonomy; its typed task executor is **not** established as an installed runtime command channel.
- Native human GLPI HITL approval is **NOT_ATTESTED**; simulation is not a substitute.

## Immediate owner dispatch and collision control

**Architect (P0):** inspect current #186, #234, #286, exact HEAD CI, current report. Update four existing schedules and board. Establish 8-hour scoreboard with proof links; no self-reported green without evidence.

**Core (P0):** canonical read-only binding of tenant/actor/Incident/Run/GLPI ticket/entity with provenance, independent authority and fail-closed. Core owns migrations and APIs; Policy must not edit Core files.

**Policy (P0):** worker lease/retry/dead-letter/outbox adversarial tests with zero-effect guarantee. No false positive HITL approval. Coordinate terminal DEAD with Core, no cross-file ownership.

**Portal (P0):** verify active portal vs rollback, then targeted operator UI incident timeline, evidence and HITL status with real contract; never claim actual GLPI approval.

**ACME (P1 queued):** deterministic Twin-backed SAN->Payments scenario, priority/impact/urgency/maintenance metadata only when supported by graph; fix bearer-token origin allowlist in locator before promotion. No invented live observation.

Promote ACME to P0 only when a P0 frees capacity. The architect may reassign slots with documented rationale.

## Context-recovery procedure

1. Read this file, the [runtime runbook](../operations/SRV-DEB-05-AUTOMATION-RUNBOOK.md), #186, reference architecture, reuse register and execution control board.
2. Inspect existing five automations (do not create a sixth); read latest execution receipts.
3. Re-fetch #234 and #286 HEAD, CI and all owner PRs; do not trust frozen SHA.
4. Fetch report branch JSON, compare `collected_at` to current time; classify stale telemetry separately from host failure.
5. Update owner tasks; commit focused code/tests/docs; use one candidate, preserve safe branch controls.
6. Publish next handoff and exact GO/NO_GO. Never claim background activity that was not observed.

## Limits

A scheduled architect run was requested, not independently confirmed completed. The assistant has GitHub connector access and can inspect published host telemetry but cannot directly run arbitrary commands on SRV-DEB-05. Future user-visible status must distinguish GitHub artifacts, CI and actual on-host proof. This file is a durable control-plane contract, not a substitute for execution evidence.
