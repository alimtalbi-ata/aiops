# Portal P0 — authenticated Core actor-resource v1 transport preflight

**Status:** SOURCE_ONLY / FAIL_CLOSED / NO DISPATCH. Owner: Portal. Base: architect's sole Draft #234. This is a proposed transport, **not** a Core response contract agreed by its owner and not a positive ACL. Existing Core #246 always returns UNKNOWN. No production IdP/GLPI connection.

## Wire proposal to Core owner (#246) and architect (#234)

- The server obtains `PortalActorContext` only from the OIDC RS256/JWKS callback and its opaque revocable session. Browser bearer, actor/tenant headers, GLPI profile and query/body claims are not accepted as authority. Session revocation/expiry is checked by existing Run API/HTML before this offline preflight.
- `prepare_core_authz_wire` requires exact server-owned `ServerXref`: tenant, Run, Incident, GLPI instance, ticket, entity. It requires `AIOPS_PORTAL_CORE_AUTHZ_ORIGIN` to be pinned HTTPS, a dedicated server-held `actor:resource:authorize` bearer distinct from XREF/viewer/operator/internal tokens, and an unexpired OIDC identity. It constructs a canonical POST body containing exact resource IDs, `run:read` and a fresh cryptographic request nonce.
- Target Core route: `POST /api/tenants/{tenant_id}/runs/{run_id}/actor-resource-authorization`, with `Authorization: Bearer <scoped server token>`. No browser bearer or actor/tenant header is forwarded. Core #246 additionally requires `X-Actor-Delegation` obtained from a separately authenticated issuer; Portal does **not** mint or forward one because the delegated token flow is unqualified.
- The request plan is **not executable**: `dispatch_allowed=False`; there is no HTTP client, Core/GLPI fetch or API route wiring. A forged ALLOW must never enable an upstream read.
- Offline response-authenticity proposal: provision an operator-pinned Core **public** RSA JWKS via `AIOPS_PORTAL_CORE_AUTHZ_RESPONSE_JWKS_JSON` (no dynamic `jku`/`x5u`). Verify RS256 over UTF-8 bytes `aiops.portal.core-actor-resource-authorization.v1\n` + pinned Core origin + `\n` + canonical JSON body (sorted keys, compact separators). Detached signature envelope: `{alg:"RS256",kid:"...",signature:"<base64url>"}`. Verify exact request nonce, actor issuer/audience/subject, tenant, Run, Incident, GLPI instance/ticket/entity, permission, expiry/revocation and claimed independent readback with existing strict shape checker. **Signature verification alone is not authorization** and this format requires Core-owner agreement.
- `core_authz_read_permitted` and the historical `positive_core_contract_matches` remain hard-coded false. No session-derived read model or CONNECTED state is enabled. Uniform `503 UNKNOWN` for absent/foreign/forged/unqualified Runs; missing/revoked/expired sessions are 401. No Run existence oracle.

## Blockers to any positive path

Core must publish and test real issuer-authenticated, resource-bound subject delegation, native GLPI actor/profile/entity `ticket:read` permission, independent GLPI ticket/Run ownership and identity mapping, durable atomic nonce/replay and revocation ledger, and a mutually agreed signed-response format with key rotation. A pinned service token, Core HMAC xref, signed synthetic fixture, claimed `verified=true`, GLPI service readback or Portal N1/N2/N3/manager role is **not** sufficient. Response authenticity also requires a qualified key provisioning/rotation process. No response is consumed as an ACL until a separate architect-reviewed activation PR.

## Tests, evidence, rollback

Portal-owned `tests/test_portal_core_acl_consumer.py` extends the existing Quality bridge. Run:
`python -m unittest discover -s tests -p 'test_portal_core_acl_consumer.py' -v`.
Adversarial cases cover unpinned origins/shared tokens, cross-tenant and forged resources, expired identity, valid fake RSA-signed ALLOW with no grant, forged/altered signatures, wrong origin/key, replayed nonce, revoked session, API/HTML uniform UNKNOWN and no upstream. Disposable RSA private key is generated only in test memory. Browser/Chromium existing synthetic checks remain a separate qualification and do not attest GLPI.

**Rollback:** revert the Portal-only PR commits or close the Draft. No Core/Worker/Evidence/shared Quality changes, migration, network action, GLPI write, deployment, SSH, sudo or LIVE. `RELEASE_STABLE=NO_GO`.


## Exact Core v1 reconciliation — 2026-11-01, offline only

Source reviewed against `app/core/actor_resource_authz.py` in the architect's
candidate. Core's actual route is
`POST /api/tenants/{tenant_id}/runs/{run_id}/actor-resource-authorization`,
mounted on the existing ITSM xref router. The request JSON has **exactly**
`incident_id`, `glpi_instance_id`, `ticket_id`, `glpi_entity_id`,
`permission=run:read`, `nonce`. Portal's preflight emits that shape with a
pinned HTTPS origin and a separate service bearer; **it does not send**
`X-Actor-Delegation`. Core requires that header to contain a separately
issuer-authenticated, opaque, short-lived IdP access token with exact resource
grants. The Portal OIDC ID token/session, its `sub`, roles and browser claims
are **not** interchangeable with this Core-audience delegation.

Core's current reply is **not signed** and carries only
`{"schema":"aiops.core-actor-resource-authorization.v1","decision":"UNKNOWN"}`
for 200/503 (also 401 UNKNOWN), or `decision=UNAUTHORIZED` for 403.
Its response headers include `no-store`, `no-cache`, `nosniff` and
`no-referrer`; 401 also advertises `WWW-Authenticate: Bearer`.
There is **no** actor issuer/audience, tenant/Run/Incident/ticket/entity proof,
nonce echo, signature or native GLPI actor authorization in that reply.
`core_v1_current_unknown_reply_matches` is a strict *negative-only*
compatibility check, not a response signature verifier or ACL. Extra fields,
forged ALLOW, incorrect status/headers and any purported CONNECTED status are
rejected. No HTTP transport is implemented or invoked.

The detached RS256 envelope described above is a **future proposal**, not the
wire response currently implemented by Core. Its test-only signature may
authenticate a synthetic payload, but cannot establish a Core-issued decision,
replay prevention, native GLPI human permission or a positive Portal read.
The Core IdP introspection audience may differ from the Portal OIDC audience;
a Core-owner-defined subject mapping and signed-response issuer/key rotation
contract are required before any activation.

The Portal-owned regression suite now invokes the *actual Core router* with
disposable mocked service auth and introspection to assert its current
200/401/403 negative response and exact resource/nonce request, plus forged
foreign IDs, ALLOW, replay-looking extra fields, revoked/expired sessions and
uniform API/HTML 503 with zero business upstream calls. The Core router is
read-only in these tests: no real IdP, GLPI, PostgreSQL or external HTTP.
Run `python -m unittest discover -s tests -p 'test_portal_core_acl_consumer.py' -v`
under the existing Quality environment. Core remains the owner of route,
introspection, native GLPI rights, nonce/revocation ledger and eventual signed
response contract. **dispatch_allowed=false**,
**core_authz_read_permitted=false**, **RELEASE_STABLE=NO_GO**.
