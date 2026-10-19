# AIOps 2.0 — target architecture: Temporal and ACME digital twin

Author: Abdelhalim Talbi  
Date: 2026-10-19

## Business chain

`CHAOS / ACME TWIN → INGRESS → CORRELATE → CMDB → OBSERVE → RAG → DGX_ANALYST → DGX_CRITIC → POLICY → HITL (when required) → REMEDIATE (only when authorized) → VERIFY → ROLLBACK (if safe and needed) → LEARN → GLPI / closure`

Temporal owns durable orchestration, retries and workflow history. Activities must be idempotent, have bounded timeouts/retries, and expose their results and provenance. Do not infer that every stage is implemented merely because the target architecture lists it.

## Run identity

Carry explicit `run_id`, `incident_id`, `correlation_id`, and where relevant `episode_id` / `execution_id`. Never infer run identity from incident identity. Reject missing or contradictory execution identifiers.

## Temporal routing observed in the audit

- V2 backend container: `aiops2_temporal`.
- V2 worker queue: `aiops2`.
- Namespace catalog returned `default` and `temporal-system`.
- Existing workflow visibility included `AIOpsRun` and `IncidentDecisionWorkflow`.
- Historical FastPath backends remain separate and use namespace `aiops`, queues `aiops-v28` and `aiops-incidents`.

The V1.1 preflight failed because the Compose file path from the running container labels was absent. Verify the real configuration before changing any routing or running deployment commands.

## ACME twin and simulation

Represent sites, services, compute, hypervisors, storage, SAN, network, applications and dependency edges explicitly. Each chaos campaign must declare seed, scope, failure profile, preconditions and event timeline. Same-seed replay should be deterministic and compare against a baseline campaign.

Persist separately: simulated state, observed state, AI recommendation, policy decision, human approval, proposed/executed action and verification evidence. Simulation-only is the default. Synthetic scenarios must not mutate LIVE systems.

## Safety invariants

- `SIMULATION_ONLY=true` by default.
- `AUTO_REMEDIATION_ENABLED=false` by default.
- `HITL_REQUIRED=true` for sensitive actions.
- P1 escalates; no automatic remediation.
- Missing, stale, conflicting or unproven evidence means `UNKNOWN`.
- PC11K5 fencing/ownership, preconditions, effect evidence and reconciliation remain unchanged.
- No production restarts, migrations, destructive cleanup or DB restore without verified preflight, backup, rollback and approved scope.

## Qualification boundary

The deployment kit and recovered historical portal sources do not prove full Temporal-chain implementation. Unit, contract, integration, synthetic E2E and production qualification must be reported separately, with exact commands and outcomes.