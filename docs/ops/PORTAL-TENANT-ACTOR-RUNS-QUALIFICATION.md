# Portal Runs: server-derived tenant/actor authorization gate

Status: **BLOCKED / NOT VERIFIED**. This is a qualification checklist, not a
declaration of deployed functionality. It accompanies draft PR #631 and the
consolidated UI candidate #629.

## Current facts

- Portal `GET /api/portal/bootstrap` checks the shared viewer bearer and
  intentionally returns HTTP 503 `TENANT_ACL_NOT_QUALIFIED`; it does not
  call Core or Twin.
- Core `GET /api/runs` returns up to 100 globally selected Runs and
  `GET /api/dashboard` aggregates global rows. Neither endpoint derives
  an actor or tenant from an authenticated server-side principal.
- The portal client refuses read-model envelopes without
  `tenant_acl_qualified=true` and `actor_identity_server_derived=true`.
  These client flags are **not themselves authorization evidence**.
- The 100-Run UI tests use synthetic envelopes, not Debian tenant data.

## Required positive contract (future implementation, not yet present)

1. Authenticate an actor from server-verified identity; do not trust
   browser-supplied tenant IDs, arbitrary headers, or a shared bearer alone.
2. Resolve authorized tenant scope on the server and enforce it at each
   Core/Twin data query. Deny absent, revoked, conflicting, or ambiguous scope.
3. Keep legacy global Core endpoints out of the browser tenant projection.
   Preserve existing command, HITL, and remediation gates unchanged.
4. Return a bounded, explicitly versioned, read-only portal envelope only
   after all upstream queries satisfy the same verified tenant/actor scope.
   Do not label an unverified source LIVE or runtime-authenticated.

## Acceptance matrix — all rows mandatory

| Case | Required result | Proof |
| --- | --- | --- |
| No bearer | 401; no upstream read | Portal HTTP integration |
| Invalid or revoked bearer | 401/403; no upstream read | Portal HTTP integration |
| Shared viewer bearer only | 503 `TENANT_ACL_NOT_QUALIFIED` | Existing regression |
| Forged tenant header or body | No scope elevation or cross-tenant rows | Auth integration |
| Actor A, tenant A | Only authorized A rows and counts | Seeded DB/API integration |
| Actor B, tenant B | Only authorized B rows and counts | Seeded DB/API integration |
| Actor A requests B run ID | 403 or 404; no B identifiers in response | Negative cross-tenant test |
| Actor with revoked membership | Deny and no stale cached rows | Revocation test |
| Missing or contradictory upstream scope | UNKNOWN/503; no partial disclosure | Failure-injection test |
| 0, 15, 17, 100 permitted Runs | All permitted bounded rows visible | Browser DOM tests |
| 101 rows or malformed envelope | UNKNOWN; no partial rows | Browser fail-closed test |
| Backend unavailable | UNKNOWN/503, no LIVE claim | Runtime failure test |
| Command or remediation attempted | Existing HITL/ACL unchanged | Command authorization regression |

## Debian qualification after CI

Use **rootless Docker as `aiops`** on `SRV-DEB-05`; never use
`sudo docker` as a proxy for the rootless daemon. Confirm deployed SHA and
the actual portal/Core image digests first. Execute only approved read-only
HTTP and tenant test fixtures; do not change production tenant data, Docker
data-root, containers, or the dirty deployment checkout. Record redacted
HTTP statuses, authorized vs denied counts, and deployed SHA in the
qualification issue. No merge or deployment is implied by green CI.
