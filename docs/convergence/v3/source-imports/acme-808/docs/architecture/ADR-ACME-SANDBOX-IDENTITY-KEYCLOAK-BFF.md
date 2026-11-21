# ADR — ACME sandbox viewer identity and authorization

**Decision:** ACCEPTED AS TARGET ARCHITECTURE (source-only). **Runtime state:** NOT DEPLOYED / NO_GO.
**Scope:** AIOPS2 ACME synthetic sandbox only; not LIVE, not a new application.

## Choice and rationale

Use a dedicated **Keycloak OIDC realm for the disposable ACME sandbox**, with the existing Portal as a **confidential backend-for-frontend (BFF)**. Keycloak is the default implementation choice because it is self-hostable, standards-based and can be tested without dependence on a corporate SSO tenant. This is a target choice, **not evidence that Keycloak is installed**. A corporate standards-compliant OIDC IdP may replace Keycloak later without changing the server-side authorization contract. Do not deploy Keycloak on the existing Debian/LIVE host.

**Identity != authorization.** Keycloak establishes the actor; it does **not** grant access to arbitrary AIOPS2 tenant/run records. AIOPS2 owns both authorization decisions.

## Trust boundaries

1. Browser -> Portal: OIDC Authorization Code + PKCE, confidential client, exact redirect URI, TLS, state/nonce and CSRF checks. Portal validates issuer, audience/client ID, signature via pinned issuer JWKS, expiry/not-before, nonce and key rotation. Fail closed on discovery/JWKS failures. No implicit flow, password grant, bearer in URLs or browser storage.
2. Portal session: opaque, server-side, rotating session ID in Secure/HttpOnly/SameSite cookie, short idle/absolute expiry, logout revocation. Store token material only server-side; never log or return it. Require CSRF protection on state-changing operations.
3. Portal -> tenant authorization: use an authoritative **server-managed actor-to-tenant grant store** keyed by immutable (issuer, subject), not email, UI-supplied roles, ID token groups or browser claims. Default deny; explicit grant for ACME-TEST only. Audit grants and revocations.
4. Portal -> exact run authorization: require an authoritative **server-managed actor-to-run grant** for the canonical Core run ID AND tenant. A tenant membership alone is insufficient. Resolve attempt_id -> (tenant_id, run_id) from the **Core persisted ACME sandbox mapping**, never a caller-supplied or SHA-derived guess. Deny before any evidence read.
5. Portal -> Core/Worker: only after both grants, use **server-held service credentials** for read-only GET. Never forward OIDC tokens or internal service bearers to the browser. Verify Core canonical binding and Worker no-effect receipt/digest; redact all upstream failures. No POST/GLPI/Temporal workflow start.
6. Browser response: render only a minimal synthetic, redacted view. Distinguish authenticated, authorized, evidence consistent, and runtime attested. Never infer production authority from sandbox receipts.

## API/error behavior

- Anonymous or expired session: **401**.
- Authenticated actor without tenant grant: **403**.
- Missing exact-run grant, missing run or mismatched attempt/run: **404**, indistinguishable externally to prevent run enumeration.
- IdP, grant store, Core or Worker unavailable/inconsistent: **503** and no evidence; do not downgrade to a local boolean.
- Never use `ViewerDecision(status=200)` or `identity_authority_qualified=True` as proof: the existing `scripts/acme_viewer_access_policy.py` and `scripts/acme_evidence_read_seam.py` are offline-only and caller-forgeable. Do not wire them directly into Portal HTTP.

## Implementation order / acceptance gates

1. **Source-only:** implement a separate server-side identity adapter and authorization provider interface, explicit no-provider fail-closed default, plus tests. No Portal route until a real provider exists.
2. **Disposable sandbox (separate approval):** provision Keycloak with non-production realm, test users and HTTPS; configure confidential Portal client and server-side session; do not check in credentials, keys or exported user records.
3. **Server-side grants:** deploy auditable actor→tenant and actor→exact-run grants with revocation, least privilege and isolation. Bind Core persisted attempt/run/tenant before Worker read.
4. **Negative security tests:** anonymous 401; cross-tenant 403; ungranted/mismatched run 404; expired/revoked token, bad issuer/audience/signature/nonce, JWKS outage, grant store outage 503 or 401 as appropriate; prove **zero Core/Worker calls** on every denial. Concurrent-session isolation and token leakage checks.
5. **Runtime qualification:** isolated browser tests for all seven ACME scenes, source-backed SAN P1→Payments P2 join, verified deployed SHA/image, zero external writes, private screenshots/manifest. No runtime GO until all P0 gates pass.

## Rejected alternatives

- **Portal internal bearer as viewer ACL:** service identity is not human identity.
- **Trusting Keycloak groups/claims as exact-run ACL:** tokens are not authoritative for mutable Core run ownership or revocation.
- **Exposing offline policy/read seam through HTTP:** caller-supplied flags/decisions can be forged.
- **Building a separate ACME demo application:** duplicates AIOPS2 and obscures source provenance.
- **Automatically installing Keycloak on LIVE Debian:** unsafe and outside the authorized scope.

## Status

This ADR authorizes a **design choice and source-only work**, not infrastructure creation, access grants, a merge or deployment. Until the IdP, grants and browser/runtime evidence are independently verified: **OIDC_AUTHORITY_NOT_RUNTIME_VERIFIED / TENANT_ACL_NOT_QUALIFIED / LIVE_NO_GO**.
