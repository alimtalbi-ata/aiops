# Portal operational-state integration — security contract (draft)

Status: **DESIGN ONLY / HOLD / NO_GO**. This document grants no permission to deploy or merge.

## Verified existing behavior

- `app/portal/main.py`: `GET /api/portal/bootstrap` aggregates Core and Twin via `shared.http.get_json`; it does not derive an authenticated human actor/tenant, validate scope, or provide an authoritative observation timestamp.
- `app/shared/http.py`: `get_json` uses a service-level internal bearer token and `X-AIOPS-Request: internal`. This is **service authentication**, not evidence of a browser user's tenant authorization.
- `app/portal/main.py`: `_get` converts upstream exceptions into `{status:'UNKNOWN',error_type:...}`; `/runs` and `/` render HTML server-side and do not call the new JS component.
- `app/portal/components/operational_state.mjs`: browser accepts only `scope_verified === true` and `authorization_source === 'server'` for READY/EMPTY; freshness requires `observed_at`.

## Preconditions for a new read-only projection

1. Identify an existing **trusted, server-verified identity source** for the requesting human actor and tenant, with documented authentication, tenant membership, and authorization policy. If none exists, **do not expose an operational projection**.
2. Authorize the actor to view the requested records *at the data source or trusted server boundary*, before serialization. Do not trust browser-provided tenant IDs, headers, query parameters, or `scope_verified` flags as authorization evidence.
3. Never equate the shared `AIOPS_INTERNAL_TOKEN` / service bearer with end-user authorization. Prevent cross-tenant results, including through caches and error messages.
4. Use an authoritative source observation timestamp (not the API response time). Missing/invalid/stale/future observation timestamps must fail closed to UNKNOWN.
5. Return a minimal envelope **only on successful authorization and scope verification**:

```json
{"records":[],"observed_at":"2026-11-10T16:24:00Z","scope_verified":true,"authorization_source":"server"}
```

The example is a schema illustration, **not real observation evidence**. An empty array means a *verified fresh empty result*, never an upstream failure. Deny anonymous and unauthorized access with 401/403, without tenant data or secret-bearing diagnostics. Do not generate `scope_verified:true` client-side or infer it from HTTP 200.

## Integration acceptance matrix (must be automated)

| Case | Expected outcome |
| --- | --- |
| Anonymous, expired session | 401, no records |
| Authenticated actor, wrong tenant | 403, no records |
| Service token without end-user identity | Denied / no projection |
| Unverified source scope | UNKNOWN, no result |
| Missing, invalid, stale or future `observed_at` | UNKNOWN |
| Fresh, scoped, nonempty data | READY |
| Fresh, scoped, empty data | EMPTY |
| Upstream failure | ERROR, sanitized diagnostic |
| Hung read | UNKNOWN timeout, abort signal |
| Rapid filter changes / late completion | Latest request only |
| Malicious HTML and secret-bearing error | Inert DOM text; no secret in rendered UI |
| Retry / assistive technology | Native keyboard button; correct live-region role |

## Required evidence before GO

- Unit tests for server-side actor/tenant authorization and source timestamp semantics.
- Integration test on the **actual portal route**, using mock authorized and unauthorized upstream responses, and Chromium acceptance of the rendered page.
- CI checks and Debian environment qualification, followed by explicit release authorization.

Keep PR #537, #539 and #540 in DRAFT. No merge, deployment, automation change, or Debian modification.

## Source audit: Core endpoints (verified on stacked branch)

- `app/core/main.py` `GET /api/runs`: `list_runs()` executes `select ... from aiops.runs order by created_at desc limit 100` without an actor/tenant filter in the handler and without an authorization dependency in its signature. This is a global run listing in the inspected implementation.
- `app/core/main.py` `GET /api/dashboard`: `dashboard()` aggregates counts from `aiops.runs`, `aiops.twin_nodes`, and `aiops.incidents` without actor/tenant predicates in the handler. These aggregates cannot be presented as tenant-qualified evidence.
- These observations describe the inspected handlers; they do not establish whether other infrastructure restricts reachability. Network restrictions or service-level bearer tokens do not, by themselves, establish end-user tenant scoping.
- **Do not expose these global responses as scoped user projections.** Identify and test an authoritative identity/tenant model and authorized data queries before introducing the proposed endpoint. If such a model is not available, retain UNKNOWN and HOLD.

## Identity-source audit (additional blocking finding)

- In the inspected `app/portal/main.py`, no authentication middleware, request-state identity, or per-route user/tenant dependency is defined. This does **not** exclude identity enforcement outside this file; an ingress or identity proxy would need separate proof and trusted-header handling tests.
- In `app/core/main.py`, the `auth(token)` helper checks a shared internal token. Several write routes call it; this establishes a service credential check, not an independently verified human identity or tenant membership.
- `record_proposal_approval` reads `actor_id` and `actor_role` from the request payload after the internal-token check. Those values must **not** be reused as authenticated browser identity for the portal projection. This is a finding about the source of the fields, not a claim that the approval workflow is exploitable.
- **Decision gate:** before implementing a user-scoped read endpoint, produce a verified trust-boundary diagram (browser -> ingress/IdP -> portal -> Core/DB), the source and verification of actor and tenant claims, cross-tenant negative tests, and a documented policy owner. Otherwise keep the projection unavailable.

## Deployment topology audit: Compose (configuration only)

- `compose.yml` publishes the portal container on `${AIOPS_BIND_IP:-127.0.0.1}:${AIOPS_PORTAL_HOST_PORT:-7777}:777`. The default bind is loopback, but `AIOPS_BIND_IP` can change it. This is a configuration default, **not evidence of actual Debian runtime settings**.
- The inspected `aiops2-portal` service joins `aiops2-public` and `aiops2-control` and carries `AIOPS_INTERNAL_TOKEN` to make internal calls. The inspected Compose file does not configure an OIDC identity provider, authenticated ingress, or reverse proxy for this service. External host-level controls may still exist and require independent qualification.
- **Debian qualification must collect, without changing it:** effective Compose config and environment (with secrets redacted), active bind address, firewall/proxy/SSO policy, TLS/session identity flow, trusted headers and actor/tenant claim validation, and cross-tenant access tests. Do not infer public accessibility or safety solely from the Compose default.

## Existing automated boundary coverage (scope limitation)

- `tests/test_internal_auth.py` checks that Evidence read/write and Policy check deny absent or invalid **internal service tokens**. It also checks a missing Evidence secret fails closed. These are useful controls, but they **do not** establish portal user authentication, verified actor/tenant claims, or cross-tenant filtering.
- `tests/test_portal_demo.py` checks synthetic demo launch behavior and idempotency, not tenant-scoped read authorization.
- A green existing CI run must not be interpreted as passing the new portal actor/tenant acceptance matrix until new integration and negative authorization tests exist.
