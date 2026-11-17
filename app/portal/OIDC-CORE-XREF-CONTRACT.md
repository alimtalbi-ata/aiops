# Portal P0 — server identity → Core xref contract (design gate)

**Status:** Portal OIDC callback and ephemeral identity-only sessions implemented; no positive Core ACL, no real IdP or GLPI connection. **Source:** DEV candidate `integration/enterprise-slice-main-20261031-2230` at `ae7c3e5102b99a66bd7806d602146f1309a9749d`. This is not an integration attestation.

## Trust boundaries

1. A future Portal **server-side** authorization-code + PKCE callback exchanges the code directly with the configured OIDC issuer. Only the server receives the ID token; browser bearer, `X-Actor-ID`, `X-Tenant-ID`, `X-GLPI-Profile`, URL parameters, cookie values and submitted JSON are never accepted as identity or tenant authority.
2. `portal.oidc_identity.verify_server_oidc_assertion` verifies a **pinned, operator-provisioned** JWKS RSA RS256 signature and exact issuer, audience, subject, expiry, not-before, issue time, group mappings and unique tenant. No token-specified `jku`/`x5u` retrieval; no JWKS network request. Group mapping is explicit; it does not create GLPI rights.
3. Portal `/auth/oidc/login` initiates code+PKCE S256 with server-stored nonce/state, `/auth/oidc/callback` exchanges code only at the configured issuer-owned HTTPS token endpoint (no redirects/proxies), validates signed ID token + nonce, and issues an opaque revocable `__Host-` Secure/HttpOnly/SameSite=Lax cookie. `/auth/oidc/logout` requires exact Origin and revokes it; `/api/portal/session` returns 401 or **503 UNKNOWN** without actor/tenant disclosure. Sessions are **identity only**; never grant business ACL. Old Run cookies are ignored.
4. Portal must call a **Core actor+tenant authorization endpoint** for the exact requested Run and verified GLPI ticket/entity link, with a **separate service bearer** never forwarded from the browser. Core must return a positive, versioned ACL decision scoped to actor, tenant, Run, ticket, GLPI entity, permissions, expiry and source provenance before any other upstream fetch. The current `core_xref_preflight` never performs I/O or authorizes a read.
5. Until that contract and its negative tests are qualified, `/api/portal/runs/{rid}`, `/api/portal/run-session`, NOC, Copilot, cockpit and `/api/portal/itsm` stay fail-closed with UNKNOWN/503 after authentication. Absent, foreign and unqualified canonical Run IDs remain indistinguishable; no CONNECTED, Evidence, ticket, incident or tenant data.
6. The Portal has no ticket or CMDB authority. GLPI native profiles, entities, categories, forms, templates, plugins, SLA/OLA and business rules must be inspected through an authorized read-only connector before mapping permissions. N1/N2/N3/manager is a **display planning role**, not a grant to comment, assign or approve. All such controls stay disabled in DEMO; GLPI remains the ticket/CMDB source of truth.

## Core owner contract request

- Authenticated service-to-service xref endpoint (Core #229 is source candidate): actor subject and tenant must originate from a Core-verified server-side delegation, not from arbitrary Portal headers or URL/query/body claims.
- Positive result must bind `tenant_id`, `actor_subject`, `run_id`, `incident_id`, `ticket_id`, `glpi_instance_id`, `glpi_entity_id`, `permission`, `acl_version`, `authorized_at`, `expires_at`, `source` and `freshness`. Response must be signed or otherwise authenticated to the Portal service and reject mismatches.
- Denials must be no-leak: 401 unauthenticated, 403 known but forbidden only when safe, 503 UNKNOWN for unqualified/absent/foreign Run when enumeration risk exists. No upstream Core/GLPI/Twin/Copilot fetch until positive exact-scope ACL.
- Tests: fake disposable IdP/JWKS with signature/key rotation/alg confusion/issuer/audience/clock/groups; cross-tenant and forged Run/ticket; N1/N2/N3/manager GLPI permission matrix; stale/UNKNOWN, API failures, CSP/no-store, JS races and ephemeral browser navigation. No real GLPI mutation.

## Operational and rollback

`cryptography==46.0.4` is pinned in the Portal image and `app/portal/requirements-oidc-ci.txt`. The Portal-owned quality bridge installs this exact version explicitly with pip before OIDC suites; the RSA fixture **must pass, never SKIP**. The shared Quality workflow remains architect-owned and unchanged. Portal image build is separately unqualified.

Revert the Portal-only PR commits to remove the new verifier/preflight and restore previous code; no database, migration, workflow, GLPI or external state is touched. No deployment or LIVE permission is granted.

## OIDC HTTP contract, limitations and security gate (2026-11-01)

- `GET /auth/oidc/login`: fixed issuer-origin authorization endpoint, authorization code + PKCE S256, random state/nonce and short-lived server-only transaction. A `__Host-` state cookie binds the callback; no browser token becomes authority.
- `GET /auth/oidc/callback`: state/cookie comparison and one-time consumption **before token exchange**; pinned HTTPS token endpoint without ambient proxy/redirect; real RSA/JWKS, issuer, audience, nonce, exp/nbf/iat, tenant-group mapping. Failure 401 or 503 UNKNOWN; no business fetch.
- `GET /api/portal/session`: 401 for missing/revoked session, 503 UNKNOWN for verified identity without Core ACL. Does not expose subject, tenant, roles or Run.
- `POST /auth/oidc/logout`: exact portal Origin required; revoke opaque cookie; 403 for cross-origin attempt. This does not mutate GLPI or Core.
- Server-side session/state store is **in-memory, per-process and non-durable**; restart, another worker or eviction fails closed. No load-balanced session sharing or revocation propagation. This is **not production-ready**. Before any positive ACL, require external shared revocable store with atomic consume, key rotation, session invalidation and CSRF threat-model review. The callback is not wired to authorize Run/NOC/Copilot/GLPI data.
- Pinned configuration: `AIOPS_PORTAL_OIDC_ISSUER`, `AIOPS_PORTAL_OIDC_AUTHORIZATION_ENDPOINT`, `AIOPS_PORTAL_OIDC_TOKEN_ENDPOINT`, `AIOPS_PORTAL_OIDC_REDIRECT_URI`, `AIOPS_PORTAL_OIDC_CLIENT_ID`, `AIOPS_PORTAL_OIDC_AUDIENCE`, `AIOPS_PORTAL_OIDC_JWKS_JSON`, explicit tenant/role group maps. Use test-only fake IdP/JWKS, never real credentials in Git.
- Core #233 provides an independent read-only xref design but synthetic ownership proofs are **not** GLPI/IdP attestation. Core must supply an actor-bound delegation and exact tenant+Run+ticket+entity permission decision before Portal can call it. Until then `RELEASE_STABLE=NO_GO`, no CONNECTED or GLPI actions.

**Rollback:** revert the scoped Portal commits (or close the PR); ephemeral state disappears on process exit. No schema migration, shared workflow change, real GLPI write, SSH or LIVE.

## Portal P0 Core ACL consumer delta — 2026-11-01

- `portal.core_acl_consumer.consume_run_acl` is wired into the existing `GET /api/portal/runs/{rid}` and `GET /runs/{rid}` routes for **server-held OIDC sessions only**. No browser bearer, `X-Actor-ID`, `X-Tenant-ID`, `X-GLPI-Profile` or URL-supplied tenant is used as identity. Existing viewer bearer path stays fail-closed.
- Session lookup is through the existing opaque, revocable, in-memory store; expired, revoked, replayed or absent sessions cannot access Run data. A valid session still yields the same `503 UNKNOWN / TENANT_ACL_NOT_QUALIFIED` for present, absent, foreign, forged or syntactically invalid Run IDs. No Run lookup or GLPI/Core/Twin fetch occurs.
- `configured_core_target` requires a pinned HTTPS origin (no userinfo, path, query, fragment, alternate port), a dedicated 32–256 character printable service token distinct from viewer/operator/internal tokens and exact declared scope `itsm:xref:read`. This is a **configuration preflight**, not a network client; no secret is returned to the browser or logged. The token's actual Core permission remains a Core-owned check.
- `ServerXref` is an internal-only exact binding of tenant, Run, Incident, GLPI instance, ticket and entity. `positive_core_contract_matches` rejects the current Core `aiops.core-itsm-xref-read.v1` `VERIFIED` response as actor authorization. A future positive contract must bind the verified OIDC subject, all exact resource IDs, permission, ACL version, expiry and independently authenticated GLPI ownership. Even a synthetic future-shaped envelope does **not** enable reads in this revision.
- **Core #233 dependency:** define a distinct authenticated subject-delegation mechanism and a Core-authoritative `aiops.core-actor-resource-authorization.v1` endpoint, with independent GLPI/CMDB ownership evidence (not merely a signed synthetic fixture). Core must authorize actor + tenant + exact Run → Incident → ticket + entity, and provide replay/expiry/revocation semantics. Until Core and GLPI attestation are independently tested, no positive ACL or CONNECTED state is permitted.
- Disposable negative tests are in `tests/test_portal_core_acl_consumer.py`, executed via the existing Portal-owned Quality bridge `tests/test_portal_demo_command_auth.py`. Shared `.github/workflows/quality.yml` is unchanged. No real IdP, GLPI API, production network or mutations.
- Rollback: revert the focused Portal-only commits; no schema, persistent state, external session or GLPI mutation to undo. `RELEASE_STABLE=NO_GO`.

## Proposed Core actor-resource authorization v1 — Portal P0 next gate (2026-11-01)

**Contract proposal, not an implemented Core endpoint or positive authorization.**
Core #233/#242 currently expose `aiops.core-itsm-xref-read.v1`, a
service-authorized xref with disposable GLPI readback tests. They do **not**
provide an OIDC-subject-delegated actor ACL, native GLPI actor permission,
or independently sourced Run↔Ticket ownership. A `VERIFIED` xref, HMAC,
DB flag or synthetic GLPI response is insufficient.

Portal's `core_v1_envelope_matches` validates only a proposed **closed**
`aiops.core-actor-resource-authorization.v1` response shape. Required:
`decision=ALLOW`, `permission=run:read`, `tenant_acl_qualified=true`,
`acl_version=vN`, opaque `decision_id`, exact actor subject/issuer/audience,
tenant, Run, Incident, GLPI instance/ticket/entity and a server-created
one-time `request_nonce`. Integer `issued_at`, `expires_at`,
`revocation_checked_at` must be recent (60/60/30 seconds respectively),
non-revoked and bounded by the live OIDC identity expiry. `delegation`
must name Core-verified subject, issuer, audience, tenant, expiry and
revocation; `glpi_readback` must attest authenticated independent ticket
ownership, exact entity, native actor `ticket:read` permission and a
separately proven Run↔Ticket link. Extra/missing fields, cross-tenant
identifiers, stale/forged/replayed nonce, wrong subject/issuer/audience,
false ownership or revoked/expired proofs are rejected.

**Important:** an attacker can construct a syntactically matching JSON.
The shape validator is NOT an ACL verifier. The historical
`positive_core_contract_matches` is deliberately hard-closed (always
false), and `consume_run_acl` still returns 503 UNKNOWN without network.
No flag/environment variable can turn on a positive read. The separate
`configured_core_authz_target` only checks pinned HTTPS origin and
`actor:resource:authorize` service token distinct from the xref token,
viewer token, operator token and internal token; it performs no request.
Never forward browser bearer or actor/tenant/profile headers to Core.

**Core-owner acceptance required before activation:** publish a versioned
Core endpoint with server-authenticated OIDC subject delegation (not
arbitrary request headers), bounded one-time challenge and replay store,
Core-side authorization of exact Run→Incident→ticket/entity, independently
authenticated GLPI ownership **and native actor permission**, expiry,
revocation and response authenticity. Agree on the wire schema, status
codes and Core-signed or pinned mTLS/service transport, and prove negative
cross-tenant/absent/foreign indistinguishability. Portal will then need
an architect-reviewed network client that authenticates the response,
atomically consumes the challenge, rechecks session revocation, and only
then performs resource reads. Until then: no upstream fetch, no CONNECTED,
no GLPI action, no positive role grant.

**Tests:** `python -m unittest discover -s tests -p
'test_portal_core_acl_consumer.py' -v` (disposable sessions, no network).
API and HTML must agree for present/absent/foreign/forged Runs; expired,
revoked and replayed cookies are 401, valid identity without ACL is 503
UNKNOWN. CSP, no-store and no-business-ID disclosure are asserted.
The existing Chromium synthetic suite is not proof of a real GLPI/IdP.
No shared Quality workflow or Core/Worker/Evidence file is changed.

**Rollback:** revert this Portal-only PR (consumer/test/contract) or close
it; no Core request, persistent state, GLPI mutation, migration, deployment
or LIVE side effect was created. `RELEASE_STABLE=NO_GO`.
