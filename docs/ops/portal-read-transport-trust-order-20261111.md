# Portal Runs/Evidence — trusted transport precedence (2026-11-11)

## Scope
Pure read-only diagnostic projector only. This branch adds negative tests and a controlled acceptance checklist; it does not wire any route, alter Core/Worker/Twin, touch Debian, or authorize a live read.

## Contract
- Only own **data** descriptors are accepted for `status`, `aborted`, and `timedOut`; inherited/accessor/Proxy values cannot qualify a diagnostic.
- Literal `aborted === true` takes precedence over `timedOut === true`. Other truthy flags do not qualify cancellation or timeout.
- HTTP 401 maps to `UNKNOWN/AUTH_REQUIRED`, 403 to `UNKNOWN/TENANT_ACL_NOT_QUALIFIED`, 404 to `UNKNOWN/NOT_FOUND`, 429 to `ERROR/RATE_LIMITED`; other valid HTTP statuses map to `ERROR/READ_FAILED`. All have `result:null`, are frozen, and never `READY`.
- Status and cancellation signals must come from trusted fetch Response/controller adapters, **not** browser JSON, request headers, exception text, or caller-provided identity. The pure projector alone cannot authenticate provenance.
- Actor/tenant authorization and `observed_at` freshness must be independently established server-side before any read model can be `READY`. Missing, stale or contradictory evidence stays UNKNOWN; no browser-persisted secret.

## Tests and controlled recipe
`node --test app/portal/components/read_transport_trust_order.test.mjs app/portal/components/read_transport_invariants.test.mjs app/portal/components/read_transport_negative_matrix.test.mjs app/portal/components/read_transport_boundary_contract.test.mjs app/portal/components/operational_state.test.mjs`

On a disposable synthetic fixture **only after independent review**, verify cross-tenant 403, 401, 404, 429, timeout/abort race, late superseded responses, spoofed transport messages, missing/stale provenance, and 404/405 security headers. Capture exact HEAD SHA, test exit code and CI conclusions. Do not use live tenants or secrets.

## Integration and rollback
Stacked on #614 (head `0c3de59b6688ba24616227d70c4b6d4a1f381e63`); trace #547 -> #550, integration issue #555 and handover #545. Keep Draft; do not merge or deploy. Rollback: discard this isolated branch/PR. `TENANT_ACL_NOT_QUALIFIED` routes remain blocked. DNS external prohibited; Docker internal DNS permitted.
