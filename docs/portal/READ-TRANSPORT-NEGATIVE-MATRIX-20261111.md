# Portal read-only transport diagnostic: negative matrix (2026-11-11)

Scope: Runs/Evidence diagnostic projection only. This change adds contract tests, not a live adapter, route, or runtime modification.

## Contract
- The trusted server/fetch boundary must derive HTTP status from Response.status; neither JSON, error messages, browser-supplied flags, nor actor/tenant claims are authorization evidence.
- Actor/tenant ACL must be derived and enforced server-side before any read model becomes visible.
- 401 -> UNKNOWN/AUTH_REQUIRED; 403 -> UNKNOWN/TENANT_ACL_NOT_QUALIFIED; 404 -> UNKNOWN/NOT_FOUND; 429 -> ERROR/RATE_LIMITED. All result:null.
- Invalid status, HTTP transport failures, hostile descriptors and forged flags -> ERROR/READ_FAILED/result:null.
- Only a trusted transport controller may set boolean aborted/timedOut. Cancellation precedes timeout. A transport diagnostic never returns READY.
- Provenance, observed_at freshness and payload qualification are **not** established by this projector; unverified freshness remains UNKNOWN. Do not persist browser secrets.

## Tests
`node --test app/portal/components/read_transport_negative_matrix.test.mjs app/portal/components/read_transport_boundary_contract.test.mjs`
Also run the existing `app/portal/components/operational_state.test.mjs` tests for #547 -> #550 regressions.

## Controlled recipe (NOT EXECUTED)
Use a separately authorized isolated candidate, never the live Debian stacks. With server-derived actor/tenant authorization, verify 401/403, cross-tenant denial, 404, 429, timeout, cancellation, delayed superseded response, transport error spoofing, missing/stale provenance and timestamp, and no payload/secret leakage. Verify 404/405 headers and navigation supersession across the consolidated Portal lot. Do not unblock bootstrap/components/copilot/demo under TENANT_ACL_NOT_QUALIFIED.

## Integration handoff
Stacked parent: PR #605 HEAD ef3f09a15d6386fb3a752f8190b0563d4aa6b802. Coordination: issue #555, PR #545, dependency #547 -> #550. No merge/deploy, Core/Worker/Twin, Debian, cron, GLPI, PG, Policy/HITL, external DNS or live mutation. Rollback: drop this draft branch/PR; it adds only tests and this document. CI and E2E must be checked at the exact final SHA; inherited CI is not sufficient.
