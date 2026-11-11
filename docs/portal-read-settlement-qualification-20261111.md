# Runs/Evidence settlement qualification — 2026-11-11

Scope: read-only Portal helper, stacked on #648 (chain #547 → #550); no live integration. projectReadSettlement is a failure-only projection, not an authentication, authorization, freshness, provenance or readiness oracle.

## Trust boundary
- generation and activeGeneration MUST be issued and compared by a trusted server-side read adapter, never copied from browser/request payloads. Own data properties only; no accessors/prototype values.
- Actor identity and tenant scope MUST be derived server-side from authenticated context and independently authorized before any business read. Deny 401/403, cross-tenant, missing qualification. TENANT_ACL_NOT_QUALIFIED routes stay disabled.
- Transport status, cancellation, timeout, response generation and provenance MUST originate from trusted adapters. Client-supplied status/ready/tenant/observedAt are untrusted.
- An HTTP 2xx/3xx or settled promise does NOT establish readiness. Only an independently authorized, provenance-checked, fresh read model may be presented; this helper NEVER returns READY or data.
- Record source, observedAt, retrieval time and freshness policy server-side. Missing, stale or contradictory evidence => UNKNOWN; malformed or hostile trusted-envelope input => ERROR/READ_FAILED; never synthetic OK.
- Keep errors sanitized and explicit, no raw exceptions, secrets, persisted browser credentials or mutable business payload.

## Failure ordering
1. Reject invalid/untrusted generation envelope as ERROR/READ_FAILED.
2. Superseded generation => UNKNOWN/STALE_RESPONSE before touching terminal fields.
3. Current generation: both terminal flags MUST be own booleans; malformed/missing => ERROR/READ_FAILED.
4. Valid flags: CANCELLED > TIMEOUT > NOT_QUALIFIED, always result:null.
5. A later response cannot overwrite an active generation in the integration adapter.

## Negative qualification and controlled recipe (not executed)
At the exact HEAD, run:
node --test app/portal/components/read_settlement_guard.test.mjs app/portal/components/read_settlement_stale_first.test.mjs app/portal/components/read_settlement_qualification.test.mjs
Then run existing transport diagnostic tests and check all GitHub CI workflows at the exact SHA. Isolated server-backed recipe: 401/403, cross-tenant, 404/429/5xx, timeout vs cancellation, late responses, malformed/hostile descriptors and Proxy, forged ready/tenant/status/freshness, missing provenance, expired evidence, empty data, no browser secrets. Verify no calls to remediation endpoints. DNS external forbidden; Docker internal DNS only where permitted.

## Integration / rollback
Coordinate with #555 and #545. #555 has an independent integration branch; avoid modifying its shared files. Review the #648 stacked dependencies and actual integration points before selective extraction. No Core/Worker/Twin, Debian, GLPI, PG, Policy/HITL, cron or runtime modifications. Do not merge or deploy. Rollback: discard this isolated Draft/test-only branch; retain parent #648. CODE is only proposed until reviewed, CI and E2E independent; Debian #557 HOLD.
