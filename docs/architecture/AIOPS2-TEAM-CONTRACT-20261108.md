# AIOps2 — coordination des cinq rôles ChatGPT

All scheduled roles share the single objective: functional, demonstrable Digital Twin E2E, customer-installable AIOps2 with adaptable ITIL 4 integrations. Debian is operational truth; GitHub is candidate code. This is a coordination contract, not a deployment instruction.

## Role ownership
- Integration: gatekeeper, architecture, cross-component contracts, baseline, PR collision avoidance, read-only evidence; do not merge.
- Portal: NOC trace visualization and truthful read-only FS147/FS1250 views; do not fabricate approval/resolution.
- Core: incident/run/external reference lineage, ITSM reconciliation contracts, idempotent outbox.
- Twin: scenario coverage, SAN/FS isolation, contract-compliant customer test bench.
- Worker: Temporal/Worker traces, action-bound authorization, negative/idempotency tests.

## Required hourly handoff
For each cycle report: baseline checked (Debian observed / GitHub only / unknown); branch + commit; files owned; contract changes proposed; tests and limitations; impact on GLPI, HITL, Temporal, evidence; one next blocking issue. Coordinate through docs/architecture/AIOPS2-RECONCILIATION-WORKPACKAGES.md. No cross-role file edits without agreement.

## Known acceptance cases
- FS1250: RUN-8CA56A39E58944F1, GLPI #201 observed in UI, no Core xref, Critic Policy outbox RECONCILED. No ticket creation, no unsafe remediation.
- FS1233: RUN-C3BD568B15367B66, GLPI #200 observed in UI.
- FS1130: 50 incidents, 44 confirmed links; six missing xrefs, not automatically six missing tickets.
- FS147: historical existing GLPI #147 must not be recreated; dynamic ticket IDs in generic code.

## Guardrails
No Debian SSH assumed, no Docker restart/cleanup, no writes to live databases, no POST, no cron/auto-deploy changes, no merge/deploy, no approval bypass. Preserve all advanced Debian functionality; classify missing evidence UNKNOWN. Branch audit/preserve-debian-48h-20261108 is not a deployment source.
