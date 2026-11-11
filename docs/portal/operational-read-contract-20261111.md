# Portal operational read-only contract — candidate, 2026-11-11

Scope: client-side presentation of Runs / Evidence / incidents. This document does **not** certify server authorization or activate routes.

## Required server boundary
- Derive authenticated actor and tenant from a validated server session, never request body, query, browser storage, or client-provided headers.
- Enforce per-record tenant authorization before serialization; strip credentials, transport headers, diagnostic URLs, unapproved record fields and cross-tenant data **on the server**.
- Return a projection with own data fields `scope_verified: true`, `authorization_source: "server"`, `observed_at` (ISO timestamp), `records` (array). These markers are a UI display guard, **not proof** of authorization.
- Record source, collection timestamp and authorized tenant/actor in server-side audit evidence; do not expose secrets in UI. Any missing/expired evidence, unknown tenant, 401/403, or unqualified scope must not display records.

## Client terminal states
- `READY`: fresh, qualified nonempty records. `EMPTY`: fresh, qualified empty records.
- `UNKNOWN`: missing/unqualified/future/stale observations, local timeout, cancellation. Never turn into OK.
- `ERROR / READ_FAILED`: transport/descriptor exception. Do not expose exception strings.
- Superseded or cancelled requests must not publish late success. Timeout is recognized by a private marker, not exception text.
- Configured `maxAgeMs` must be a safe integer 1..86400000 (default 180000). `timeoutMs` 1..120000 (default 15000).

## Negative test / controlled recipe
Run `node --test app/portal/components/operational_state.test.mjs app/portal/components/operational_state_contract_negative.test.mjs` at the exact candidate SHA. Exercise 401/403, missing tenant/actor, foreign tenant record, invalid provenance, expired/future time, descriptor getter/proxy failure, timeout spoofing, late response after cancellation and error sanitization. Confirm browser displays UNKNOWN/ERROR with null data; verify no secret persists or leaks.

## Release gates / handoff
Coordinate with issue #555 and PR #545. This test-only increment is stacked on #569 (#566 → #562 → #558 → #550 → #547); do not integrate before independent server ACL review and exact-SHA CI. Keep bootstrap/components/copilot/demo blocked by `TENANT_ACL_NOT_QUALIFIED`. Debian HOLD #557: no deploy, merge, live remediation, external DNS, Core/Worker/Twin, Policy/HITL, GLPI, PG, cron, or stack changes. Rollback: omit this candidate PR or revert its isolated test/document commits.
