# Runs/Evidence transport diagnostics — no success promotion

Scope: isolated Portal read-only diagnostic helper, following #547 → #550 and #634. This helper **never** authorizes a request, returns evidence, or establishes a read model's READY state.

## Contract
- Only a trusted server-side fetch adapter may provide HTTP status and terminal cancellation/timeout signals. Do not trust browser fields, JSON body, headers asserted by a client, exception strings, or caller-provided actor/tenant.
- Actor/tenant authorization must be derived and enforced server-side before any read-model result is exposed. Missing or unqualified authorization stays UNKNOWN; bootstrap/components/copilot/demo remain blocked by TENANT_ACL_NOT_QUALIFIED.
- Successful HTTP 2xx and redirect 3xx are **not** proof of successful authorized data projection: this failure-only helper returns ERROR/READ_FAILED/result:null. A separate server-authorized projector must validate provenance, observed_at freshness, tenant scope, schema and budgets before any READY.
- Terminal precedence: validated booleans CANCELLED > TIMEOUT > HTTP. Malformed terminal flags, hostile property descriptors and malformed statuses fail closed as ERROR/READ_FAILED/result:null. 401 → UNKNOWN/AUTH_REQUIRED, 403 → UNKNOWN/TENANT_ACL_NOT_QUALIFIED, 404 → UNKNOWN/NOT_FOUND, 429 → ERROR/RATE_LIMITED.
- Diagnostics must be frozen, bounded, free of payload, tokens, raw errors, actor and tenant identifiers. No persistent browser secret.

## Negative verification
Run at the exact commit SHA:
`node --test app/portal/components/read_transport_diagnostics.test.mjs app/portal/components/read_transport_no_success_contract.test.mjs`

New tests check 200–399 non-promotion, hostile status getter and inherited/client body status rejection, and terminal short-circuit without leaking forged tenant/freshness/READY. Tests are added but not claimed executed.

## Controlled recipe / gates
1. Independently review #547→#550, #545 handover, #555, and SHA-specific CI; distinguish infrastructure failure from application failure.
2. In an isolated non-live harness, supply trusted transport events and separately server-derived actor/tenant authorization; check 401/403, cross-tenant denial, timeout, cancellation, late response suppression, transport failure, hostile descriptors and malformed flags.
3. Validate provenance, observed_at freshness, unknown/stale/missing source, and no READY promotion; confirm bootstrap/components/copilot/demo stay blocked absent qualified ACL.
4. Record evidence per case (expected/actual, SHA, CI URLs, reviewer, timestamps), with explicit CODE/CI/DEBIAN/E2E statuses. Do not deploy or merge; rollback is to discard the isolated draft branch.

No Core/Worker/Twin, Debian, runtime, cron, GLPI, PG, Policy/HITL, or live remediation changes. No external DNS.
