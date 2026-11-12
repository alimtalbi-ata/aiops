# ADR — Core native GLPI human-rights preflight and durable OIDC delegation replay fence

**Date:** 2026-11-01. **Status:** P0 proposal, fail-closed; not production-qualified. **Owner:** Core xref/NOC/Evidence/GLPI. **Candidate:** architect Draft #234; focused owner PR only. **Scope:** no Portal, Worker, Policy, shared Quality, packaging or real GLPI writes.

## Existing authority preserved

Core owns Incident, Run, tenant ACL and append-only cross-reference. GLPI owns Ticket, Entity, User, Profile and CI. The IdP owns the OIDC subject and token status. Evidence is append-only. A service bearer, signed xref row, synthetic HMAC or `verified=true` does **not** prove native human GLPI rights. `RUN-*` ticket text is never a link. The existing `aiops.core-itsm-xref-read.v1` and `aiops.core-actor-resource-authorization.v1` schemas remain unchanged. The actor endpoint always returns `UNKNOWN` (or its existing 401/403/503 denial) and never `ALLOW`.

## Independent sources / binding contract

The new `app/core/actor_native_authority.py` is a negative-only preflight, invoked **after** issuer-authenticated resource-bound OIDC introspection and exact Core Run→Incident→ticket/entity verification. It requires two distinct pinned HTTPS origins and separate credentials, with no ambient proxy, redirect, unbounded response or caller-supplied destination:

1. An operator-controlled identity mapping authority receives the exact `issuer`, `subject`, `tenant_id`, `glpi_instance_id`, `glpi_user_id`, `jti` and request `nonce`. It returns a versioned `aiops.core-oidc-glpi-actor-binding.v1` envelope with independent `source_event_id`, issued/expiry times, revocation flag and a short-lived **human** GLPI session token. The entire mapping is authenticated by HTTPS Basic client credentials and a separately keyed canonical HMAC. This HMAC is an integrity check, **not** evidence of actual issuer authority when the producer is a test fixture.
2. GLPI independently validates that actor session by read-only `getFullSession`, `User/{id}`, `Profile/{id}`, `Entity/{id}`, and exact `Ticket/{id}` reads. The session's `glpiID`, active profile and active entities must match the mapped human, requested entity and ticket. A 200 from the **service** GLPI session is insufficient; no native actor session or profile/entity read means `UNKNOWN`. A ticket `200` is only a candidate read permission for that exact ticket; it cannot grant any action or general CI rights.
3. The IdP must independently attest exact `Run→Incident` and resource claims; Core's signed association and tenant ownership must agree. The mapping source must be operationally distinct from GLPI and the xref HMAC producer. Production identity mapping, GLPI session provisioning, user/profile rights semantics, issuer key rotation and credential lifecycle remain **NOT_ATTESTED**.

The new adapter's internal boolean means **source-contract shape checked**, never `ALLOW`, `VERIFIED` or `LINKED`. Even all-positive synthetic responses leave the public actor endpoint `UNKNOWN`. No real GLPI/IdP/network requests are made in this qualification.

## Proposed durable replay and revocation ledger

`db/migrations/013_actor_delegation_replay_ledger.sql` is additive after installed `001/004/009 AI/010 Evidence/011 HITL/012 xref`; existing migrations are unchanged. Two append-only PostgreSQL tables persist SHA-256 digests of subject/JTI/nonce/resource, issuer, tenant, expiration and independently sourced revocation event. Raw tokens, GLPI session tokens and human identifiers are **not** persisted. A unique issuer/JTI key plus unique tenant/nonce key prevents reuse. `actor_delegation_consume` and `actor_delegation_revoke` serialize on the same transaction-scoped advisory lock and use database time, with a maximum five-minute expiry. Revocation tombstones remain durable. Calls must originate from a separately authenticated Core issuer adapter; the database functions do not authenticate callers themselves. No endpoint currently calls `consume` or `revoke`: the migration cannot silently activate `ALLOW`.

The migration is subject to architect review before integration; it does not change the installed 009–012 chain. The separate PG16 disposable suite tests populated replay, concurrent single-winner, revocation before/after consume, expiry, idempotent reapplication, immutable records and transactional rollback. A transaction rollback on populated data is **not** a production-safe persisted-data downgrade. A destructive downgrade must be refused unless a separately approved backup/restore and retention plan is qualified. No automatic deletion of revocation history is authorized.

## Adversarial contract and gates

Fail closed on: foreign tenant/entity, mismatched OIDC subject/GLPI user/profile/ticket, changed mapping signature, expired/revoked mapping, duplicate config, missing native session, redirect/HTTP source, replayed JTI/nonce, revocation, missing independent GLPI authority, missing source event, stale evidence or DB outage. Return no business identifiers on denial. Existing service auth and tenant permission checks precede source reads. No HITL APPROVE, synthetic human authorization, GLPI write, executor or LIVE path.

**Release gates:** (a) GLPI native human rights validated against a disposable real GLPI instance, (b) IdP subject↔GLPI mapping signed by an independently controlled issuer with key rotation, (c) atomic ledger integration with revocation ingestion, (d) installed 009–013 PG16 exact-head tests, (e) separate populated-data backup/restore downgrade qualification, (f) end-to-end tenant/actor non-enumeration. Until all pass: actor `UNKNOWN`, xref unverified without Core+GLPI readback, `RELEASE_STABLE=NO_GO`.

**Revert:** revert only the focused Core module, Core test bridges, ADR and proposed 013 migration. If 013 has already been applied, do **not** drop populated immutable ledgers; disable new calls and preserve records pending an architect-approved retention/downgrade procedure.
