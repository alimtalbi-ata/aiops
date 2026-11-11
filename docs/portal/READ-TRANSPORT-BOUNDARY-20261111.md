# Portal Runs/Evidence read-only transport boundary — 2026-11-11

Scope: additive contract and negative tests only, stacked on PR #601 and the #547 → #550 timeout/cancellation chain. Not wired to live Portal routes.

## Trust boundary
- `projectReadTransportFailure` is a *diagnostic projection*, not an authentication, authorization, freshness, or data-read adapter.
- HTTP status must be supplied by a trusted server-side fetch adapter from `Response.status`, never JSON, query parameters, exception strings, local storage, or browser actor/tenant claims.
- Abort and timeout flags must be derived from the trusted request lifecycle, not arbitrary caller payloads. The pure projection alone cannot authenticate these flags.
- Server must derive actor and tenant from authenticated context, verify tenant ACL, bind source/provenance and observation timestamp, and apply a freshness gate before a separate read model can be `READY`.
- Missing, stale, inconsistent, or unqualified data => `UNKNOWN`, `result:null`; transport failures => explicit sanitized `ERROR`. Never infer `READY` from HTTP 2xx.
- 401 => `UNKNOWN/AUTH_REQUIRED`; 403 => `UNKNOWN/TENANT_ACL_NOT_QUALIFIED`; cancellation outranks timeout only when trusted lifecycle evidence is available. Ignore late responses after supersession.
- Do not reactivate bootstrap/components/copilot/demo routes while `TENANT_ACL_NOT_QUALIFIED`; do not persist browser secrets.

## Test and integration gate
`node --test app/portal/components/read_transport_diagnostics.test.mjs app/portal/components/read_transport_boundary_contract.test.mjs`

Negative tests: 2xx/3xx never READY, forged truthy flags, invalid status, hostile payload getter, Proxy descriptor exception. Existing tests cover 401/403, cancellation, timeout, and secret suppression.

Controlled isolated recipe (not executed): pin candidate SHA; verify CI at exact SHA; confirm server-side actor/tenant and source ACL; replay 401/403, cross-tenant, stale/unknown provenance, timeout, cancellation, superseded late response, 404/429/5xx, and no secret persistence. Verify no external DNS, no writes/remediation. Document E2E results separately; never infer Debian qualification from CI.

Dependencies: #547, #550, #601, integration issue #555, handover PR #545. Debian release hold #557 and credential P0 #535 remain blocking. No merge, deploy, runtime, cron, GLPI, PG, Policy/HITL, Core/Worker/Twin, or Debian changes.

Rollback: drop this branch / revert its two additive commits; existing Portal behavior unchanged.
