# Runs/Evidence read-only transport invariants — 2026-11-11

## Scope and trust boundary
Additional negative tests for the pure diagnostic projector; no runtime wiring or live read. The status must originate from a trusted Response.status adapter. Boolean abort/timeout flags must originate from a trusted controller, not request JSON. Actor and tenant must be derived and authorized server-side before reading any records. Browser actor/tenant assertions never qualify access.

## Contract
- Every integer HTTP status 100–599 yields a frozen, sanitized UNKNOWN or ERROR with result:null; never READY.
- Noninteger, malformed or out-of-range statuses without trusted abort/timeout yield ERROR/READ_FAILED/result:null.
- Hostile Proxy property descriptors fail closed; no raw exception or payload leakage.
- Client-provided provenance, observed_at, state, authorization and records are ignored by this diagnostic. They cannot qualify freshness or grant access.
- This diagnostic is **not** a complete read model: actual provenance and observed_at must be independently server-qualified, and absent or stale values remain UNKNOWN. No browser secret persistence.

## Verification commands (not executed here)
`node --test app/portal/components/read_transport_invariants.test.mjs app/portal/components/read_transport_negative_matrix.test.mjs app/portal/components/read_transport_boundary_contract.test.mjs app/portal/components/operational_state.test.mjs`

## Minimal candidate and isolated acceptance recipe (NOT EXECUTED)
Only after review and explicit authorization, build a minimal Portal-only candidate atop the approved #547 -> #550 timeout/cancel/transport chain and review #545 handover through #555. In an isolated, non-live test fixture verify: 401/403 and cross-tenant denial, 404/429, timeout versus cancel precedence, delayed superseded responses, forged timeout messages, 2xx without freshness/provenance, stale timestamps, malformed Proxy descriptors, 404/405 security headers and navigation supersession. Require server-side actor/tenant evidence, explicit UNKNOWN/error states, no leaked records, and CI at exact final SHA. Do not activate bootstrap/components/copilot/demo while TENANT_ACL_NOT_QUALIFIED.

## Handoff and rollback
Base PR #610 at 7cb03b8aee4ef234c7a7b0343563d74dbfd986c8; integration issue #555 and handover PR #545. Independent review required. Rollback is to drop this draft branch; tests and documentation only. No merge, deployment, Debian stack, Core/Worker/Twin, cron, GLPI, PG, Policy/HITL, runtime mutation or external DNS.
