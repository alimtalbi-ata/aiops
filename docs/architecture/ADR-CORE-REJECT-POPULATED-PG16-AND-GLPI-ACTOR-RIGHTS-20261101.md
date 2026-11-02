# ADR — Core REJECT delivery PG16 populated qualification and human GLPI rights boundary

**2026-11-01 — P0 Core-owned, Draft #234 integration dependency.**
Status: **test/contract only; no actor ALLOW, no GLPI write, no LIVE**.
Supersedes no earlier ADR. Existing schema `aiops.core-hitl-reject-delivery.v1`,
`aiops.core-actor-resource-authorization.v1` and installed migrations
009 AI / 010 Evidence / 011 HITL / 012 xref remain unchanged.

## What this delta actually exercises

`tests/test_core_hitl_reject_pg16_populated.py` calls **the actual Core route handlers** (no HTTP transport), actual psycopg transactions and installed PostgreSQL 16
tables. It creates its own `aiops_core_reject_populated_ci` database on the
CI loopback PostgreSQL service, refusing any other URL/PG version and refusing
to overwrite a pre-existing database. It inserts synthetic Incident, Run,
Evidence, Analyst, Critic, immutable REJECT approval, proposal, outbox event
and signed Run ownership. No human decision is fabricated as authenticated.

The existing Quality command
`PYTHONPATH=app python -m unittest discover -s tests -p 'test_core_xref_installed_migrations.py' -v`
imports the new suite. Tests exercise two concurrent Core handler claims
(`FOR UPDATE SKIP LOCKED`), single lease, expired lease reclaim, stale
token ACK refusal, exact eight-field ACK wire, response-loss replay after
committed ACK, cross-tenant service bearer refusal, source-proof removal,
and 009–012 reapplication against populated tables. Every fixture asserts
zero APPROVE and zero effect receipts. Worker #251 retains ownership of
its own synthetic transport; **Core never imports Worker code**.

A CI-only HMAC manifest is independently keyed relative to the outbox DB
row. It tests integrity and fail-closed behavior, **not** authenticated GLPI
or human rights. No ticket-text `RUN-*` is interpreted as linkage.

## Future native human authorization, still UNKNOWN

A future source-authenticated adapter MUST independently obtain:

1. IdP OIDC subject, issuer, audience, JTI, token active/revoked state,
   `iat/nbf/exp`, exact tenant/Run/Incident/ticket/entity/permission
   and nonce from server-authenticated introspection. Do not trust Portal
   headers, `verified=true`, fixture HMAC, or an OIDC-to-GLPI user ID claim.
2. A separate administrator-provisioned, versioned mapping from exact
   `(issuer, subject, tenant_id, glpi_instance_id)` to a GLPI user ID,
   authenticated from its own source and valid at request time. Mapping
   conflicts, deactivation, changed GLPI user or tenant return UNKNOWN.
3. Authenticated, **actor-scoped** GLPI native User, Profile/UserProfile
   and Entity rights, including recursive entity scope and effective ticket
   read permission; exact ticket/entity and attached CI readback through
   a credential genuinely restricted to the mapped human actor.
   A GLPI service session is insufficient for this positive grant.
4. Core-owned exact Run→Incident and signed tenant→GLPI instance→ticket/
   entity ownership with independently sourced association ID, source event,
   freshness, source version and revocation. No implied link from ticket text.
5. A **durable transactional** nonce/JTI ledger (not in-process memory)
   keyed by issuer, tenant, subject, JTI, nonce and exact resource digest.
   Enforce unique consumption, token expiry, explicit revocation and
   replay rejection across Core replicas/restarts, with retention and
   revocation propagation. A migration requires a separate ADR, populated
   upgrade/downgrade tests and architect integration approval.

All checks are conjunctive. Any missing authority, stale source, ambiguous
mapping, duplicate/revoked nonce, failed GLPI read or unavailable backend
returns **UNKNOWN** without resource identifiers. Do not emit ALLOW yet.

## Migration/downgrade qualification boundary

The new test proves idempotent reapplication of installed 009–012 **with
populated rows** and rollback of a deliberately uncommitted data transaction.
The existing installed gate separately proves transactional DDL rollback
on an empty disposable database. Neither proves a **persisted-data
downgrade**, which requires explicit down scripts, data preservation
requirements, restored snapshot, re-upgrade, and a dedicated PG16 test.
There is no approved destructive downgrade and no change to migrations.

## Ownership and rollback

Only Core tests and this Core ADR are touched; no shared Quality, candidate,
Worker, Policy, Portal, packaging or migration changes. Architect owns
selective integration into #234. Rollback is revert of this PR's commits,
then discard the disposable CI database. A test failure is NO_GO, not an
excuse to skip a PG16 gate.
