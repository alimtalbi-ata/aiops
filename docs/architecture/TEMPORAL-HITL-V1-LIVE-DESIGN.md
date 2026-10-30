# AIOps2 Temporal HITL v1 — LIVE design

**Status:** implementation design / fail-closed  
**Target branch:** `feat/temporal-hitl-v1`  
**Base:** `feat/glpi-hitl-proposal-fastpath`  
**Model endpoint:** DGX NIM OpenAI-compatible API  
**Model ID:** `nvidia/NVIDIA-Nemotron-3.5-Super-VL-120B-A12B-NVFP4`

## Scope

Connect the existing Core proposal/approval ledger to a durable Temporal human-wait state and an authenticated Portal workflow. LIVE means real incident/evidence processing and a real human decision; it does not enable automatic remediation.

## Source baseline inspected

- `app/worker/workflow.py` runs the ordered stages and currently has no Temporal signal or durable human wait.
- `app/worker/main.py` invokes the Intelligence API for Analyst/Critic, persists their records, and currently blocks every LIVE stage because LIVE evidence/CMDB/RAG/remediation adapters are not qualified.
- `app/core/main.py` contains proposal creation and approval persistence, including proposal-hash and scope checks, expiry, risk-tier role allowlists, and two distinct required roles for CRITICAL proposals. Approval currently returns `execution_allowed: false`.
- `app/portal/main.py` exposes a read-only proposal inbox and explicitly does not offer browser approval because verified human identity is not yet bound to approver roles.
- `app/intelligence/main.py` reads `LLM_BASE_URL`, `LLM_MODEL`, and `LLM_API_KEY`; Nemotron must be configured through the existing Intelligence service, not hard-coded in the workflow.

## Required end-to-end design

1. Keep Analyst/Critic calls in Worker activities. Record the exact provider, model, prompt version, evidence IDs and evidence-set hash with each result.
2. Create a proposal only from a persisted, validated Analyst record and a clean persisted Critic record. The proposal must bind run, incident, action, target CI, parameters, evidence, preconditions, expected postconditions, rollback plan, revision, expiry and canonical hash.
3. Persist the human decision and a notification/outbox record in the same Core database transaction. A post-commit best-effort HTTP callback is not sufficient.
4. A Worker reconciler claims outbox records with lease/fencing semantics, signals the exact Temporal workflow ID, and records delivery idempotently. Lost acknowledgements must be safe to retry.
5. The workflow enters a durable wait state after the HITL stage. It accepts only a decision matching the run, proposal ID, revision, hash, scope and current status. Rejection, expiry, revocation, cancellation, duplicate and stale signals must be terminal or fail-closed outcomes.
6. Before any future effect, re-read Core approval state and re-run Policy against current evidence freshness, target identity, preconditions, ownership/fencing and emergency stop. A Temporal signal is notification, never execution authority.
7. Portal must display the evidence and complete proposal scope before allowing a decision. Actor identity and role must come from a verified IdP assertion, not browser-supplied `actor_id` / `actor_role` fields.
8. CRITICAL continues to require two distinct actors and the distinct required roles `security_admin` and `incident_commander`. No self-approval, role reuse, hash substitution, or expired approval.
9. Preserve append-only audit and evidence. Never rewrite prior decisions; revoke by recording a separate revocation event.
10. Add deterministic unit, API, Temporal replay/time-skipping, duplicate-delivery, lost-acknowledgement, restart/recovery, expiry, rejection, revocation, role-escalation and concurrent-approval tests.

## Hard LIVE gates (must remain closed until qualified)

- Real source evidence adapters and authoritative freshness/provenance.
- Real CMDB and target-CI identity binding.
- DGX Nemotron Analyst/Critic contract qualification against the production endpoint and model.
- Verified human identity provider, issuer, audience, signing keys, actor-to-role mapping and revocation semantics.
- Transactional approval outbox and Temporal delivery/reconciliation.
- Policy recheck and executor-side ownership/fencing/precondition enforcement.
- Independent postcondition verification and rollback qualification.

Until every gate is independently qualified, the system may collect a human decision and demonstrate durable workflow resumption in a non-effecting test harness, but MUST keep `execution_allowed=false` and must not invoke remediation adapters.

## Configuration contract

Use the existing Intelligence settings `LLM_BASE_URL`, `LLM_MODEL`, `LLM_API_KEY`, and bounded `LLM_TIMEOUT_SECONDS`. The expected DGX values are deployment configuration, never committed secrets. Do not log API keys or raw authorization headers.

Human identity configuration is intentionally not guessed. The IdP must be selected and its issuer, audience, JWKS/discovery URL and role-mapping contract reviewed before enabling any LIVE approval endpoint.

## Deployment and rollback

No production compose change, container restart, database migration, workflow launch, GLPI write, or live approval is part of this source change. Apply migrations only after backup, preflight, reviewed rollback, and explicit deployment authorization. Roll back by disabling the HITL approval route/worker signal consumer and restoring the prior application image; preserve already-written audit rows and outbox records for reconciliation.
