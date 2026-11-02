# ADR — Core REJECT-only delivery fence and native GLPI actor authority (2026-11-01)

Status: **Draft, synthetic qualification only; RELEASE_STABLE=NO_GO**. Owner: Core. Target: sole architect candidate #234. Does not grant human actor access, approve, execute or mutate GLPI.

## Delta and wire contract

The existing installed `011_hitl_decision_outbox.sql` remains the **only** HITL outbox. No new migration or duplicate ledger is introduced.

* `POST /api/tenants/{tenant_id}/hitl/reject-delivery/claim`: service Bearer with server ACL tenant and `hitl:reject:deliver`, body `{"owner":"<service actor_id>","limit":1}`. Select one canonical REJECT/REVOKE outbox row with `FOR UPDATE OF o SKIP LOCKED`, join exact proposal hash/revision, approval, Run→Incident and tenant ownership; independently verify signed ownership, bitemporal freshness; set a random 30-second lease token and increment attempts transactionally. Returns a single no-effect REJECT item or `UNKNOWN`/empty.
* `POST /api/tenants/{tenant_id}/hitl/reject-delivery/{event_id}/ack`: same service authorization, exact owner/tenant/Run/proposal/hash/revision/lease token, no-effect booleans, canonical proposal and approval joins, row lock, lease expiry, then conditional `DELIVERED` update. A repeated exact ACK is idempotent; an expired/replaced/foreign lease cannot ACK. Never treats HTTP 200 alone as a delivery proof.
* All responses use `aiops.core-hitl-reject-delivery.v1`, `Cache-Control: no-store`, and `execution_allowed=false`/`effect_allowed=false`. Invalid/foreign business references are non-enumerating `UNKNOWN`; missing/invalid service Bearer is 401, service tenant/permission mismatch 403, database failure 503.

**No Worker integration in this PR.** Policy owner must independently validate the claim/ACK shape against `app/worker/hitl_reject_notification.py` before any consumer is enabled. The ACK is an audit notification receipt, never HITL APPROVE or remediation permission. The service identity `actor_id` is the lease owner; the caller cannot substitute a Worker name. No Temporal signal is sent by Core.

## GLPI native human rights — independent authority still missing

The actor OIDC introspection introduced by #246 authenticates the subject but does not establish a native GLPI user/profile/entity grant. `glpi_user_id` inside an IdP response, an HMAC fixture, a `verified=true` field, or service-session GLPI Ticket/Entity/CI readback is **not** independent GLPI human authorization. Actor resource authorization therefore remains **UNKNOWN, never ALLOW**.

The next adapter must, using independently authenticated source credentials and a tenant/instance-pinned HTTPS origin, read GLPI User, Profile_User, Profile rights, Entity and Ticket/CI under **native actor context**, verify the OIDC subject↔GLPI identity mapping against an independent directory attestation, and enforce exact tenant, entity inheritance/recursion, ticket and CI scope, permission, timestamps and revocation. Do not infer rights from a username, text `RUN-*`, copied ticket ID or a service credential.

Before a positive authorization, install an architect-approved durable nonce/JTI and revocation ledger with unique (issuer, tenant, subject, jti, nonce, exact resource digest), atomic consume, bounded expiry, revocation generation and replay rejection. Tests must cover subject collision, entity inheritance, role change, revoked/expired token, tenant collision, concurrent nonce use, source outage, replay, cross-instance and false profile grants. No new SQL is proposed until the migration ADR and combined chain are reviewed.

## Qualification boundaries

Local synthetic HTTP tests cover service 401/403, owner spoof, limit, exact lease token, proposal hash/revision, expired lease, idempotent delivered ACK, cross-tenant, missing ownership attestation and DB 503. The existing shared Quality suite discovers the new Core tests via the Core-owned test bridge; the architect-owned workflow is untouched.

Installed 009 AI → 010 Evidence → 011 HITL → 012 xref idempotence and transaction rollback are a **separate** disposable PostgreSQL 16 gate already on the candidate. This PR does not claim a populated-data downgrade; that needs a distinct restore/downgrade fixture, row-level assertions and a disposable database. The SQL claim/ACK paths must be exercised on disposable PG16 before any Worker transport is enabled.

## Rollback

Revert the focused Core commits on this PR; no new schema or persistent data migration. Do not roll back or edit the architect candidate, shared Quality, Worker, Policy, Portal, GLPI, or a real database. All status/impact claims remain UNKNOWN unless independently source-qualified.
