# FS147 — Temporal / Worker action-bound HITL conformance (candidate, 2026-11-08)

Owner: Worker. Baseline: GitHub candidate only; Debian installed state UNKNOWN. Reference: FS364 and docs/architecture/AIOPS2-{PRODUCT-REFERENCE-ARCHITECTURE,RECONCILIATION-WORKPACKAGES,TEAM-CONTRACT-20261108}. No live execution authorized.

## Proposed integration contract (not a Core/Policy schema migration)

An immutable ActionIntent carries tenant_id, incident_id, run_id, action_id, target resource/path, parameters_digest, preconditions_digest, policy_revision, expiry, dry_run, and idempotency_key. An approval receipt binds exactly these fields by a canonical digest and includes approver identity (distinct from requester), native approval identifier, decision, issued_at and valid_until. Any missing, mismatched, expired, unverified or reused approval is BLOCKED/UNKNOWN; approval for GLPI 146 never authorizes GLPI 147. GLPI 147 is an existing external reference: lookup/readback only; no create or RESOLVED.

Temporal workflow_id and execution_id, Worker attempt/fencing token, Core reservation reference, evidence IDs, observation provenance (fs-lab bridge identity, observed_at, received_at, freshness TTL), Critic verdict, Policy decision_id, and GLPI external reference must be correlated by the same run_id. Missing evidence is UNKNOWN, not PASS. Bridge df/du/ls only; no SAN dependency. The observation age must be checked before Analyst and again before Policy; stale or insufficient data blocks.

## Decision gate

1. Verify tenant, run, incident, existing GLPI external reference and Core atomic durable claim; False => DUPLICATE_RUN; ambiguous acknowledgement => IDEMPOTENCY_UNAVAILABLE/UNKNOWN; never replay a remote operation after unknown acknowledgement.
2. Verify source provenance, bounded freshness, read-only capability and Analyst evidence. Timeout/unavailable => UNKNOWN/NO_EFFECT.
3. Verify Critic PASS and Policy PASS on the same evidence digest, action digest and revision. Denial => BLOCKED/NO_EFFECT.
4. Verify native HITL action binding, expiry, distinct approver, and Temporal run/fencing token immediately before dispatch. Missing/mismatch/denial => BLOCKED/NO_EFFECT.
5. This candidate's only permitted outcome is SIMULATE; live dispatch remains disabled even if an approval is valid. Durable outbox/dispatch ownership and actual transport authentication require integration evidence.

## Negative integration matrix

- Concurrent same run_id: one Core claim; loser DUPLICATE_RUN; zero additional bridge/Analyst/Critic/Policy calls.
- Two distinct run_ids on GLPI 147: independent claims/evidence; no duplicate ticket.
- Claim None/1, remote timeout at each stage: UNKNOWN, NO_EFFECT, no automatic retry.
- Missing/stale evidence, mismatched tenant/ticket/run/action/target/parameters/policy revision, GLPI 146 approval, expired approval, same requester/approver: BLOCKED.
- Critic denial, Policy denial, Temporal run mismatch or stale fencing: BLOCKED.
- Resume after UNKNOWN: read durable receipt and reconcile before any further work; no second effect.
- Dry-run False: BLOCKED until separately approved implementation and live safety gate.

## Evidence and handoff

Worker: proposed guard, replay tests and Temporal receipt. Core: atomic claim/outbox and GLPI xref ownership. Twin: deterministic read-only fs-lab fixture. Portal: show UNKNOWN/BLOCKED without implied RESOLVED. Integration: Debian-vs-GitHub provenance, transport auth, end-to-end acceptance.

Qualification requires a trace receipt linking fs-lab observation -> Analyst -> Critic -> Policy -> Temporal/Worker -> existing GLPI 147 on one run_id. No claim of such receipt yet. No Debian inspection, deployment, ticket mutation or approval was performed by this document.
