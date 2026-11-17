# ADR — Core actor-resource authorization v1 preflight (2026-11-01)

**Decision:** Add a distinct, Core-owned, read-only actor-delegation preflight on the existing xref router. Preserve `aiops.core-itsm-xref-read.v1` and installed migrations 009 AI → 010 Evidence → 011 HITL → 012 xref unchanged. This PR does **not** enable positive actor ACL.

## Endpoint and trust boundaries

`POST /api/tenants/{tenant_id}/runs/{run_id}/actor-resource-authorization`

- Service `Authorization: Bearer` is checked by the existing server-side `AIOPS_XREF_READ_AUTHZ_JSON` digest ACL. The dedicated service permission is `actor:resource:authorize`, and the tenant must be authorized. A service bearer is **not** a human identity or GLPI permission.
- `X-Actor-Delegation` carries a short-lived opaque **server-held** IdP access token, not a browser bearer, caller-supplied subject or unsigned JWT. The operator pins `AIOPS_XREF_ACTOR_INTROSPECTION_JSON` with `url` (HTTPS introspection URL), `issuer`, `audience`, `client_id` and `client_secret`. Credentials must be provisioned outside Git and never logged.
- Core makes an independently client-authenticated OAuth2 introspection request for **every** authorization attempt, with TLS verification, no redirects, no ambient proxies and bounded responses. It requires `active=true`, `revoked=false`, exact issuer/audience, OIDC subject, tenant, exact Run/Incident/GLPI instance/ticket/entity, `run:read`, nonce, GLPI user ID, `jti` and a short bounded lifetime. The resource-specific claims are a proposed custom authorization-server extension; an ordinary ID token is **not** sufficient.
- The requested resource fields are only exact-match selectors, never authority. After introspection, Core checks the existing signed, tenant-scoped xref history, exact Run→Incident join, separately keyed ownership manifest and authenticated GLPI service Ticket/Entity/CI readback. A `RUN-*` ticket string cannot create an association.
- **No ALLOW path in this revision.** The existing GLPI readback is performed with a **service** session, not the human actor's native GLPI profile/entity rights. Neither a signed fixture, `verified=true`, IdP custom claims nor a service's ability to read GLPI proves native actor permission. An independently authenticated GLPI actor-session/native permission read, trusted OIDC↔GLPI user binding and durable nonce/replay/revocation semantics are required before positive authorization. Until then all otherwise valid requests return `200 {"schema":"aiops.core-actor-resource-authorization.v1","decision":"UNKNOWN"}` without resource IDs or subject. Missing/invalid service bearer is 401, service tenant/permission refusal 403, Core/DB failure 503. Missing/foreign/invalid resource and inactive/revoked actor token are indistinguishable UNKNOWN.
- The current Portal #245 consumer remains fail-closed. This route is **not** a permission to turn on Run/NOC/Copilot reads; the Portal owner must coordinate the eventual positive wire contract and server-held delegation, not consume the present UNKNOWN as ALLOW.

## Security and tests

Unit tests in `tests/test_core_actor_resource_authz.py` cover service 401/403, exact resource and nonce, HTTPS origin pinning, token introspection, issuer/audience/tenant/subject/permission, expiry, revocation, GLPI identity claim, redirection, content type, payload cap, synthetic signed xref and non-enumeration. They use only fake transport and DB; **no real IdP or GLPI requests**.

The existing installed PostgreSQL 16 001→004→009→010→011→012 migration chain, DDL idempotence and transactional rollback remain architect-owned Quality gates. **Populated-data downgrade is a separate unqualified gate**; a DDL transaction rollback is not a supported downgrade strategy. No schema change or data migration in this PR.

## Dependencies and rollback

Next Core/GLPI owner action: implement and test native GLPI actor-session permission read and trusted OIDC↔GLPI identity mapping with disposable mock servers, then add a durable one-time nonce/revocation store under a separately reviewed ADR. Only after these independent gates and exact-source-head PG16/HTTP CI may Core return a bounded `ALLOW` envelope; do not infer it from service xref VERIFIED. Coordinate Core claim/ACK endpoint ownership with Policy via #186; no Policy/Worker files are changed here.

Rollback: revert only the focused commits on this PR (new Core module, existing xref router registration, tests and this ADR). No DB changes, GLPI writes, shared workflow edits, deploy or LIVE.
