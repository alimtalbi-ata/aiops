# Portal P0 — server identity → Core xref contract (design gate)

**Status:** implementation preflight only; no positive ACL, no IdP runtime, no GLPI connection. **Source:** DEV candidate `integration/enterprise-slice-main-20261031-2230` at `ae7c3e5102b99a66bd7806d602146f1309a9749d`. This is not an integration attestation.

## Trust boundaries

1. A future Portal **server-side** authorization-code + PKCE callback exchanges the code directly with the configured OIDC issuer. Only the server receives the ID token; browser bearer, `X-Actor-ID`, `X-Tenant-ID`, `X-GLPI-Profile`, URL parameters, cookie values and submitted JSON are never accepted as identity or tenant authority.
2. `portal.oidc_identity.verify_server_oidc_assertion` verifies a **pinned, operator-provisioned** JWKS RSA RS256 signature and exact issuer, audience, subject, expiry, not-before, issue time, group mappings and unique tenant. No token-specified `jku`/`x5u` retrieval; no JWKS network request. Group mapping is explicit; it does not create GLPI rights.
3. An eventual server-side session must be bound to this verified subject, tenant and issuer using a revocable server-owned session record and secure/HttpOnly/SameSite cookie. **No session creation is implemented in this PR**. Old `aiops_portal_run_session` cookies are ignored and the dead HMAC issuer has been removed.
4. Portal must call a **Core actor+tenant authorization endpoint** for the exact requested Run and verified GLPI ticket/entity link, with a **separate service bearer** never forwarded from the browser. Core must return a positive, versioned ACL decision scoped to actor, tenant, Run, ticket, GLPI entity, permissions, expiry and source provenance before any other upstream fetch. The current `core_xref_preflight` never performs I/O or authorizes a read.
5. Until that contract and its negative tests are qualified, `/api/portal/runs/{rid}`, `/api/portal/run-session`, NOC, Copilot, cockpit and `/api/portal/itsm` stay fail-closed with UNKNOWN/503 after authentication. Absent, foreign and unqualified canonical Run IDs remain indistinguishable; no CONNECTED, Evidence, ticket, incident or tenant data.
6. The Portal has no ticket or CMDB authority. GLPI native profiles, entities, categories, forms, templates, plugins, SLA/OLA and business rules must be inspected through an authorized read-only connector before mapping permissions. N1/N2/N3/manager is a **display planning role**, not a grant to comment, assign or approve. All such controls stay disabled in DEMO; GLPI remains the ticket/CMDB source of truth.

## Core owner contract request

- Authenticated service-to-service xref endpoint (Core #229 is source candidate): actor subject and tenant must originate from a Core-verified server-side delegation, not from arbitrary Portal headers or URL/query/body claims.
- Positive result must bind `tenant_id`, `actor_subject`, `run_id`, `incident_id`, `ticket_id`, `glpi_instance_id`, `glpi_entity_id`, `permission`, `acl_version`, `authorized_at`, `expires_at`, `source` and `freshness`. Response must be signed or otherwise authenticated to the Portal service and reject mismatches.
- Denials must be no-leak: 401 unauthenticated, 403 known but forbidden only when safe, 503 UNKNOWN for unqualified/absent/foreign Run when enumeration risk exists. No upstream Core/GLPI/Twin/Copilot fetch until positive exact-scope ACL.
- Tests: fake disposable IdP/JWKS with signature/key rotation/alg confusion/issuer/audience/clock/groups; cross-tenant and forged Run/ticket; N1/N2/N3/manager GLPI permission matrix; stale/UNKNOWN, API failures, CSP/no-store, JS races and ephemeral browser navigation. No real GLPI mutation.

## Operational and rollback

`cryptography==46.0.4` is pinned **only in the Portal image**. The shared Quality job currently installs FastAPI/httpx/requests without this package; claim/contract tests run there and the real RSA fixture test may skip. Architect must add an explicit pinned crypto test dependency to CI before declaring RSA exact-head qualification. The Portal image itself must be built/tested separately before any promotion.

Revert the Portal-only PR commits to remove the new verifier/preflight and restore previous code; no database, migration, workflow, GLPI or external state is touched. No deployment or LIVE permission is granted.
