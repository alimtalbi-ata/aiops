# Operator identity and tenant authorization

Status: proposed, not enabled. No new browser permissions.

## Identity boundary

Use a configured OIDC issuer with authorization code + PKCE, state and nonce.
Validate issuer, audience, signature, expiration and nonce using a maintained OIDC library.
Map issuer + subject to a server-managed operator record and tenant memberships.
Never trust tenant or role supplied by a browser, shared bearer, or signed NOC source.
Provider selection and membership schema require deployment-owner approval.

## Session boundary

Use opaque random session identifiers, server-side storage, Secure/HttpOnly/SameSite cookies,
rotation at login and privilege changes, bounded idle and absolute expiry, logout revocation.
Re-evaluate membership on each protected read. Do not store provider access tokens in browser storage.
Require CSRF protection for state-changing routes; no LIVE privileges granted by read sessions.

## Incident read gate

Core must enforce tenant predicates before returning list or detail results.
Portal must derive the active tenant from verified membership and apply incident_read_policy.
Unknown authority returns a constant unavailable response; unauthorized resource identifiers must
not become existence or timing oracles. Pagination, filters and totals must be tenant scoped.
Log subject, tenant, action and outcome without tokens or evidence contents.

## Acceptance gates

- Missing, expired, wrong-issuer and wrong-audience identity denied.
- Session fixation, replay after logout and CSRF tests.
- Cross-tenant IDs, list filters, counts and pagination leak no data.
- Membership removal invalidates subsequent reads.
- Existing shared bearer routes remain fail closed until migration qualifies.
- Real browser and identity provider integration tests before deployment.

No provider, credentials, session store or Core list endpoint is configured by this document.
