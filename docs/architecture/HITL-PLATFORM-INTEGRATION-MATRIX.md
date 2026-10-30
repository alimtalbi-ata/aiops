# AIOps2 HITL v1 — platform integration matrix

**Branch:** `feat/temporal-hitl-v1`  
**Target:** LIVE-ready architecture with a non-effecting IAM simulator  
**DGX model:** `nvidia/NVIDIA-Nemotron-3.5-Super-VL-120B-A12B-NVFP4`  
**Execution posture:** fail-closed; all newly added authorization helpers return `execution_allowed=false`.

## Integration principle

HITL is not a standalone approval screen. It is a cross-platform control plane. The canonical run, evidence, proposal, decision, policy evaluation, workflow state, target identity, ITSM record and audit trail must all refer to the same run and immutable proposal hash. A Temporal signal is a notification of a Core-persisted decision, never the source of authorization.

## Service-by-service integration

| Platform component | Required HITL integration | Current branch change | Remaining qualification |
|---|---|---|---|
| Portal | Operator inbox, identity status, evidence and scope review, approve/reject/revoke UX | Adds read-only `/hitl` cross-platform command center | Bind Portal sessions to verified IdP; implement decision UI only after identity verification |
| Core | Canonical proposals, immutable revisions, approvals, role policy, audit | Adds isolated simulator identity routes; existing proposal/approval ledger remains canonical | Replace trusted caller-supplied actor fields with verified provider claims; transactional decision/outbox semantics |
| Temporal | Durable wait, idempotent signal, timeout and conflict handling | Adds `submit_hitl_decision` signal and bounded wait; missing persisted proposal now blocks before REMEDIATE | Add integration tests against Temporal test server; approval still cannot release execution |
| Worker | Reconcile Core decision state into the exact run workflow | Adds a HITL proposal activity that only uses explicit allowlisted Analyst action fields after a clean persisted Critic in LIVE; DEMO/REPLAY/STORY record an explicit no-approval simulation skip and retain execution_allowed=false; adds at-least-once Core-to-Temporal signal polling | Add durable cursor/lease or transactional outbox; verify retry/restart and workflow-not-found behavior |
| Intelligence / DGX | Nemotron Analyst and Critic evidence-grounded outputs | Extends the strict Analyst action schema with explicit allowlisted action type, parameters and expected postconditions; DGX config stays deployment-owned | Add model/provider/prompt/evidence-set attestation to proposal provenance and LIVE contract qualification |
| Evidence | Freshness, provenance, evidence IDs and hash bound to proposal | Existing Evidence API remains the source used by Worker/Core | Qualify all real-source adapters and immutable snapshot/hash semantics |
| Digital Twin / CMDB | Bind proposal target CI to authoritative CI identity and dependency context | No write path added | Verify CMDB target ownership, CI identity and topology freshness before approval and again before execution |
| Policy | Risk tier, autonomy mode, freeze, evidence freshness, preconditions, fencing and emergency stop | Existing Policy remains authoritative; new sudo helper is precheck-only | Add mandatory post-approval Policy recheck and executor-side fencing |
| Linux / Unix execution | SSH machine identity, constrained wrappers, sudo policy, host verification and command audit | Adds a logical sudo action catalogue; it never runs commands | Implement host-specific root-owned wrappers, SSH CA/machine identity, sudoers/LDAP policy and postcondition verification |
| GLPI / ITSM | Ticket linked to incident/run/proposal/decision/execution/verification | No GLPI writes added | Add idempotent lifecycle sync and verify ticket IDs/status/report against Core |
| Observability | Metrics and audit for queue depth, wait duration, approval/rejection, timeout, signal lag and execution outcomes | Portal status view surfaces current identity posture | Add Prometheus metrics, Grafana panels and alerting without logging secrets or sensitive evidence |
| Learning / governance | Human-reviewed outcome, verified postcondition and gold-set eligibility | Existing Core learning gates remain unchanged | Link approval and verified execution evidence; simulator events must never enter LIVE gold data |

## Implemented in this branch

1. `app/shared/hitl_identity.py`
   - Provider-neutral signed assertion format for simulator use.
   - Fictional operator, senior, storage, security, incident commander and platform identities.
   - Explicit group-to-role mapping with mapping version.
   - Short-lived HMAC assertions with issuer, audience, expiry, nonce and `simulated=true`.
   - Simulator assertions are rejected by LIVE verification.
   - CRITICAL role separation helper checks distinct subjects.
   - Fixed logical Linux action catalogue; no free-form commands and no execution authority.

2. `app/core/hitl_identity.py`
   - Simulator health, catalog and token endpoints.
   - Endpoints are absent unless both simulator feature flags are enabled.
   - Production directory is explicitly reported as not configured.

3. `app/worker/workflow.py`
   - Temporal signal handler for one immutable decision binding.
   - Durable wait with bounded timeout.
   - Duplicate identical signal is idempotent; conflicting signals fail closed.
   - Proposal ID, hash and revision must match the proposal returned by the HITL stage.
   - A human approval does not advance to REMEDIATE in this release.

4. `app/worker/main.py`
   - At-least-once reconciliation of Core proposal statuses to the workflow identified by run ID.
   - Core remains the authority; Temporal signal delivery does not grant execution permission.

5. `app/portal/main.py`
   - Read-only `/hitl` command center with navigation to Core runs, timeline, DGX, Evidence, Twin, Policy and Copilot.
   - Displays simulator and LIVE readiness state. No approval buttons or secrets in the browser.

6. Tests:
   - `tests/test_hitl_identity.py`
   - `tests/test_hitl_workflow_contract.py`

## Explicitly not implemented yet

- No production AD/LDAP bind, OIDC/SAML federation, Kerberos or SSSD configuration. The directory connector must be a separately qualified adapter.
- No authenticated Portal approval endpoint. Existing Core approval API requires the internal token and accepts actor fields; do not expose that API to a browser or treat browser-supplied role claims as identity.
- No database migration or transactional HITL outbox. The current Worker poller is at-least-once best-effort reconciliation, not a transactional delivery guarantee.
- Proposal creation is wired only for LIVE runs with fully structured Analyst actions after a clean Critic. DEMO/REPLAY/STORY skip human approval explicitly and continue only through synthetic no-effect stages; they do not mint approval or execution authority. The current LIVE path remains blocked earlier because real LIVE evidence/CMDB/RAG/Analyst/Critic adapters are not qualified. Approval is still not sufficient to resume into remediation; execution stays closed.
- No LIVE evidence, CMDB, Policy or execution adapters are enabled by this work.
- No SSH connection, sudo command, remediation, GLPI mutation, workflow launch or production deployment was performed.

## Runtime configuration for the simulator

Enable only in an isolated development stack:

- `AIOPS_HITL_IDENTITY_MODE=SIMULATOR`
- `AIOPS_HITL_SIMULATOR_ENABLED=true`
- `AIOPS_HITL_SIMULATOR_SIGNING_KEY` = independently generated random secret of at least 32 bytes

Never commit the signing key. Do not enable the simulator on an internet-facing or production LIVE Core. Simulator assertions carry `simulated=true` and are categorically rejected for LIVE.

## Production AD / LDAP design constraints

- Prefer enterprise OIDC/SAML federation for Portal authentication; AD/LDAP supplies authoritative groups and immutable subject IDs.
- If direct LDAP auth is required, use LDAPS/StartTLS with CA validation and a dedicated read-only bind account.
- Map immutable AD group SIDs/objectGUIDs to a versioned allowlist of application roles.
- Fail closed on disabled users, unknown groups, directory outages, stale privileged membership, expired assertions or revocation uncertainty.
- Do not impersonate users or collect/replay passwords, TGTs or reusable credentials.
- Linux hosts may use SSSD for identity/group resolution. Execution uses a dedicated machine identity, not the approver's password or ticket.
- sudo permits only fixed root-owned wrappers with strict arguments and narrow host scope; no unrestricted shell, `sudo ALL`, wildcard interpreter, or browser-provided command.

## Mandatory acceptance gates before LIVE approval or execution

1. Verified human identity (issuer, audience, signature/JWKS, immutable subject, group mapping, session revocation).
2. Core approval authorization derives actor and roles only from verified assertions; self-approval and critical role separation tested.
3. Core approval and notification outbox commit atomically; Worker reconciles with leases/fencing and idempotent delivery.
4. Temporal restart, replay, duplicate, conflicting signal, timeout, rejection and revocation tests pass.
5. Proposal hash binds exact run, action, target CI, parameters, evidence, preconditions, postconditions, rollback and expiry.
6. Policy rechecks current state, evidence freshness, emergency freeze, ownership and fencing after approval.
7. Host-specific SSH identity, sudo wrapper allowlist, host key verification, command audit and rollback are qualified.
8. Independent verification confirms postconditions; GLPI and learning records correlate to the same run and proposal.
9. Security tests cover role escalation, stale LDAP cache, directory outage, disabled accounts, nonce replay, hash substitution and concurrent approvals.
10. Production rollout is separately authorized with backup, migration plan, canary, rollback and operator runbook.

Until all gates pass, all routes and activities must preserve `execution_allowed=false`; the system may simulate decisions but must not run remediation.
