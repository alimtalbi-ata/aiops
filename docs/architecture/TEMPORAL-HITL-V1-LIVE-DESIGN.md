# AIOps2 Temporal HITL v1 — LIVE design

**Status:** implementation design / fail-closed  
**Target branch:** `feat/temporal-hitl-v1`  
**Base:** `feat/glpi-hitl-proposal-fastpath`  
**Model endpoint:** DGX NIM OpenAI-compatible API  
**Model ID:** `nvidia/NVIDIA-Nemotron-3.5-Super-VL-120B-A12B-NVFP4`

## Scope

Connect the existing Core proposal/approval ledger to a durable Temporal human-wait state and an authenticated Portal workflow. LIVE means real incident/evidence processing and a real human decision; it does not enable automatic remediation.

Identity must be provider-neutral and simulatable from day one. The intended production identity estate is Microsoft Active Directory / LDAP with delegated authorization, Linux/Unix host identity through SSSD where appropriate, and tightly constrained sudo execution. No identity provider is currently deployed, so the first implementation must not assume an existing AD, LDAP, Kerberos, OIDC, or SSO service.

## Source baseline inspected

- `app/worker/workflow.py` runs the ordered stages and currently has no Temporal signal or durable human wait.
- `app/worker/main.py` invokes the Intelligence API for Analyst/Critic, persists their records, and currently blocks every LIVE stage because LIVE evidence/CMDB/RAG/remediation adapters are not qualified.
- `app/core/main.py` contains proposal creation and approval persistence, including proposal-hash and scope checks, expiry, risk-tier role allowlists, and two distinct required roles for CRITICAL proposals. Approval currently returns `execution_allowed: false`.
- `app/portal/main.py` exposes a read-only proposal inbox and explicitly does not offer browser approval because verified human identity is not yet bound to approver roles.
- `app/intelligence/main.py` reads `LLM_BASE_URL`, `LLM_MODEL`, and `LLM_API_KEY`; Nemotron must be configured through the existing Intelligence service, not hard-coded in the workflow.

## Identity architecture: simulator first, AD/LDAP production adapter

### Provider-neutral contract

Create an Identity & Delegation Gateway behind Portal/Core. Application code consumes normalized, signed identity assertions and authorization decisions; it must not query LDAP directly from business routes or trust actor/role fields supplied by a browser.

Normalized principal claims:

- immutable `subject_id` (provider-scoped immutable identifier; never display name or email);
- `issuer`, `audience`, `auth_time`, `issued_at`, `expires_at`, and authentication method / assurance level;
- `groups` and normalized application roles, each with source and mapping-policy version;
- `session_id`, `delegation_id` (when applicable), and correlation ID;
- explicit `simulated=true|false` marker.

Every authorization decision records principal, roles/groups used, policy version, requested scope, decision, reason, and timestamp. Unknown identity, missing claims, expired assertion, unknown role mapping, stale directory data, or unavailable provider fails closed.

### Simulator mode

Provide a deterministic local simulator for development, integration tests, demos, and Temporal replay tests. It should model users, groups, role membership, disabled accounts, expiry, delegation grants, approval separation, and audit events. Seeded identities are fictional and clearly marked `SIMULATED`.

- Simulator identities must never be accepted by production LIVE endpoints.
- No simulator route may mint an assertion with `simulated=false`.
- No simulator action may contact SSH, sudo, AD, LDAP, or a real execution adapter.
- Tests can inject a clock and deterministic signing keys; development keys are never production defaults.
- A simulator decision may exercise workflow state transitions, but always returns `execution_allowed=false`.

### Production directory adapter: AD / LDAP

Implement a separately configurable adapter, not an assumption baked into the domain model:

- Prefer OIDC/SAML federation from the enterprise IdP for Portal browser authentication when available; use AD/LDAP as the authoritative directory/group source. If direct LDAP authentication is required, use LDAPS or StartTLS with certificate validation and an explicit bind policy.
- Use a dedicated, least-privilege, read-only directory service identity for lookup. Never use Domain Admin, directory write privileges, or a shared human password.
- Map directory groups to application roles through explicit, versioned allowlists (e.g. configured group SID/objectGUID/DN → `incident_commander`, `security_admin`, `storage_admin`, `senior_operator`, `operator`). Do not infer privileged roles from display names, arbitrary OU membership, or user-provided attributes.
- Resolve nested group membership according to a documented policy; detect loops and truncation. Record the exact group identifiers and mapping version used for each decision.
- Handle disabled/locked users, account expiry, group removal, token revocation, directory outages, replication delay, and stale caches. Privileged approvals require fresh authorization; stale cache or unknown state denies.
- Bind identities to immutable directory identifiers (objectGUID/SID), not mutable UPN, email, or common name. Normalize but retain original issuer and subject.
- Use short-lived signed sessions, audience restriction, CSRF protection, secure cookies, and server-side session revocation. Do not expose LDAP credentials, bind responses, access tokens, or raw authorization headers to browser logs.
- Directory delegation is authorization to request a bounded operation; it is not password impersonation and must not permit the application to obtain or replay a user's password, TGT, or reusable credential.

### Approval roles and separation of duties

Keep the existing Core risk-role matrix as the initial authorization policy. The simulator and future directory adapter must implement the same normalized role contract.

- LOW / MEDIUM / HIGH role allowlists remain those enforced by Core; directory mapping grants no extra role by default.
- CRITICAL requires two distinct human subjects and the two distinct required roles `security_admin` and `incident_commander`.
- The proposer cannot approve their own proposal. One human cannot satisfy both CRITICAL approvals through multiple sessions, accounts, aliases, or group memberships.
- Approval binds to proposal ID, revision, canonical hash, run, target CI, action, parameters, evidence set, expiry and preconditions. Any change creates a new revision and invalidates earlier approvals.
- A human decision is not a sudo grant and does not itself create execution authority.

## Linux / Unix delegation and sudo design

Use AD/LDAP for identity and group membership, SSSD for host-side identity/group resolution where supported, and a dedicated execution gateway for remote work. Keep the application authorization model separate from host sudo policy.

1. Human authenticates to Portal using the approved identity adapter. The gateway resolves current directory identity and normalized roles.
2. Core authorizes the proposal decision and records the human decision. The decision is not a shell credential.
3. After all HITL and Policy gates are satisfied in a future qualified release, the execution gateway receives a short-lived, signed, narrowly scoped job authorization. It does not receive the user's password or reusable Kerberos ticket.
4. The gateway connects using a dedicated per-environment automation principal / SSH certificate or other approved machine identity. Human subject, approvals, proposal hash and job ID are propagated as immutable audit context.
5. On the target host, sudo permits only exact, reviewed command wrappers or fixed binaries with validated arguments, narrowly scoped target accounts, and explicit host/group scope. Prefer root-owned wrappers with strict input validation over broad command patterns.
6. Capture sudo I/O / command audit where approved, SSH principal, target host identity, command digest, start/end status, exit code, and postcondition evidence. Secrets and sensitive command arguments must be redacted.
7. Recheck host identity, job expiry, proposal hash, target scope, emergency stop, current approval status and fencing token immediately before the privileged operation.

Sudo policy requirements:

- No general-purpose `sudo ALL`, unrestricted shell, arbitrary `sudo -u`, editor/interpreter escape, package-manager shell escape, or wildcard command grant.
- No browser-supplied command line. Commands are selected from a versioned action catalogue and generated by validated server-side adapters.
- No blanket `NOPASSWD` rule. If non-interactive execution is required, permit only specific root-owned wrappers for a dedicated automation account, with logging, narrow host scope, and independent Policy authorization.
- Avoid direct writes to user-managed `sudoers` from AIOps. Manage host policy through reviewed configuration management or a controlled LDAP sudoRole integration, with syntax validation and rollback.
- LDAP/SSSD unavailability, unknown group membership, stale privileged cache, host key mismatch, or sudo policy mismatch blocks execution.
- Do not grant the AIOps service account interactive login or unrestricted shell access.
- Linux sudo is not automatically portable to every Unix variant. Qualify each target OS and sudo version separately; unsupported hosts remain out of scope.

## Required end-to-end design

1. Keep Analyst/Critic calls in Worker activities. Record the exact provider, model, prompt version, evidence IDs and evidence-set hash with each result.
2. Create a proposal only from a persisted, validated Analyst record and a clean persisted Critic record. The proposal must bind run, incident, action, target CI, parameters, evidence, preconditions, expected postconditions, rollback plan, revision, expiry and canonical hash.
3. Persist the human decision and a notification/outbox record in the same Core database transaction. A post-commit best-effort HTTP callback is not sufficient.
4. A Worker reconciler claims outbox records with lease/fencing semantics, signals the exact Temporal workflow ID, and records delivery idempotently. Lost acknowledgements must be safe to retry.
5. The workflow enters a durable wait state after the HITL stage. It accepts only a decision matching the run, proposal ID, revision, hash, scope and current status. Rejection, expiry, revocation, cancellation, duplicate and stale signals must be terminal or fail-closed outcomes.
6. Before any future effect, re-read Core approval state and re-run Policy against current evidence freshness, target identity, preconditions, ownership/fencing and emergency stop. A Temporal signal is notification, never execution authority.
7. Portal must display the evidence and complete proposal scope before allowing a decision. Actor identity and role must come from a verified provider assertion, not browser-supplied `actor_id` / `actor_role` fields.
8. CRITICAL continues to require two distinct actors and the distinct required roles `security_admin` and `incident_commander`. No self-approval, role reuse, hash substitution, or expired approval.
9. Preserve append-only audit and evidence. Never rewrite prior decisions; revoke by recording a separate revocation event.
10. Add deterministic unit, API, Temporal replay/time-skipping, duplicate-delivery, lost-acknowledgement, restart/recovery, expiry, rejection, revocation, role-escalation, directory-outage, stale-group-cache, sudo-policy-drift and concurrent-approval tests.

## Hard LIVE gates (must remain closed until qualified)

- Real source evidence adapters and authoritative freshness/provenance.
- Real CMDB and target-CI identity binding.
- DGX Nemotron Analyst/Critic contract qualification against the production endpoint and model.
- Verified human identity provider, issuer, audience, signing keys, immutable subject mapping, group-to-role mapping, revocation and session invalidation semantics.
- Transactional approval outbox and Temporal delivery/reconciliation.
- Policy recheck and executor-side ownership/fencing/precondition enforcement.
- Linux/Unix host identity, SSH machine identity, sudo command allowlist, audit capture and rollback qualification per supported OS.
- Independent postcondition verification and rollback qualification.

Until every gate is independently qualified, the system may collect a simulated human decision and demonstrate durable workflow resumption in a non-effecting test harness, but MUST keep `execution_allowed=false` and must not invoke remediation adapters.

## Configuration contract

Use the existing Intelligence settings `LLM_BASE_URL`, `LLM_MODEL`, `LLM_API_KEY`, and bounded `LLM_TIMEOUT_SECONDS`. The expected DGX values are deployment configuration, never committed secrets. Do not log API keys or raw authorization headers.

Identity configuration is provider-neutral. Start with the deterministic simulator. Production AD/LDAP settings (directory endpoints, CA trust, read-only bind identity, base DNs, group mapping and SSSD/sudo integration) are deployment secrets/configuration and must never be committed. No real directory is presumed to exist. The production Portal federation mechanism and IdP must be selected and security-reviewed before enabling real human approval.

## Deployment and rollback

No production compose change, container restart, database migration, workflow launch, GLPI write, or live approval is part of this source change. Apply migrations only after backup, preflight, reviewed rollback, and explicit deployment authorization. Roll back by disabling the HITL approval route/worker signal consumer and restoring the prior application image; preserve already-written audit rows and outbox records for reconciliation.
