# AIOps 2.0 — Database Schema Catalog

**Author:** Abdelhalim Talbi  
**Source reviewed:** Git-tracked migrations 001, 002, 004, 006, 007 and 008 on main as reviewed 2026-10-19.  
**Status:** Source-derived inventory; not a database runtime inspection.

## Migration inventory

- 000_n8n.sql — reserved/minimal n8n initialization.
- 001_schema.sql — base run, event, evidence, gate, twin node/edge, scenario and command receipt tables.
- 002_integrity.sql — triggers preventing UPDATE/DELETE of run_events and evidence.
- 003_seed_twin.sql — synthetic topology seed.
- 004_operational_model.sql — temporal twin facts, incidents, observations, changes, impact assessments, scenario steps, stage state and API audit.
- 005_seed_acme.sql — ACME synthetic seed data.
- 006_execution_receipts.sql — run-to-Temporal workflow receipt.
- 007_runtime_hardening.sql — indexes, run checkpoints and demo artifacts.
- 008_event_idempotency.sql — unique event_key per run when event_key is non-null.

## Existing canonical tables

| Table | Role | Key constraints / caveats |
|---|---|---|
| aiops.runs | Durable run identity, mode, state, version, idempotency | Mode constrained to LIVE/DEMO/REPLAY/STORY; status constrained; optimistic version is part of API contract |
| aiops.run_events | Ordered run timeline | Unique run/sequence; append-only trigger; event idempotency key added in 008 |
| aiops.evidence | Source observations, claims, provenance, hash and payload | Append-only trigger; evidence provenance should carry run/mode/source identity and freshness metadata |
| aiops.gates | Stage gate result and required/observed evidence | State constrained to PASS/FAIL/BLOCKED/UNKNOWN |
| aiops.run_stage_state | Durable stage state, attempts and error | Stage-level retry state; verify completion/error semantics in Core |
| aiops.command_receipts | Idempotent command response ledger | Unique idempotency key |
| aiops.execution_receipts | Temporal workflow receipt per run | Workflow ID unique; inspect creation/recovery behavior |
| aiops.run_checkpoints | Stage/version/workflow checkpoint | Verify reconciliation with Temporal history on restart |
| aiops.api_audit | Request metadata and actor | Ensure sensitive payload values are redacted before insertion |
| aiops.twin_nodes / twin_edges | Topology nodes and relationships | Current seed/twin belongs to later ACME phase; temporal validity and confidence matter |
| aiops.twin_facts | Bi-temporal facts | valid_from/valid_to plus known_at; source_evidence_id link |
| aiops.incidents | Normalized incident summary | External ID unique; synthetic flag defaults true |
| aiops.observations | Time-stamped metrics/observations | Evidence link and explicit UNKNOWN status |
| aiops.changes | Change events and affected nodes | Synthetic marker and source payload |
| aiops.impact_assessments | Impact assessment tied to run/incident/service | Rationale and evidence IDs stored |
| aiops.scenarios / scenario_steps | Deterministic seeded scenario definition | Synthetic by default; scenario step schedule ordered |
| aiops.demo_artifacts | Captions/artifacts for repeatable demo | Must never be mistaken for live evidence |

## Important gap: explicit AI decision ledger

The migrations reviewed provide durable run events, evidence and policy gates, but do not yet show dedicated normalized tables for analyst output, critic output, versioned action proposals, human approval binding, effect receipt, postcondition verification and curated learning cases. Some values may currently be stored in run event payloads; that is not equivalent to a queryable/versioned domain contract.

Before implementation, map every existing write/read in Core, Worker, Policy, Evidence and Copilot to the schema. Then add an additive, versioned migration for any missing domain records. Avoid breaking existing APIs or relying on PostgreSQL initdb scripts to upgrade an already initialized volume: upgrade scripts must be run explicitly and be idempotent/transactional where possible.

## Required AI ledger entities for a future migration

1. analysis_records: run/incident, contract version, model/provider, prompt version, output JSON, input evidence IDs/hash, status, created_at.
2. critique_records: analysis ID, critic/provider/version, validated, issue list, evidence checks, output JSON, created_at.
3. policy_decisions: run, policy version, evaluated input hash, decision/state/reasons, gate proof snapshot.
4. action_proposals: immutable proposal version, target CI, allowlisted action, risk tier, preconditions, evidence IDs, expected postconditions, rollback plan, proposal hash.
5. approval_records: proposal hash, actor/role, decision, scope, expiry, nonce/replay protection and audit.
6. effect_receipts: proposal/approval references, idempotency key, executor/adapter, actual result and timestamps.
7. verification_records: expected versus observed postconditions, evidence IDs, outcome and confidence/quality.
8. reconciliation_records: desired/current state, status, discrepancy and recovery action.
9. learning_cases: parent case/revision, human-reviewed label, outcome verification strength, source/evidence references, synthetic flag and gold-set eligibility.
10. model_evaluation_runs: dataset/version, model/prompt/retrieval/policy versions, metric results, sample size, artifact references and gate decision.

All proposed tables must include stable identifiers, foreign keys where the lifecycle permits them, schema versions, timestamps and auditability. Append-only or explicit supersession is preferred for decision evidence. Do not add tables without mapping to API contracts and retention/access policy.

## Migration qualification

- [ ] Run all migrations from an empty disposable PostgreSQL volume.
- [ ] Run migration upgrade against a disposable snapshot of the previous schema.
- [ ] Prove repeat execution or documented one-shot semantics.
- [ ] Verify append-only triggers and indexes.
- [ ] Test foreign keys and concurrent/idempotent writes.
- [ ] Test backup/restore and schema version reporting.
- [ ] Confirm synthetic seed data is labelled and excluded from trusted live gold data.
- [ ] Verify no secrets or production exports are stored in migration fixtures.
